import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot } from "lucide-react";
import Stepper, { Step } from "@/components/Stepper";
import { Button } from "@/components/ui/button";
import { EstadoBadge, TipoBadge } from "@/components/EstadoBadge";
import { PageHeader } from "@/components/PageHeader";
import { EVENTO_GENERAR, estaEscribiendo } from "@/lib/atajos";
import { api } from "@/lib/api";
import { useNav } from "@/lib/app-context";
import { useTheme } from "@/lib/theme";
import { token } from "@/lib/tokens";
import { keys, useGeneracion, useJobRunner, useSettings, useTarea } from "@/lib/queries";
import { ExamenCard } from "@/views/tarea/ExamenCard";
import { IndicacionesCard } from "@/views/tarea/IndicacionesCard";
import { DetalleTarea } from "@/views/tarea/DetalleTarea";
import { EntregarStep } from "@/views/tarea/EntregarStep";
import { GenerarStep } from "@/views/tarea/GenerarStep";
import { InsumosStep } from "@/views/tarea/InsumosStep";
import { RevisarStep } from "@/views/tarea/RevisarStep";

export function TareaView({ id, materiaId }: { id: string; materiaId: string }) {
  const { go } = useNav();
  const { resuelto } = useTheme();
  const qc = useQueryClient();
  const { data: tarea, isLoading, error } = useTarea(id);
  const { data: gen } = useGeneracion(id);
  const { data: settings } = useSettings();
  const [elegido, setPaso] = useState<number | null>(null);
  const paso = elegido ?? (gen ? 3 : 1);

  const pasoActual = useRef(paso);
  useEffect(() => {
    pasoActual.current = paso;
  });
  const esExamen = tarea?.tipo === "examen";

  useEffect(() => {
    if (esExamen) return;
    const onPaste = async (e: ClipboardEvent) => {
      const imgs = Array.from(e.clipboardData?.files ?? []).filter((f) => f.type.startsWith("image/"));
      if (imgs.length === 0) return;
      e.preventDefault();
      await api.subirImagenes(id, imgs);
      qc.invalidateQueries({ queryKey: keys.insumos(id) });
      setPaso(1);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.key.toLowerCase() !== "g" || estaEscribiendo(e.target))
        return;
      e.preventDefault();
      if (pasoActual.current === 2) window.dispatchEvent(new Event(EVENTO_GENERAR));
      else setPaso(2);
    };
    document.addEventListener("paste", onPaste);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("paste", onPaste);
      window.removeEventListener("keydown", onKey);
    };
  }, [esExamen, id, qc]);

  const generacion = useJobRunner((j) => {
    qc.invalidateQueries({ queryKey: keys.generacion(id) });
    qc.invalidateQueries({ queryKey: keys.etapas(materiaId) });
    if (j.estado === "ok") {
      qc.invalidateQueries({ queryKey: keys.tarea(id) });
      setPaso(settings?.entregar_sin_revisar ? 4 : 3);
    }
  });

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-8">
      <PageHeader
        atras={
          <Button
            variant="ghost"
            size="sm"
            className="-ml-2"
            onClick={() => go({ name: "materia", id: materiaId })}
          >
            <ArrowLeft /> Etapas
          </Button>
        }
        titulo={tarea ? `${tarea.numero} · ${tarea.titulo}` : "Tarea"}
        acciones={
          tarea && (
            <>
              <Button variant="secondary" size="sm" onClick={() => go({ name: "asistente", tareaId: id })}>
                <Bot /> Preguntar al asistente
              </Button>
              <TipoBadge tarea={tarea} />
              {tarea.tipo !== "examen" && <EstadoBadge tarea={tarea} />}
            </>
          )
        }
      />
      {isLoading && <p className="text-muted-foreground">Cargando tarea…</p>}
      {error && <p className="text-destructive">{error.message}</p>}
      {tarea && tarea.tipo === "examen" && <ExamenCard tarea={tarea} />}
      {tarea && tarea.tipo !== "examen" && (
        <>
          <Stepper
            step={paso}
            onStepChange={setPaso}
            showFooter={false}
            transition="fade"
            frame={false}
            width="100%"
            accentColor={token("--primary")}
            theme={resuelto === "oscuro" ? "dark" : "light"}
          >
            <Step title="Insumos">
              <div className="space-y-6 pt-6">
                <DetalleTarea tarea={tarea} />
                <IndicacionesCard tarea={tarea} />
                <InsumosStep tareaId={id} onContinuar={() => setPaso(2)} />
              </div>
            </Step>
            <Step title="Generar">
              <div className="pt-6">
                <IndicacionesCard tarea={tarea} />
                <GenerarStep
                  tareaId={id}
                  materiaId={materiaId}
                  runner={generacion}
                  onAtras={() => setPaso(1)}
                  onListo={() => setPaso(3)}
                />
              </div>
            </Step>
            <Step title="Revisar">
              <div className="pt-6">
                <RevisarStep tareaId={id} onRegenerar={() => setPaso(2)} onContinuar={() => setPaso(4)} />
              </div>
            </Step>
            <Step title="Entregar">
              <div className="pt-6">
                <EntregarStep tarea={tarea} onAtras={() => setPaso(3)} />
              </div>
            </Step>
          </Stepper>
        </>
      )}
    </div>
  );
}
