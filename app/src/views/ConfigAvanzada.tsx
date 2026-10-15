import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, DatabaseBackup, RotateCcw, Stethoscope, XCircle } from "lucide-react";
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
import { api, type DiagnosticoResultado, type Respaldo, type Settings } from "@/lib/api";
import { keys, useJobRunner, useSaveSettings } from "@/lib/queries";

const INTERVALOS = [0, 1, 2, 4, 6, 12, 24];

export function ConfigAvanzada({ settings }: { settings: Settings }) {
  return (
    <>
      <SincronizacionPeriodica settings={settings} />
      <RespaldoSeccion />
      <DiagnosticoSeccion />
    </>
  );
}

function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section aria-label={titulo} className="space-y-4 rounded-xl border bg-card p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{titulo}</h2>
      {children}
    </section>
  );
}

function SincronizacionPeriodica({ settings }: { settings: Settings }) {
  const guardar = useSaveSettings();
  return (
    <Seccion titulo="Sincronización">
      <div className="flex items-center justify-between gap-4">
        <div>
          <label htmlFor="sync-horas" className="text-sm font-medium">
            Sincronizar automáticamente cada N horas
          </label>
          <p className="text-xs text-muted-foreground">
            Mientras la aplicación esté abierta. Es incremental y no interrumpe.
          </p>
        </div>
        <select
          id="sync-horas"
          className="h-9 rounded-md border border-input bg-background/50 px-2 text-sm"
          value={settings.sync_cada_horas ?? 0}
          onChange={(e) => guardar.mutate({ sync_cada_horas: Number(e.target.value) })}
        >
          {INTERVALOS.map((h) => (
            <option key={h} value={h}>
              {h === 0 ? "Desactivado" : `Cada ${h} ${h === 1 ? "hora" : "horas"}`}
            </option>
          ))}
        </select>
      </div>
    </Seccion>
  );
}

function RespaldoSeccion() {
  const qc = useQueryClient();
  const { data: respaldos = [] } = useQuery({ queryKey: keys.respaldos, queryFn: api.respaldos });
  const [aRestaurar, setARestaurar] = useState<Respaldo | null>(null);
  const [restaurado, setRestaurado] = useState(false);
  const crear = useMutation({
    mutationFn: api.crearRespaldo,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.respaldos }),
  });
  const restaurar = useMutation({
    mutationFn: (id: string) => api.restaurarRespaldo(id),
    onSuccess: () => {
      setARestaurar(null);
      setRestaurado(true);
      qc.invalidateQueries();
    },
  });

  return (
    <Seccion titulo="Respaldo">
      <p className="text-sm text-muted-foreground">
        Guarda una copia de tus datos (tareas, insumos y generaciones) o vuelve a una anterior.
      </p>
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => crear.mutate()} disabled={crear.isPending}>
          <DatabaseBackup /> {crear.isPending ? "Creando…" : "Crear respaldo"}
        </Button>
        {crear.error && <span className="text-sm text-danger">{crear.error.message}</span>}
        {restaurado && <span className="text-sm text-success">Respaldo restaurado</span>}
      </div>
      {respaldos.length > 0 && (
        <ul className="divide-y rounded-lg border" aria-label="Respaldos">
          {respaldos.map((r) => (
            <li key={r.id} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="flex-1">
                {new Date(r.creado_en).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })}
              </span>
              <span className="text-xs text-muted-foreground">{(r.tamano / 1_000_000).toFixed(1)} MB</span>
              <Button size="sm" variant="ghost" onClick={() => setARestaurar(r)}>
                <RotateCcw /> Restaurar
              </Button>
            </li>
          ))}
        </ul>
      )}
      <Dialog open={!!aRestaurar} onOpenChange={(v) => !v && setARestaurar(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Restaurar este respaldo?</DialogTitle>
            <DialogDescription>
              Se reemplazarán tus datos actuales por los del respaldo. Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setARestaurar(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={restaurar.isPending}
              onClick={() => aRestaurar && restaurar.mutate(aRestaurar.id)}
            >
              Sí, restaurar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Seccion>
  );
}

function DiagnosticoSeccion() {
  const runner = useJobRunner();
  const resultado =
    runner.job?.estado === "ok" ? (runner.job.resultado as DiagnosticoResultado | null) : null;
  return (
    <Seccion titulo="Diagnóstico de NEXUS">
      <p className="text-sm text-muted-foreground">
        Comprueba que la automatización todavía reconoce las páginas de SIASE y NEXUS.
      </p>
      <Button variant="secondary" onClick={() => runner.start(api.diagnostico)} disabled={runner.running}>
        <Stethoscope /> Ejecutar diagnóstico
      </Button>
      <JobProgress job={runner.job} error={runner.error} />
      {resultado && (
        <ul className="divide-y rounded-lg border" aria-label="Reporte de diagnóstico">
          {resultado.pasos.map((p) => (
            <li key={p.nombre} className="flex items-start gap-3 px-3 py-2 text-sm">
              {p.ok ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
              ) : (
                <XCircle className="mt-0.5 size-4 shrink-0 text-danger" />
              )}
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{p.nombre}</span>
                <span className={p.ok ? "text-xs text-muted-foreground" : "text-xs text-danger"}>
                  {p.detalle}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Seccion>
  );
}
