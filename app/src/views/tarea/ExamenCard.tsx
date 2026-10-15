import { ClipboardCheck, ExternalLink } from "lucide-react";
import { VencimientoBadge } from "@/components/EstadoBadge";
import { Button } from "@/components/ui/button";
import type { TareaDetalle } from "@/lib/api";
import { fechaRango } from "@/lib/format";
import { URL_NEXUS, abrirEnNavegador } from "@/lib/opener";

export function ExamenCard({ tarea }: { tarea: TareaDetalle }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border bg-card p-10 text-center shadow-card">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-accent text-primary">
        <ClipboardCheck className="size-7" />
      </span>
      <h2 className="text-xl font-semibold">Este examen se contesta directamente en NEXUS</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        nmwfm no genera ni entrega exámenes; esto es solo un recordatorio de la fecha límite.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3 text-sm text-muted-foreground">
        <span>{fechaRango(tarea.desde, tarea.hasta)}</span>
        {tarea.puntos !== null && <span>{tarea.puntos} pts</span>}
        <VencimientoBadge tarea={tarea} />
      </div>
      <Button size="lg" onClick={() => abrirEnNavegador(URL_NEXUS)}>
        <ExternalLink /> Abrir NEXUS
      </Button>
    </div>
  );
}
