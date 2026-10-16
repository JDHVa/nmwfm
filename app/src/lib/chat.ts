import { useCallback, useEffect, useRef, useState } from "react";
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

type Guardado = { items: ItemChat[]; tareaId?: string };

const CLAVE = "nmwfm.chat";

export function cargarChat(): Guardado {
  try {
    const crudo = localStorage.getItem(CLAVE);
    if (!crudo) return { items: [] };
    const g = JSON.parse(crudo) as Guardado;
    return {
      tareaId: g.tareaId,
      items: (g.items ?? []).map((i) => (i.tipo === "asistente" ? { ...i, completo: true } : i)),
    };
  } catch {
    return { items: [] };
  }
}

export function guardarChat(g: Guardado) {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(g));
  } catch {
    return;
  }
}

export function borrarChat() {
  try {
    localStorage.removeItem(CLAVE);
  } catch {
    return;
  }
}

let contador = 0;
const nuevoId = () => `${Date.now().toString(36)}-${++contador}`;

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

export function useChat(tareaIdInicial?: string) {
  const qc = useQueryClient();
  const inicial = useRef(cargarChat());
  const [items, setItems] = useState<ItemChat[]>(() => (tareaIdInicial ? [] : inicial.current.items));
  const [tareaId, setTareaId] = useState<string | undefined>(tareaIdInicial ?? inicial.current.tareaId);
  const [enCurso, setEnCurso] = useState(false);
  const abortar = useRef<AbortController | null>(null);

  useEffect(() => {
    if (items.length === 0 && !tareaId) borrarChat();
    else guardarChat({ items, tareaId });
  }, [items, tareaId]);

  useEffect(() => () => abortar.current?.abort(), []);

  const actualizarUltimoAsistente = useCallback(
    (cambio: (a: Extract<ItemChat, { tipo: "asistente" }>) => void) => {
      setItems((prev) => {
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
    [],
  );

  const alEvento = useCallback(
    (e: EventoChat) => {
      if (e.type === "token") actualizarUltimoAsistente((a) => (a.texto += e.text));
      else if (e.type === "tool_call")
        actualizarUltimoAsistente((a) =>
          a.herramientas.push({ id: nuevoId(), nombre: e.nombre, args: e.args, terminada: false }),
        );
      else if (e.type === "tool_result") {
        actualizarUltimoAsistente((a) => {
          const idx = a.herramientas.findIndex((h) => h.nombre === e.nombre && !h.terminada);
          if (idx >= 0)
            a.herramientas[idx] = { ...a.herramientas[idx], resultado: e.resultado, terminada: true };
        });
        void qc.invalidateQueries();
      } else if (e.type === "confirmar")
        actualizarUltimoAsistente((a) => {
          a.confirmacion = { id: e.id, accion: e.accion, args: e.args, estado: "pendiente" };
        });
      else if (e.type === "error") actualizarUltimoAsistente((a) => (a.error = e.message));
      else if (e.type === "estado") actualizarUltimoAsistente((a) => (a.estado = e.mensaje ?? "Pensando…"));
      else if (e.type === "fin") actualizarUltimoAsistente((a) => (a.completo = true));
    },
    [actualizarUltimoAsistente, qc],
  );

  const enviar = useCallback(
    async (texto: string, adjuntos: File[] = []) => {
      const limpio = texto.trim();
      if ((!limpio && adjuntos.length === 0) || enCurso) return;
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
      const previos = items;
      setItems([...previos, ...nuevos, usuario, asistente]);
      setEnCurso(true);
      const controlador = new AbortController();
      abortar.current = controlador;
      try {
        await chatAsistente(
          {
            mensajes: aMensajes([...previos, { ...usuario, texto: usuario.texto + extra } as ItemChat]),
            ...(tareaId ? { tarea_id: tareaId } : {}),
          },
          alEvento,
          controlador.signal,
        );
      } catch (err) {
        actualizarUltimoAsistente(
          (a) => (a.error = err instanceof Error ? err.message : "Error desconocido"),
        );
      } finally {
        actualizarUltimoAsistente((a) => (a.completo = true));
        setEnCurso(false);
        abortar.current = null;
      }
    },
    [actualizarUltimoAsistente, alEvento, enCurso, items, tareaId],
  );

  const detener = useCallback(() => abortar.current?.abort(), []);

  const nueva = useCallback(() => {
    abortar.current?.abort();
    setItems([]);
    setTareaId(undefined);
    borrarChat();
  }, []);

  const resolverConfirmacion = useCallback(
    async (itemId: string, aceptar: boolean) => {
      const item = items.find((i) => i.id === itemId);
      if (!item || item.tipo !== "asistente" || !item.confirmacion) return;
      try {
        const r = await api.confirmarAsistente(item.confirmacion.id, aceptar);
        setItems((prev) =>
          prev.map((i) =>
            i.id === itemId && i.tipo === "asistente" && i.confirmacion
              ? {
                  ...i,
                  confirmacion: {
                    ...i.confirmacion,
                    estado: aceptar ? "aceptada" : "cancelada",
                    resultado: r.mensaje ?? (aceptar ? "Hecho" : "Cancelado"),
                  },
                }
              : i,
          ),
        );
        void qc.invalidateQueries();
      } catch (err) {
        setItems((prev) =>
          prev.map((i) =>
            i.id === itemId && i.tipo === "asistente" && i.confirmacion
              ? {
                  ...i,
                  confirmacion: {
                    ...i.confirmacion,
                    estado: "error",
                    resultado: err instanceof Error ? err.message : "Error",
                  },
                }
              : i,
          ),
        );
      }
    },
    [items, qc],
  );

  return { items, enCurso, tareaId, enviar, detener, nueva, resolverConfirmacion };
}
