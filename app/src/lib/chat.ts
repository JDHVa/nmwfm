import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, chatAsistente, type EventoChat, type MensajeChat } from "@/lib/api";

export type Herramienta = {
  id: string;
  nombre: string;
  args: unknown;
  resultado?: unknown;
  terminada: boolean;
};

export type Confirmacion = {
  id: string;
  accion: string;
  args: unknown;
  estado: "pendiente" | "aceptada" | "cancelada" | "error";
  resultado?: string;
};

export type ItemChat =
  | { id: string; tipo: "usuario"; texto: string; adjuntos?: number }
  | {
      id: string;
      tipo: "asistente";
      texto: string;
      herramientas: Herramienta[];
      estado?: string;
      confirmacion?: Confirmacion;
      error?: string;
      completo: boolean;
    }
  | { id: string; tipo: "sistema"; texto: string; enlace?: { url: string; etiqueta: string } };

export type Conversacion = {
  id: string;
  titulo: string;
  items: ItemChat[];
  tareaId?: string;
  actualizada: number;
};

type Almacen = { actual: string | null; conversaciones: Conversacion[] };

const CLAVE = "nmwfm.chats";
const MAX_CONVERSACIONES = 40;

let contador = 0;
const nuevoId = () => `${Date.now().toString(36)}-${++contador}`;

export function cargarAlmacen(): Almacen {
  try {
    const crudo = localStorage.getItem(CLAVE);
    if (!crudo) return { actual: null, conversaciones: [] };
    const a = JSON.parse(crudo) as Almacen;
    return {
      actual: a.actual ?? null,
      conversaciones: (a.conversaciones ?? []).map((c) => ({
        ...c,
        items: c.items.map((i) => (i.tipo === "asistente" ? { ...i, completo: true } : i)),
      })),
    };
  } catch {
    return { actual: null, conversaciones: [] };
  }
}

export function guardarAlmacen(a: Almacen) {
  try {
    if (a.conversaciones.length === 0) localStorage.removeItem(CLAVE);
    else localStorage.setItem(CLAVE, JSON.stringify(a));
  } catch {
    return;
  }
}

export function tituloDe(items: ItemChat[]): string {
  const primero = items.find((i) => i.tipo === "usuario");
  const t = primero?.texto.trim().replace(/\s+/g, " ") ?? "";
  return t.length > 42 ? `${t.slice(0, 42)}…` : t || "Conversación nueva";
}

export function aMensajes(items: ItemChat[]): MensajeChat[] {
  const salida: MensajeChat[] = [];
  for (const i of items) {
    if (i.tipo === "usuario") salida.push({ rol: "user", contenido: i.texto });
    else if (i.tipo === "asistente") {
      i.herramientas
        .filter((h) => h.terminada)
        .forEach((h) =>
          salida.push({ rol: "tool", herramienta: h.nombre, contenido: JSON.stringify(h.resultado ?? null) }),
        );
      if (i.texto.trim()) salida.push({ rol: "assistant", contenido: i.texto });
    }
  }
  return salida;
}

function crearVacia(tareaId?: string): Conversacion {
  return { id: nuevoId(), titulo: "Conversación nueva", items: [], tareaId, actualizada: Date.now() };
}

function estadoInicial(tareaIdInicial?: string): { conversaciones: Conversacion[]; actualId: string } {
  const almacen = cargarAlmacen();
  const guardadas = almacen.conversaciones;
  if (tareaIdInicial) {
    const nueva = crearVacia(tareaIdInicial);
    return { conversaciones: [nueva, ...guardadas], actualId: nueva.id };
  }
  const actual = guardadas.find((c) => c.id === almacen.actual) ?? guardadas[0];
  if (actual) return { conversaciones: guardadas, actualId: actual.id };
  const vacia = crearVacia();
  return { conversaciones: [vacia], actualId: vacia.id };
}

