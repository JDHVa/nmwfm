import { useEffect, useRef, useState } from "react";
import { ChevronUp, Terminal, Trash2 } from "lucide-react";
import { useLogs, useWsStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const COLORES: Record<string, string> = {
  error: "text-red-400",
  warning: "text-amber-300",
  warn: "text-amber-300",
  info: "text-muted-foreground",
};

export function LogPanel() {
  const { logs, clear } = useLogs();
  const conectado = useWsStatus();
  const [abierto, setAbierto] = useState(false);
  const fin = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (abierto) fin.current?.scrollIntoView?.({ block: "end" });
  }, [logs, abierto]);

  return (
    <section aria-label="Registro" className="relative z-10 border-t bg-background/85 backdrop-blur">
      <div className="flex h-9 items-center gap-2 px-3 text-xs">
        <button
          type="button"
          onClick={() => setAbierto((v) => !v)}
          aria-expanded={abierto}
          className="flex items-center gap-2 rounded px-1.5 py-1 text-muted-foreground hover:text-foreground"
        >
          <Terminal className="size-3.5" />
          <span className="font-medium">Registro</span>
          <span className="tabular-nums">({logs.length})</span>
          <ChevronUp className={cn("size-3.5 transition-transform", abierto && "rotate-180")} />
        </button>
        <span className="truncate text-muted-foreground/80">
          {!abierto && logs.length > 0 && logs[logs.length - 1].message}
        </span>
        <span className="ml-auto flex items-center gap-3">
          {abierto && (
            <button
              type="button"
              onClick={clear}
              className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
            >
              <Trash2 className="size-3.5" /> Limpiar
            </button>
          )}
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <span className={cn("size-2 rounded-full", conectado ? "bg-emerald-400" : "bg-red-400")} />
            {conectado ? "Conectado" : "Sin conexión"}
          </span>
        </span>
      </div>
      {abierto && (
        <div className="h-48 overflow-y-auto border-t px-3 py-2 font-mono text-xs leading-5">
          {logs.length === 0 && <p className="text-muted-foreground">Sin mensajes todavía.</p>}
          {logs.map((l) => (
            <div key={l.id} className={cn("whitespace-pre-wrap", COLORES[l.level] ?? "text-foreground")}>
              <span className="mr-2 text-muted-foreground/60">
                {new Date(l.at).toLocaleTimeString("es-MX")}
              </span>
              {l.message}
            </div>
          ))}
          <div ref={fin} />
        </div>
      )}
    </section>
  );
}
