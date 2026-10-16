import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, Sparkles } from "lucide-react";
import DecryptedText from "@/components/DecryptedText";
import RotatingText from "@/components/RotatingText";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { JobProgress } from "@/components/JobProgress";
import { api, type Job } from "@/lib/api";
import { datosDePortada, usePortadaForm } from "@/components/PortadaCampos";
import { PortadaPreview } from "@/views/tarea/PortadaPreview";
import { EVENTO_GENERAR } from "@/lib/atajos";
import { useReducedMotion } from "@/lib/app-context";
import { keys, useInsumos, useMaterias, useSettings, type useJobRunner } from "@/lib/queries";

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
  const { data: settings } = useSettings();
  const fijas = settings?.instrucciones_fijas ?? [];
  const [ajustes, setAjustes] = useState<Record<string, boolean>>({});
  const [prompt, setPrompt] = useState<string | null>(null);
  const [cargandoPrompt, setCargandoPrompt] = useState(false);
  const diferencias = Object.fromEntries(
    fijas
      .filter((i) => ajustes[i.id] !== undefined && ajustes[i.id] !== i.activa)
      .map((i) => [i.id, ajustes[i.id]]),
  );

  async function verPrompt() {
    setCargandoPrompt(true);
    try {
      setPrompt((await api.promptPreview(tareaId, diferencias)).prompt);
    } finally {
      setCargandoPrompt(false);
    }
  }
  const { job, running } = runner;

  async function generar() {
    const j = await runner.start(() =>
      api.generar(
        tareaId,
        extra.trim() || undefined,
        datosDePortada(portada),
        Object.keys(diferencias).length ? diferencias : undefined,
      ),
    );
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

      {fijas.length > 0 && (
        <fieldset className="space-y-3 rounded-xl border bg-card p-4" disabled={running}>
          <legend className="px-1 text-sm font-medium">Instrucciones fijas para esta generación</legend>
          <p className="text-xs text-muted-foreground">
            Parten de lo que tienes en Configuración; los cambios aquí solo aplican a esta tarea.
          </p>
          <ul className="space-y-2">
            {fijas.map((ins) => {
              const marcada = ajustes[ins.id] ?? ins.activa;
              const apa = ins.id === "referencias_apa7";
              return (
                <li
                  key={ins.id}
                  className={apa ? "rounded-lg border border-primary/40 bg-primary/5 p-2.5" : "p-2.5"}
                >
                  <label className="flex cursor-pointer items-start gap-3 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-primary"
                      checked={marcada}
                      onChange={(e) => setAjustes((a) => ({ ...a, [ins.id]: e.target.checked }))}
                    />
                    <span className="flex-1">
                      {apa && <span className="mr-2 font-semibold text-primary">Referencias APA 7.</span>}
                      {ins.texto}
                      {apa && !marcada && (
                        <span className="mt-1 block text-xs text-muted-foreground">
                          Sin esta instrucción el documento no llevará referencias.
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          <Button variant="outline" size="sm" onClick={verPrompt} disabled={cargandoPrompt}>
            <Eye /> Ver prompt
          </Button>
        </fieldset>
      )}

      <Dialog open={prompt !== null} onOpenChange={(o) => !o && setPrompt(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Prompt para Gemini</DialogTitle>
            <DialogDescription>Esto es lo que se enviaría con los ajustes actuales.</DialogDescription>
          </DialogHeader>
          <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/40 p-3 text-xs">
            {prompt}
          </pre>
        </DialogContent>
      </Dialog>

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
      <JobProgress job={job} error={runner.error} onCambio={runner.actualizar} />

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
