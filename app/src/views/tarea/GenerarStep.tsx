import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Sparkles } from "lucide-react";
import DecryptedText from "@/components/DecryptedText";
import RotatingText from "@/components/RotatingText";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { JobProgress } from "@/components/JobProgress";
import { api, type Job } from "@/lib/api";
import { datosDePortada, usePortadaForm } from "@/components/PortadaCampos";
import { PortadaPreview } from "@/views/tarea/PortadaPreview";
import { EVENTO_GENERAR } from "@/lib/atajos";
import { useReducedMotion } from "@/lib/app-context";
import { keys, useInsumos, useMaterias, type useJobRunner } from "@/lib/queries";

const FRASES = [
  "Leyendo tus insumos",
  "Consultando a Gemini",
  "Redactando el documento",
  "Armando la portada",
];

export function GenerarStep({
  tareaId,
  materiaId,
  runner,
  onAtras,
  onListo,
}: {
  tareaId: string;
  materiaId: string;
  runner: ReturnType<typeof useJobRunner>;
  onAtras: () => void;
  onListo: (job: Job) => void;
}) {
  const qc = useQueryClient();
  const reducido = useReducedMotion();
  const { data: insumos = [] } = useInsumos(tareaId);
  const { data: materias = [] } = useMaterias();
  const { valores: portada, cambiar: cambiarPortada } = usePortadaForm(
    materias.find((m) => m.id === materiaId)?.profesor ?? "",
  );
  const [extra, setExtra] = useState("");
  const { job, running } = runner;

  async function generar() {
    const j = await runner.start(() => api.generar(tareaId, extra.trim() || undefined, datosDePortada(portada)));
    if (j) {
      qc.invalidateQueries({ queryKey: keys.generacion(tareaId) });
      qc.invalidateQueries({ queryKey: keys.etapas(materiaId) });
    }
  }

  const alGenerar = useRef(generar);
  useEffect(() => {
    alGenerar.current = generar;
  });
  const puedeGenerar = !running && insumos.length > 0;
  useEffect(() => {
    if (!puedeGenerar) return;
    const on = () => void alGenerar.current();
    window.addEventListener(EVENTO_GENERAR, on);
    return () => window.removeEventListener(EVENTO_GENERAR, on);
  }, [puedeGenerar]);

  return (
    <div className="space-y-5">
      <div className="space-y-2 rounded-xl border bg-card p-4">
        <label htmlFor="instrucciones-extra" className="text-sm font-medium">
          Instrucciones extra (opcional)
        </label>
        <Textarea
          id="instrucciones-extra"
          rows={4}
          placeholder="Por ejemplo: usa un tono formal, incluye un ejemplo numérico, máximo 3 páginas…"
          value={extra}
          onChange={(e) => setExtra(e.target.value)}
          disabled={running}
        />
        <p className="text-xs text-muted-foreground">
          {insumos.length} insumo{insumos.length === 1 ? "" : "s"} listo{insumos.length === 1 ? "" : "s"} para
          enviar.
        </p>
      </div>

      <PortadaPreview tareaId={tareaId} valores={portada} onCambio={cambiarPortada} />

      {running && (
        <div className="flex flex-col items-center gap-3 rounded-xl border bg-card/60 p-8 text-center">
          <Sparkles className="size-6 text-primary" />
          {reducido ? (
            <p className="text-lg font-semibold">{job?.paso}</p>
          ) : (
            <>
              <RotatingText
                texts={FRASES}
                rotationInterval={2600}
                mainClassName="text-xl font-semibold text-primary"
                splitLevelClassName="overflow-hidden"
              />
              <DecryptedText
                key={job?.paso}
                text={job?.paso ?? ""}
                animateOn="view"
                speed={35}
                maxIterations={12}
                sequential
                className="text-sm text-foreground"
                encryptedClassName="text-sm text-primary/70"
              />
            </>
          )}
        </div>
      )}
      <JobProgress job={job} error={runner.error} />

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onAtras} disabled={running}>
          <ArrowLeft /> Insumos
        </Button>
        <div className="flex gap-2">
          {job?.estado === "ok" && (
            <Button variant="secondary" onClick={() => onListo(job)}>
              Ir a revisar
            </Button>
          )}
          <Button onClick={generar} disabled={running || insumos.length === 0}>
            <Sparkles /> {job?.estado === "ok" ? "Generar de nuevo" : "Generar tarea"}
          </Button>
        </div>
      </div>
    </div>
  );
}
