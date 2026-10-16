import { useEffect, useRef, useState, type ClipboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  Check,
  ChevronDown,
  FileDown,
  Loader2,
  MessageSquarePlus,
  Paperclip,
  Send,
  Square,
  Wrench,
  X,
} from "lucide-react";
import { Markdown } from "@/components/Markdown";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, fileUrl } from "@/lib/api";
import { useChat, type Confirmacion, type Herramienta, type ItemChat } from "@/lib/chat";
import { cn } from "@/lib/utils";

const SUGERENCIAS = [
  "¿Qué vence esta semana?",
  "Explícame la 1.4 de Algoritmos",
  "El profe dijo que la 2.3 es en equipo de 3",
  "Hazme un PDF con estas fotos",
  "Portada para el profe Rafael Cavazos",
];

const NOMBRES_HERRAMIENTAS: Record<string, string> = {
  buscar_tareas: "Buscar tareas",
  ver_tarea: "Ver tarea",
  proximas_entregas: "Próximas entregas",
  agregar_indicaciones: "Agregar indicaciones",
  reemplazar_indicaciones: "Reemplazar indicaciones",
  crear_pdf_imagenes: "Crear PDF de imágenes",
  generar_portada: "Generar portada",
  sincronizar: "Sincronizar",
  revisar_entregas: "Revisar entregas",
  generar_tarea: "Generar tarea",
  entregar_tarea: "Entregar tarea",
};

const nombreHerramienta = (n: string) => NOMBRES_HERRAMIENTAS[n] ?? n.replace(/_/g, " ");

export function AsistenteView({ tareaId }: { tareaId?: string }) {
  const chat = useChat(tareaId);
  const { data: estado } = useQuery({
    queryKey: ["asistente-estado"],
    queryFn: api.asistenteEstado,
    retry: false,
  });
  const disponible = !estado || (estado.ollama && estado.modelo_instalado);
  const [texto, setTexto] = useState("");
  const [adjuntos, setAdjuntos] = useState<File[]>([]);
  const fin = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fin.current?.scrollIntoView?.({ block: "end" });
  }, [chat.items]);

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

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col gap-4 p-8">
      <PageHeader
        titulo="Asistente"
        descripcion="Pregunta, pide resúmenes o delega tareas sencillas. Todo corre en tu equipo."
        acciones={
          <Button
            variant="secondary"
            onClick={chat.nueva}
            disabled={chat.items.length === 0 && !chat.tareaId}
          >
            <MessageSquarePlus /> Nueva conversación
          </Button>
        }
      />

      {estado && !disponible && <TarjetaSinOllama estado={estado} />}

      {tareaDeContexto && (
        <p className="rounded-lg border bg-card px-3 py-2 text-xs text-muted-foreground">
          Contexto: tarea <strong className="text-foreground">{tareaDeContexto.numero}</strong> ·{" "}
          {tareaDeContexto.titulo}
        </p>
      )}

      <div
        role="log"
        aria-label="Conversación"
        aria-live="polite"
        className="min-h-0 flex-1 space-y-3 overflow-y-auto rounded-xl border bg-card/60 p-4"
      >
        {chat.items.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <span className="flex size-12 items-center justify-center rounded-2xl bg-accent text-primary">
              <Bot className="size-6" />
            </span>
            <p className="text-sm text-muted-foreground">Prueba con una de estas ideas:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGERENCIAS.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={!disponible}
                  onClick={() => enviar(s)}
                  className="rounded-full border bg-card px-3 py-1.5 text-xs outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          chat.items.map((it) => (
            <Burbuja
              key={it.id}
              item={it}
              onConfirmar={(aceptar) => chat.resolverConfirmacion(it.id, aceptar)}
            />
          ))
        )}
        <div ref={fin} />
      </div>

      <div className="space-y-2 rounded-xl border bg-card p-3 shadow-card">
        {adjuntos.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Adjuntos">
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
        <div className="flex items-end gap-2">
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
          <Textarea
            aria-label="Mensaje"
            rows={2}
            value={texto}
            placeholder={
              disponible ? "Escribe un mensaje… (Enter para enviar)" : "El asistente no está disponible"
            }
            disabled={!disponible}
            onChange={(e) => setTexto(e.target.value)}
            onPaste={pegar}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar();
              }
            }}
            className="resize-none"
          />
          {chat.enCurso ? (
            <Button type="button" variant="secondary" size="icon" aria-label="Detener" onClick={chat.detener}>
              <Square />
            </Button>
          ) : (
            <Button
              type="button"
              size="icon"
              aria-label="Enviar"
              onClick={() => enviar()}
              disabled={!disponible || (!texto.trim() && adjuntos.length === 0)}
            >
              <Send />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function TarjetaSinOllama({ estado }: { estado: { error: string | null; modelo: string; ollama: boolean } }) {
  return (
    <section
      aria-label="Asistente no disponible"
      className="space-y-2 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm"
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

function Burbuja({ item, onConfirmar }: { item: ItemChat; onConfirmar: (aceptar: boolean) => void }) {
  if (item.tipo === "usuario") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand px-4 py-2 text-sm text-primary-foreground">
          <p className="whitespace-pre-wrap">{item.texto}</p>
        </div>
      </div>
    );
  }
  if (item.tipo === "sistema") {
    return (
      <div className="flex justify-center">
        <p className="flex items-center gap-2 rounded-full border bg-muted px-3 py-1 text-xs text-muted-foreground">
          {item.texto}
          {item.enlace && (
            <a
              href={fileUrl(item.enlace.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 font-medium text-primary underline"
            >
              <FileDown className="size-3" /> {item.enlace.etiqueta}
            </a>
          )}
        </p>
      </div>
    );
  }
  return (
    <div className="flex gap-2">
      <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-primary">
        <Bot className="size-4" />
      </span>
      <div className="min-w-0 max-w-[85%] space-y-2">
        {item.herramientas.map((h) => (
          <ChipHerramienta key={h.id} h={h} />
        ))}
        {item.texto ? (
          <div className="rounded-2xl rounded-tl-sm border bg-card px-4 py-2">
            <Markdown texto={item.texto} />
          </div>
        ) : (
          !item.completo &&
          item.herramientas.length === 0 && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" /> Pensando…
            </p>
          )
        )}
        {item.confirmacion && <TarjetaConfirmacion c={item.confirmacion} onResolver={onConfirmar} />}
        {item.error && (
          <p
            role="alert"
            className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
          >
            {item.error}
          </p>
        )}
      </div>
    </div>
  );
}

function ChipHerramienta({ h }: { h: Herramienta }) {
  return (
    <details className="group rounded-lg border bg-muted/50 text-xs">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-1.5 font-medium">
        {h.terminada ? (
          <Wrench className="size-3.5 text-primary" />
        ) : (
          <Loader2 className="size-3.5 animate-spin" />
        )}
        {nombreHerramienta(h.nombre)}
        <ChevronDown className="ml-auto size-3.5 transition-transform group-open:rotate-180" />
      </summary>
      <div className="space-y-2 border-t px-3 py-2">
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">Argumentos</p>
          <pre className="overflow-x-auto rounded bg-background/60 p-2">
            {JSON.stringify(h.args, null, 2)}
          </pre>
        </div>
        {h.terminada && (
          <div>
            <p className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">Resultado</p>
            <pre className="max-h-48 overflow-auto rounded bg-background/60 p-2">
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
        "space-y-2 rounded-xl border p-3 text-sm",
        c.estado === "pendiente" ? "border-warning/40 bg-warning/10" : "bg-card",
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
