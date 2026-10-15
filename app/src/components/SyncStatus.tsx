import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { jobActivo } from "@/lib/api";
import { useSettings } from "@/lib/queries";
import { haceTiempo, useSync } from "@/lib/sync";
import { cn } from "@/lib/utils";

export function SyncOverlay() {
  const sync = useSync();
  const { data: settings } = useSettings();
  const primera = settings && !settings.sync_inicial_hecha;
  const activo = jobActivo(sync.job);
  const fallo = sync.job?.estado === "error" || !!sync.error;
  if (!primera || sync.minimizado || !(activo || fallo)) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="titulo-sync"
      className="fixed inset-0 z-40 flex items-center justify-center bg-background/70 p-6 backdrop-blur-md"
    >
      <div className="w-full max-w-lg space-y-5 rounded-2xl border bg-popover p-8 shadow-pop">
        <div className="flex items-center gap-3">
          {fallo ? (
            <AlertTriangle className="size-6 text-danger" />
          ) : (
            <Loader2 className="size-6 animate-spin text-primary" />
          )}
          <h2 id="titulo-sync" className="text-xl font-semibold tracking-tight">
            {fallo ? "No se pudo completar la sincronización" : "Preparando todo por primera vez"}
          </h2>
        </div>
        {fallo ? (
          <p role="alert" className="text-sm text-danger">
            {sync.job?.mensaje ?? sync.error}
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              Estamos leyendo todas tus materias y tareas de NEXUS, solo se hace una vez.
            </p>
            <div className="space-y-2">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 break-words font-medium">{sync.job?.paso ?? "Iniciando…"}</span>
                <span className="tabular-nums text-muted-foreground">{sync.job?.progreso ?? 0}%</span>
              </div>
              <Progress value={sync.job?.progreso ?? 0} className="h-2" />
              {sync.job?.mensaje && <p className="text-xs text-muted-foreground">{sync.job.mensaje}</p>}
            </div>
          </>
        )}
        <div className="flex justify-end gap-2">
          {fallo && (
            <Button variant="secondary" onClick={() => sync.iniciar("auto")}>
              Reintentar
            </Button>
          )}
          <Button variant={fallo ? "ghost" : "secondary"} onClick={() => sync.setMinimizado(true)}>
            {fallo ? "Cerrar" : "Seguir en segundo plano"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function SyncIndicator({ className }: { className?: string }) {
  const sync = useSync();
  const { data: settings } = useSettings();
  const [abierto, setAbierto] = useState(false);
  const activo = jobActivo(sync.job);
  const fallo = sync.job?.estado === "error" || !!sync.error;
  const avisos = sync.errores.length;

  let texto: string;
  if (activo) texto = `Sincronizando… ${sync.job?.progreso ?? 0}%`;
  else if (fallo) texto = "Error al sincronizar";
  else if (avisos > 0) texto = `Sincronizado con ${avisos} aviso${avisos === 1 ? "" : "s"}`;
  else texto = `Al día · ${haceTiempo(settings?.ultima_sync ?? null)}`;

  const Icono = activo ? Loader2 : fallo || avisos > 0 ? AlertTriangle : CheckCircle2;

  return (
    <div className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className={cn(
          "flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs font-medium shadow-card outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
          fallo && "text-danger",
          !fallo && avisos > 0 && "text-warning",
        )}
      >
        <Icono
          className={cn(
            "size-3.5",
            activo && "animate-spin text-primary",
            !activo && !fallo && avisos === 0 && "text-success",
          )}
        />
        {texto}
      </button>
      {abierto && (
        <div className="absolute right-0 top-full z-30 mt-2 w-80 space-y-3 rounded-xl border bg-popover p-4 text-sm shadow-pop">
          {activo && sync.job ? (
            <>
              <p className="font-medium">{sync.job.paso}</p>
              <Progress value={sync.job.progreso} className="h-1.5" />
              {sync.job.mensaje && <p className="text-xs text-muted-foreground">{sync.job.mensaje}</p>}
            </>
          ) : (
            <>
              <p className="text-muted-foreground">
                Última sincronización: {haceTiempo(settings?.ultima_sync ?? null)}
              </p>
              {sync.resultado && (
                <p className="text-xs text-muted-foreground">
                  {sync.resultado.materias} materias · {sync.resultado.tareas} tareas ·{" "}
                  {sync.resultado.detalles_leidos} detalles leídos · {sync.resultado.nuevas} nuevas
                </p>
              )}
              {fallo && <p className="text-danger">{sync.job?.mensaje ?? sync.error}</p>}
              {avisos > 0 && (
                <ul className="list-disc space-y-1 pl-4 text-xs text-warning">
                  {sync.errores.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              )}
              <Button size="sm" variant="secondary" onClick={() => sync.iniciar("auto")}>
                <RefreshCw /> Sincronizar ahora
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
