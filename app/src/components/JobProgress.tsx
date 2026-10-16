import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, OctagonX, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { api, jobActivo, jobCancelado, type Job } from "@/lib/api";
import { cn } from "@/lib/utils";

export function DetenerButton({
  job,
  onCambio,
  confirmar,
  className,
}: {
  job: Job | null;
  onCambio?: (job: Job) => void;
  confirmar?: boolean;
  className?: string;
}) {
  const [enviando, setEnviando] = useState(false);
  const [abierto, setAbierto] = useState(false);
  if (!job || !jobActivo(job)) return null;

  async function detener() {
    if (!job) return;
    setAbierto(false);
    setEnviando(true);
    try {
      onCambio?.(await api.cancelarJob(job.id));
    } catch {
      return;
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        className={cn("text-destructive", className)}
        disabled={enviando}
        onClick={() => (confirmar ? setAbierto(true) : void detener())}
      >
        <Square /> Detener
      </Button>
      <Dialog open={abierto} onOpenChange={setAbierto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Detener la entrega?</DialogTitle>
            <DialogDescription>
              Se cancelará el proceso y se cerrará el navegador. Revisa en NEXUS si la entrega alcanzó a
              subirse antes de volver a intentarlo.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAbierto(false)}>
              Seguir entregando
            </Button>
            <Button variant="destructive" onClick={detener}>
              Sí, detener
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function JobProgress({
  job,
  error,
  className,
  onCambio,
  confirmar,
}: {
  job: Job | null;
  error?: string | null;
  className?: string;
  onCambio?: (job: Job) => void;
  confirmar?: boolean;
}) {
  if (!job && !error) return null;
  const estado = job?.estado;
  const cancelado = jobCancelado(job);
  const fallo = (estado === "error" && !cancelado) || !!error;
  return (
    <div className={cn("rounded-lg border bg-card p-4", className)} role="status" aria-live="polite">
      <div className="flex items-center gap-3 text-sm">
        {job && jobActivo(job) && <Loader2 className="size-4 animate-spin text-primary" />}
        {estado === "ok" && <CheckCircle2 className="size-4 text-success" />}
        {cancelado && !error && <OctagonX className="size-4 text-muted-foreground" />}
        {fallo && <AlertTriangle className="size-4 text-destructive" />}
        <span className="font-medium">{error ?? job?.paso}</span>
        {job && jobActivo(job) && (
          <span className="ml-auto tabular-nums text-muted-foreground">{job.progreso}%</span>
        )}
      </div>
      {job && estado !== "error" && <Progress value={job.progreso} className="mt-3 h-1.5" />}
      {job?.mensaje && <p className="mt-2 text-sm text-muted-foreground">{job.mensaje}</p>}
      <div className="mt-3 flex flex-wrap gap-2 empty:hidden">
        {job && estado === "esperando_usuario" && (
          <Button size="sm" variant="outline" onClick={() => api.continuarJob(job.id)}>
            Ya lo resolví, continuar
          </Button>
        )}
        <DetenerButton job={job} onCambio={onCambio} confirmar={confirmar} />
      </div>
    </div>
  );
}
