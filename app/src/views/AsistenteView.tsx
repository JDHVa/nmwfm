import { useEffect, useLayoutEffect, useRef, useState, type ClipboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUp,
  Check,
  ChevronRight,
  FileDown,
  Loader2,
  MessageSquarePlus,
  PanelLeft,
  Paperclip,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { api, fileUrl } from "@/lib/api";
import { alPulsarEnlace } from "@/lib/opener";
import { useChat, type Confirmacion, type Herramienta, type ItemChat } from "@/lib/chat";
import { useSettings } from "@/lib/queries";
import { haceTiempo } from "@/lib/sync";
import { cn } from "@/lib/utils";
import { HerramientasPanel } from "@/views/HerramientasPanel";

const SUGERENCIAS = [
  "¿Qué vence esta semana?",
  "Explícame la 1.4 de Algoritmos",
  "El profe dijo que la 2.3 es en equipo de 3",
  "Hazme un PDF con estas fotos",
];

const CLAVE_BARRA = "nmwfm.chat.historial";

function leerBarra(): boolean {
  try {
    return localStorage.getItem(CLAVE_BARRA) === "1";
  } catch {
    return false;
  }
}

function guardarBarra(v: boolean) {
  try {
    localStorage.setItem(CLAVE_BARRA, v ? "1" : "0");
  } catch {
    return;
  }
}

export function AsistenteView({ tareaId }: { tareaId?: string }) {
  const [pestana, setPestana] = useState<"chat" | "herramientas">("chat");
  const [precalentando, setPrecalentando] = useState(true);
  const chat = useChat(tareaId);
  const [barra, setBarra] = useState(leerBarra);

  useEffect(() => {
    let vivo = true;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    api
      .precalentarAsistente()
      .then((r) => {
        const cargando = (r as { cargando?: boolean } | null)?.cargando;
        if (vivo && cargando) temporizador = setTimeout(() => vivo && setPrecalentando(false), 25_000);
        else if (vivo) setPrecalentando(false);
      })
      .catch(() => vivo && setPrecalentando(false));
    return () => {
      vivo = false;
      if (temporizador) clearTimeout(temporizador);
      void api.liberarAsistente();
    };
  }, []);

  function alternarBarra() {
    setBarra((v) => {
      guardarBarra(!v);
      return !v;
    });
  }

  return (
    <div className="flex h-full min-h-0">
      {barra && (
        <aside
          aria-label="Historial de conversaciones"
          className="flex w-64 shrink-0 flex-col border-r bg-card"
        >
          <div className="p-3">
            <Button variant="secondary" className="w-full justify-start" onClick={chat.nueva}>
              <MessageSquarePlus /> Nueva conversación
            </Button>
          </div>
          <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
            {chat.historial.length === 0 && (
              <li className="px-3 py-4 text-xs text-muted-foreground">Aún no hay conversaciones.</li>
            )}
            {chat.historial.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  type="button"
                  onClick={() => chat.seleccionar(c.id)}
                  aria-current={c.id === chat.actualId}
                  className={cn(
                    "w-full rounded-lg px-3 py-2 pr-9 text-left text-sm outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
                    c.id === chat.actualId && "bg-accent",
                  )}
                >
                  <span className="block truncate">{c.titulo}</span>
                  <span className="block text-[11px] text-muted-foreground">
                    {haceTiempo(new Date(c.actualizada).toISOString())}
                  </span>
                </button>
                <button
                  type="button"
                  aria-label={`Borrar conversación: ${c.titulo}`}
                  onClick={() => chat.borrar(c.id)}
                  className="absolute right-2 top-2.5 rounded p-1 text-muted-foreground opacity-0 outline-none hover:text-danger focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <h1 className="sr-only">Asistente</h1>
        <div className="flex items-center gap-2 px-4 pt-4">
          <Button
            variant="ghost"
            size="icon"
            aria-label={barra ? "Ocultar historial" : "Mostrar historial"}
            aria-pressed={barra}
            onClick={alternarBarra}
          >
            <PanelLeft />
          </Button>
          <div
            role="tablist"
            aria-label="Asistente y herramientas"
            className="inline-flex rounded-lg bg-muted p-1"
          >
            {(["chat", "herramientas"] as const).map((p) => (
              <button
                key={p}
                type="button"
                role="tab"
                aria-selected={pestana === p}
                onClick={() => setPestana(p)}
                className={cn(
                  "rounded-md px-3 py-1 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  pestana === p
                    ? "bg-card text-foreground shadow-card"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {p === "chat" ? "Chat" : "Herramientas"}
              </button>
            ))}
          </div>
          {pestana === "chat" && !barra && (
            <Button variant="ghost" size="sm" onClick={chat.nueva}>
              <MessageSquarePlus /> Nueva conversación
            </Button>
          )}
          {precalentando && (
            <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" /> Cargando modelo…
            </p>
          )}
        </div>

        {pestana === "chat" ? (
          <ChatPanel chat={chat} />
        ) : (
          <div className="mx-auto flex min-h-0 w-full flex-1 flex-col px-4 pb-6 pt-4 min-[1000px]:w-[70%] max-w-[900px]">
            <HerramientasPanel />
          </div>
        )}
      </div>
    </div>
  );
}

function ChatPanel({ chat }: { chat: ReturnType<typeof useChat> }) {
  const { data: estado } = useQuery({
    queryKey: ["asistente-estado"],
    queryFn: api.asistenteEstado,
    retry: false,
  });
  const { data: ajustes } = useSettings();
  const disponible = !estado || (estado.ollama && estado.modelo_instalado);
  const [texto, setTexto] = useState("");
  const [adjuntos, setAdjuntos] = useState<File[]>([]);
  const fin = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fin.current?.scrollIntoView?.({ block: "end" });
  }, [chat.items]);

  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [texto]);

  const tareaDeContexto = useQuery({
    queryKey: ["tarea", chat.tareaId ?? ""],
    queryFn: () => api.tarea(chat.tareaId!),
    enabled: !!chat.tareaId,
  }).data;

  function enviar(t = texto) {
    if (!disponible || chat.enCurso) return;
    void chat.enviar(t, adjuntos);
    setTexto("");
    setAdjuntos([]);
  }

  function pegar(e: ClipboardEvent<HTMLTextAreaElement>) {
    const imgs = Array.from(e.clipboardData.files).filter((f) => f.type.startsWith("image/"));
    if (imgs.length) {
      e.preventDefault();
      setAdjuntos((a) => [...a, ...imgs]);
    }
  }

  const primerNombre = (ajustes?.nombre ?? "").trim().split(/\s+/)[0];
  const vacio = chat.items.length === 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pb-6 pt-4 min-[1000px]:w-[70%] max-w-[900px]">
          {estado && !disponible && <TarjetaSinOllama estado={estado} />}
          {tareaDeContexto && (
            <p className="mb-4 rounded-lg border bg-card px-3 py-2 text-xs text-muted-foreground">
              Contexto: tarea <strong className="text-foreground">{tareaDeContexto.numero}</strong> ·{" "}
              {tareaDeContexto.titulo}
            </p>
          )}
          <div role="log" aria-label="Conversación" aria-live="polite" className="space-y-6">
            {vacio ? (
              <div className="flex min-h-[50vh] flex-col items-center justify-center gap-8 text-center">
                <h2 className="font-serif text-3xl tracking-tight">
                  ¿En qué te ayudo{primerNombre ? `, ${primerNombre}` : ""}?
                </h2>
                <div className="grid w-full gap-3 sm:grid-cols-2">
                  {SUGERENCIAS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      disabled={!disponible}
                      onClick={() => enviar(s)}
                      className="rounded-xl border bg-card px-4 py-3 text-left text-sm text-muted-foreground outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              chat.items.map((it) => (
                <Mensaje
                  key={it.id}
                  item={it}
                  onConfirmar={(aceptar) => chat.resolverConfirmacion(it.id, aceptar)}
                />
              ))
            )}
          </div>
          <div ref={fin} />
        </div>
      </div>

      <div className="mx-auto w-full px-4 pb-5 min-[1000px]:w-[70%] max-w-[900px]">
        <div className="rounded-2xl border bg-card p-3 shadow-card focus-within:border-ring">
          {adjuntos.length > 0 && (
            <ul className="mb-2 flex flex-wrap gap-2" aria-label="Adjuntos">
              {adjuntos.map((f, i) => (
                <li
                  key={`${f.name}-${i}`}
                  className="flex items-center gap-1 rounded-full border bg-muted px-2 py-1 text-xs"
                >
                  {f.name}
                  <button
                    type="button"
                    aria-label={`Quitar ${f.name}`}
                    onClick={() => setAdjuntos((a) => a.filter((_, j) => j !== i))}
                    className="rounded-full hover:text-danger"
                  >
                    <X className="size-3" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <textarea
            ref={area}
            aria-label="Mensaje"
            rows={1}
            value={texto}
            placeholder={disponible ? "Escribe un mensaje…" : "El asistente no está disponible"}
            disabled={!disponible}
            onChange={(e) => setTexto(e.target.value)}
            onPaste={pegar}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar();
              }
            }}
            className="block max-h-[200px] min-h-[52px] w-full resize-none bg-transparent px-1 py-1 text-[15px] leading-6 outline-none placeholder:text-muted-foreground disabled:opacity-60"
          />
          <div className="mt-1 flex items-center gap-2">
            <input
              ref={input}
              type="file"
              accept="image/*"
              multiple
              hidden
              data-testid="adjuntar-chat"
              onChange={(e) => {
                setAdjuntos((a) => [...a, ...Array.from(e.target.files ?? [])]);
                e.target.value = "";
              }}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Adjuntar imágenes"
              onClick={() => input.current?.click()}
              disabled={!disponible}
            >
              <Paperclip />
            </Button>
            <span className="hidden text-xs text-muted-foreground sm:block">Shift+Enter nueva línea</span>
            <div className="ml-auto">
              {chat.enCurso ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="icon"
                  className="rounded-full"
                  aria-label="Detener"
                  onClick={chat.detener}
                >
                  <Square />
                </Button>
              ) : (
                <Button
                  type="button"
                  size="icon"
                  className="rounded-full"
                  aria-label="Enviar"
                  onClick={() => enviar()}
                  disabled={!disponible || (!texto.trim() && adjuntos.length === 0)}
                >
                  <ArrowUp />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TarjetaSinOllama({ estado }: { estado: { error: string | null; modelo: string; ollama: boolean } }) {
  return (
    <section
      aria-label="Asistente no disponible"
      className="mb-4 space-y-2 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm"
    >
      <p className="flex items-center gap-2 font-semibold text-warning">
        <AlertTriangle className="size-4" />
        {estado.ollama ? `Falta el modelo ${estado.modelo}` : "Falta Ollama"}
      </p>
      <p>
        Instala Ollama desde <span className="font-medium">ollama.com</span> y ejecuta{" "}
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">ollama pull {estado.modelo}</code> en una
        terminal. Cuando termine, vuelve a abrir esta vista.
      </p>
      {estado.error && <p className="text-xs text-muted-foreground">Detalle: {estado.error}</p>}
    </section>
  );
}

function Mensaje({ item, onConfirmar }: { item: ItemChat; onConfirmar: (aceptar: boolean) => void }) {
  if (item.tipo === "usuario") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-secondary px-4 py-2.5 text-[15px] leading-6">
          <p className="whitespace-pre-wrap">{item.texto}</p>
        </div>
      </div>
    );
  }
  if (item.tipo === "sistema") {
    return (
      <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {item.texto}
        {item.enlace && (
          <a
            href={fileUrl(item.enlace.url)}
            onClick={(e) => alPulsarEnlace(e, fileUrl(item.enlace!.url))}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 font-medium text-primary underline underline-offset-2"
          >
            <FileDown className="size-3" /> {item.enlace.etiqueta}
          </a>
        )}
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {item.herramientas.map((h) => (
        <ChipHerramienta key={h.id} h={h} />
      ))}
      {item.texto ? (
        <Markdown texto={item.texto} />
      ) : (
        !item.completo &&
        item.herramientas.length === 0 && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" /> {item.estado ?? "Pensando…"}
          </p>
        )
      )}
      {item.confirmacion && <TarjetaConfirmacion c={item.confirmacion} onResolver={onConfirmar} />}
      {item.error && (
        <p
          role="alert"
          className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
        >
          {item.error}
        </p>
      )}
    </div>
  );
}

function ChipHerramienta({ h }: { h: Herramienta }) {
  return (
    <details className="group text-xs text-muted-foreground">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 rounded px-1 py-0.5 hover:text-foreground">
        {h.terminada ? null : <Loader2 className="size-3 animate-spin" />}
        Usó {h.nombre}
        <ChevronRight className="size-3 transition-transform group-open:rotate-90" />
      </summary>
      <div className="mt-1 space-y-2 border-l pl-3">
        <div>
          <p className="mb-1 uppercase tracking-wide">Argumentos</p>
          <pre className="overflow-x-auto rounded bg-muted p-2 text-foreground">
            {JSON.stringify(h.args, null, 2)}
          </pre>
        </div>
        {h.terminada && (
          <div>
            <p className="mb-1 uppercase tracking-wide">Resultado</p>
            <pre className="max-h-48 overflow-auto rounded bg-muted p-2 text-foreground">
              {JSON.stringify(h.resultado, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </details>
  );
}

function TarjetaConfirmacion({ c, onResolver }: { c: Confirmacion; onResolver: (aceptar: boolean) => void }) {
  const args = c.args as { titulo?: string; tarea_id?: string } | null;
  return (
    <section
      aria-label="Confirmación"
      className={cn(
        "space-y-2 rounded-xl border bg-card p-4 text-sm",
        c.estado === "pendiente" && "border-primary/50",
      )}
    >
      <p className="font-medium">
        {c.accion === "entregar_tarea"
          ? "El asistente quiere entregar una tarea en NEXUS"
          : `Acción: ${c.accion}`}
      </p>
      <p className="text-xs text-muted-foreground">{args?.titulo ?? args?.tarea_id}</p>
      {c.estado === "pendiente" ? (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => onResolver(true)}>
            <Check /> Aceptar
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onResolver(false)}>
            Cancelar
          </Button>
        </div>
      ) : (
        <p className={cn("text-xs", c.estado === "error" ? "text-danger" : "text-muted-foreground")}>
          {c.estado === "aceptada" ? "Aceptada" : c.estado === "cancelada" ? "Cancelada" : "Error"}
          {c.resultado ? `: ${c.resultado}` : ""}
        </p>
      )}
    </section>
  );
}
