import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api, jobActivo, type Job } from "@/lib/api";
import { cn } from "@/lib/utils";

export function JobProgress({
  job,
  error,
  className,
}: {
  job: Job | null;
  error?: string | null;
  className?: string;
}) {
  if (!job && !error) return null;
  const estado = job?.estado;
  return (
    <div
      className={cn("rounded-lg border bg-card/60 p-4 backdrop-blur", className)}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3 text-sm">
        {job && jobActivo(job) && <Loader2 className="size-4 animate-spin text-primary" />}
        {estado === "ok" && <CheckCircle2 className="size-4 text-emerald-400" />}
        {(estado === "error" || error) && <AlertTriangle className="size-4 text-destructive" />}
        <span className="font-medium">{error ?? job?.paso}</span>
        {job && jobActivo(job) && (
          <span className="ml-auto tabular-nums text-muted-foreground">{job.progreso}%</span>
        )}
      </div>
      {job && estado !== "error" && <Progress value={job.progreso} className="mt-3 h-1.5" />}
      {job?.mensaje && <p className="mt-2 text-sm text-muted-foreground">{job.mensaje}</p>}
      {job && estado === "esperando_usuario" && (
        <Button size="sm" variant="outline" className="mt-3" onClick={() => api.continuarJob(job.id)}>
          Ya lo resolví, continuar
        </Button>
      )}
    </div>
  );
}
