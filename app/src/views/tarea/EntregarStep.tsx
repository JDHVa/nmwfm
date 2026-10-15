import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, PartyPopper, Send } from "lucide-react";
import ClickSpark, { type ClickSparkHandle } from "@/components/ClickSpark";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { JobProgress } from "@/components/JobProgress";
import { api, type TareaDetalle } from "@/lib/api";
import { useReducedMotion } from "@/lib/app-context";
import { keys, useGeneracion, useJobRunner, useSettings } from "@/lib/queries";

export function EntregarStep({ tarea, onAtras }: { tarea: TareaDetalle; onAtras: () => void }) {
  const qc = useQueryClient();
  const reducido = useReducedMotion();
  const { data: settings } = useSettings();
  const { data: gen } = useGeneracion(tarea.id);
  const [abierto, setAbierto] = useState(false);
  const chispa = useRef<ClickSparkHandle>(null);
  const caja = useRef<HTMLDivElement>(null);

  const runner = useJobRunner((j) => {
    if (j.estado !== "ok") return;
    qc.invalidateQueries({ queryKey: keys.tarea(tarea.id) });
    qc.invalidateQueries({ queryKey: keys.etapas(tarea.materia_id) });
    const r = caja.current?.getBoundingClientRect();
    chispa.current?.spark(r ? r.width / 2 : undefined, r ? r.height / 2 : undefined);
  });

  const reemplazo = tarea.estado === "entregada";
  const entregada = runner.job?.estado === "ok";
  const mensajeOk = runner.job?.mensaje ?? "La Tarea ha sido cargada y entregada con éxito";

  async function confirmar() {
    setAbierto(false);
    await runner.start(() => api.entregar(tarea.id));
  }

  return (
    <ClickSpark
      sparkColor={["#a78bfa", "#38bdf8", "#34d399"]}
      sparkCount={14}
      sparkRadius={60}
      disabled={reducido}
      shape="star"
      glow={0.4}
    >
      <div ref={caja} className="space-y-5">
        <div className="flex flex-col items-center gap-3 rounded-xl border bg-card p-8 text-center backdrop-blur">
          {entregada ? (
            <>
              <PartyPopper className="size-10 text-emerald-400" />
              <h2 className="text-xl font-semibold">Tarea entregada</h2>
              <p className="text-sm text-muted-foreground">El PDF ya se subió a NEXUS.</p>
            </>
          ) : (
            <>
              <Send className="size-10 text-primary" />
              <h2 className="text-xl font-semibold">
                {reemplazo ? "Reemplazar entrega en NEXUS" : "Entregar en NEXUS"}
              </h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Se subirá el PDF de «{tarea.titulo}». Esta acción no se puede deshacer desde la aplicación.
              </p>
              {settings?.entregar_sin_revisar && (
                <p className="text-xs text-amber-300">«Entregar sin revisar» está activo.</p>
              )}
              {!gen && <p className="text-sm text-destructive">Primero genera el documento.</p>}
              <Button size="lg" disabled={!gen || runner.running} onClick={() => setAbierto(true)}>
                <Send /> {reemplazo ? "Reemplazar entrega" : "Entregar"}
              </Button>
            </>
          )}
        </div>
        <JobProgress job={runner.job} error={runner.error} />
        {entregada && (
          <div
            role="status"
            className="fixed bottom-14 right-6 z-50 rounded-lg border border-emerald-400/40 bg-popover px-4 py-3 text-sm shadow-2xl"
          >
            {mensajeOk}
          </div>
        )}
        {!entregada && (
          <div className="flex justify-start">
            <Button variant="ghost" onClick={onAtras} disabled={runner.running}>
              <ArrowLeft /> Revisar
            </Button>
          </div>
        )}
      </div>

      <Dialog open={abierto} onOpenChange={setAbierto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{reemplazo ? "¿Reemplazar la entrega?" : "¿Entregar esta tarea?"}</DialogTitle>
            {reemplazo && (
              <p
                role="alert"
                className="rounded-md border border-amber-400/50 bg-amber-400/10 px-3 py-2 text-sm font-medium text-amber-300"
              >
                Ya entregaste esta tarea. Se reemplazará la entrega anterior.
              </p>
            )}
            <DialogDescription>
              Se subirá el PDF de «{tarea.numero} · {tarea.titulo}» a NEXUS. Confirma que ya lo revisaste.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAbierto(false)}>
              Cancelar
            </Button>
            <Button onClick={confirmar}>{reemplazo ? "Reemplazar entrega" : "Sí, entregar"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ClickSpark>
  );
}