export function useChat(tareaIdInicial?: string) {
  const qc = useQueryClient();
  const inicial = useRef(estadoInicial(tareaIdInicial));
  const [conversaciones, setConversaciones] = useState<Conversacion[]>(inicial.current.conversaciones);
  const [actualId, setActualId] = useState<string>(inicial.current.actualId);
  const actualRef = useRef(actualId);
  const [enCurso, setEnCurso] = useState(false);
  const abortar = useRef<AbortController | null>(null);

  useEffect(() => {
    actualRef.current = actualId;
  }, [actualId]);

  useEffect(() => {
    const guardables = conversaciones.filter((c) => c.items.length > 0).slice(0, MAX_CONVERSACIONES);
    guardarAlmacen({
      actual: guardables.some((c) => c.id === actualId) ? actualId : null,
      conversaciones: guardables,
    });
  }, [conversaciones, actualId]);

  useEffect(() => () => abortar.current?.abort(), []);

  const actual = conversaciones.find((c) => c.id === actualId) ?? conversaciones[0];
  const items = useMemo(() => actual?.items ?? [], [actual]);

  const cambiarItems = useCallback((id: string, fn: (prev: ItemChat[]) => ItemChat[]) => {
    setConversaciones((prev) =>
      prev.map((c) => {
        if (c.id !== id) return c;
        const nuevos = fn(c.items);
        return { ...c, items: nuevos, titulo: tituloDe(nuevos), actualizada: Date.now() };
      }),
    );
  }, []);

  const actualizarUltimoAsistente = useCallback(
    (id: string, cambio: (a: Extract<ItemChat, { tipo: "asistente" }>) => void) => {
      cambiarItems(id, (prev) => {
        const copia = [...prev];
        for (let i = copia.length - 1; i >= 0; i--) {
          const it = copia[i];
          if (it.tipo === "asistente") {
            const clon = { ...it, herramientas: [...it.herramientas] };
            cambio(clon);
            copia[i] = clon;
            break;
          }
        }
        return copia;
      });
    },
    [cambiarItems],
  );

  const alEvento = useCallback(
    (id: string, e: EventoChat) => {
      const act = (c: (a: Extract<ItemChat, { tipo: "asistente" }>) => void) =>
        actualizarUltimoAsistente(id, c);
      if (e.type === "token") act((a) => (a.texto += e.text));
      else if (e.type === "tool_call")
        act((a) => a.herramientas.push({ id: nuevoId(), nombre: e.nombre, args: e.args, terminada: false }));
      else if (e.type === "tool_result") {
        act((a) => {
          const idx = a.herramientas.findIndex((h) => h.nombre === e.nombre && !h.terminada);
          if (idx >= 0)
            a.herramientas[idx] = { ...a.herramientas[idx], resultado: e.resultado, terminada: true };
        });
        void qc.invalidateQueries();
      } else if (e.type === "confirmar")
        act((a) => {
          a.confirmacion = { id: e.id, accion: e.accion, args: e.args, estado: "pendiente" };
        });
      else if (e.type === "error") act((a) => (a.error = e.message));
      else if (e.type === "estado")
        act((a) => (a.estado = e.mensaje ?? (e.estado === "cargando" ? "Cargando modelo…" : "Pensando…")));
      else if (e.type === "fin") act((a) => (a.completo = true));
    },
    [actualizarUltimoAsistente, qc],
  );

  const enviar = useCallback(
    async (texto: string, adjuntos: File[] = []) => {
      const limpio = texto.trim();
      if ((!limpio && adjuntos.length === 0) || enCurso || !actual) return;
      const id = actual.id;
      let extra = "";
      const nuevos: ItemChat[] = [];
      if (adjuntos.length > 0) {
        try {
          const { pdf_url } = await api.herramientaPdf(adjuntos, true);
          nuevos.push({
            id: nuevoId(),
            tipo: "sistema",
            texto: `Se unieron ${adjuntos.length} imagen(es) en un PDF.`,
            enlace: { url: pdf_url, etiqueta: "Abrir PDF" },
          });
          extra = `\n\n(Adjunté ${adjuntos.length} imagen(es); ya se creó el PDF: ${pdf_url})`;
        } catch (err) {
          nuevos.push({
            id: nuevoId(),
            tipo: "sistema",
            texto: `No se pudo crear el PDF: ${err instanceof Error ? err.message : "error desconocido"}`,
          });
        }
      }
      const usuario: ItemChat = {
        id: nuevoId(),
        tipo: "usuario",
        texto: limpio || "Adjunté imágenes",
        adjuntos: adjuntos.length || undefined,
      };
      const asistente: ItemChat = {
        id: nuevoId(),
        tipo: "asistente",
        texto: "",
        herramientas: [],
        completo: false,
      };
      const previos = actual.items;
      cambiarItems(id, () => [...previos, ...nuevos, usuario, asistente]);
      setEnCurso(true);
      const controlador = new AbortController();
      abortar.current = controlador;
      try {
        await chatAsistente(
          {
            mensajes: aMensajes([...previos, { ...usuario, texto: usuario.texto + extra } as ItemChat]),
            ...(actual.tareaId ? { tarea_id: actual.tareaId } : {}),
          },
          (e) => alEvento(id, e),
          controlador.signal,
        );
      } catch (err) {
        actualizarUltimoAsistente(
          id,
          (a) => (a.error = err instanceof Error ? err.message : "Error desconocido"),
        );
      } finally {
        actualizarUltimoAsistente(id, (a) => (a.completo = true));
        setEnCurso(false);
        abortar.current = null;
      }
    },
    [actual, actualizarUltimoAsistente, alEvento, cambiarItems, enCurso],
  );

  const detener = useCallback(() => abortar.current?.abort(), []);

  const nueva = useCallback(() => {
    abortar.current?.abort();
    setEnCurso(false);
    setConversaciones((prev) => {
      const vacia = prev.find((c) => c.items.length === 0);
      if (vacia) {
        setActualId(vacia.id);
        return prev.map((c) => (c.id === vacia.id ? { ...c, tareaId: undefined } : c));
      }
      const nuevaConv = crearVacia();
      setActualId(nuevaConv.id);
      return [nuevaConv, ...prev];
    });
  }, []);

  const seleccionar = useCallback((id: string) => {
    abortar.current?.abort();
    setEnCurso(false);
    setActualId(id);
  }, []);

  const borrar = useCallback((id: string) => {
    setConversaciones((prev) => {
      const resto = prev.filter((c) => c.id !== id);
      if (resto.length === 0) {
        const vacia = crearVacia();
        setActualId(vacia.id);
        return [vacia];
      }
      if (actualRef.current === id) {
        abortar.current?.abort();
        setEnCurso(false);
        setActualId(resto[0].id);
      }
      return resto;
    });
  }, []);

  const resolverConfirmacion = useCallback(
    async (itemId: string, aceptar: boolean) => {
      const item = items.find((i) => i.id === itemId);
      if (!item || item.tipo !== "asistente" || !item.confirmacion || !actual) return;
      const id = actual.id;
      const poner = (estado: Confirmacion["estado"], resultado: string) =>
        cambiarItems(id, (prev) =>
          prev.map((i) =>
            i.id === itemId && i.tipo === "asistente" && i.confirmacion
              ? { ...i, confirmacion: { ...i.confirmacion, estado, resultado } }
              : i,
          ),
        );
      try {
        const r = await api.confirmarAsistente(item.confirmacion.id, aceptar);
        poner(aceptar ? "aceptada" : "cancelada", r.mensaje ?? (aceptar ? "Hecho" : "Cancelado"));
        void qc.invalidateQueries();
      } catch (err) {
        poner("error", err instanceof Error ? err.message : "Error");
      }
    },
    [actual, cambiarItems, items, qc],
  );

  const historial = conversaciones
    .filter((c) => c.items.length > 0)
    .sort((a, b) => b.actualizada - a.actualizada);

  return {
    items,
    enCurso,
    tareaId: actual?.tareaId,
    actualId: actual?.id ?? actualId,
    historial,
    enviar,
    detener,
    nueva,
    seleccionar,
    borrar,
    resolverConfirmacion,
  };
}
