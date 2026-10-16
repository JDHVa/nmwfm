import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, DatabaseBackup, RefreshCw, RotateCcw, Stethoscope, XCircle } from "lucide-react";
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
import { api, type Diagnostico, type Respaldo, type Settings } from "@/lib/api";
import { keys, useJobRunner, useSaveSettings } from "@/lib/queries";

const INTERVALOS = [0, 1, 2, 4, 6, 12, 24];

export function ConfigAvanzada({ settings }: { settings: Settings }) {
  return (
    <>
      <SincronizacionPeriodica settings={settings} />
      <AsistenteSeccion settings={settings} />
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
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
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

const MODELOS = ["qwen3:4b-instruct-2507-q4_K_M", "qwen3:4b", "qwen3:8b", "llama3.2:3b", "gemma3:4b"];

function AsistenteSeccion({ settings }: { settings: Settings }) {
  const qc = useQueryClient();
  const guardar = useSaveSettings();
  const [edicion, setEdicion] = useState<string | null>(null);
  const modelo = edicion ?? settings.asistente_modelo ?? "qwen3:4b-instruct-2507-q4_K_M";
  const [segundos, setSegundos] = useState<string | null>(null);
  const keepAlive = segundos ?? String(settings.asistente_keep_alive_s ?? 90);
  const estado = useQuery({
    queryKey: ["asistente-estado", settings.asistente_modelo],
    queryFn: api.asistenteEstado,
    retry: false,
  });

  function aplicar() {
    const limpio = modelo.trim();
    setEdicion(null);
    if (limpio && limpio !== settings.asistente_modelo) {
      guardar.mutate(
        { asistente_modelo: limpio },
        { onSuccess: () => qc.invalidateQueries({ queryKey: ["asistente-estado"] }) },
      );
    }
  }

  const e = estado.data;
  return (
    <Seccion titulo="Asistente">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <label htmlFor="asistente-modelo" className="text-sm font-medium">
            Modelo del asistente (Ollama)
          </label>
          <p className="text-xs text-muted-foreground">
            Corre en tu equipo. Si cambias de modelo, descárgalo antes con <code>ollama pull</code>.
          </p>
        </div>
        <>
          <input
            id="asistente-modelo"
            list="modelos-asistente"
            className="h-9 w-56 rounded-md border border-input bg-background px-3 text-sm"
            value={modelo}
            onChange={(ev) => setEdicion(ev.target.value)}
            onBlur={aplicar}
            onKeyDown={(ev) => ev.key === "Enter" && ev.currentTarget.blur()}
          />
          <datalist id="modelos-asistente">
            {MODELOS.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <label htmlFor="asistente-keep-alive" className="text-sm font-medium">
            Liberar GPU tras N segundos
          </label>
          <p className="text-xs text-muted-foreground">
            El modelo se descarga de la memoria de video tras este tiempo sin usar el asistente.
          </p>
        </div>
        <input
          id="asistente-keep-alive"
          type="number"
          min={0}
          step={10}
          className="h-9 w-28 rounded-md border border-input bg-background px-3 text-sm"
          value={keepAlive}
          onChange={(ev) => setSegundos(ev.target.value)}
          onBlur={() => {
            const n = Math.max(0, Math.round(Number(keepAlive)));
            setSegundos(null);
            if (Number.isFinite(n) && n !== (settings.asistente_keep_alive_s ?? 90)) {
              guardar.mutate({ asistente_keep_alive_s: n });
            }
          }}
          onKeyDown={(ev) => ev.key === "Enter" && ev.currentTarget.blur()}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm" role="status" aria-label="Estado de Ollama">
        <Bot className="size-4 text-primary" />
        {estado.isLoading && <span className="text-muted-foreground">Comprobando…</span>}
        {estado.isError && <span className="text-danger">No se pudo consultar el estado</span>}
        {e && (
          <>
            <span className={e.ollama ? "text-success" : "text-danger"}>
              Ollama: {e.ollama ? "conectado" : "no encontrado"}
            </span>
            <span className={e.modelo_instalado ? "text-success" : "text-warning"}>
              Modelo {e.modelo}: {e.modelo_instalado ? "instalado" : "falta descargarlo"}
            </span>
          </>
        )}
        <Button size="sm" variant="ghost" onClick={() => estado.refetch()} disabled={estado.isFetching}>
          <RefreshCw className={estado.isFetching ? "animate-spin" : ""} /> Comprobar de nuevo
        </Button>
      </div>
      {e && (!e.ollama || !e.modelo_instalado) && (
        <p className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs">
          Instala Ollama (ollama.com) y ejecuta <code>ollama pull {e.modelo}</code>.
          {e.error ? ` Detalle: ${e.error}` : ""}
        </p>
      )}
    </Seccion>
  );
}

function RespaldoSeccion() {
  const qc = useQueryClient();
  const { data: respaldos = [] } = useQuery({ queryKey: keys.respaldos, queryFn: api.respaldos });
  const [aRestaurar, setARestaurar] = useState<Respaldo | null>(null);
  const [restaurado, setRestaurado] = useState<string | null>(null);
  const crear = useMutation({
    mutationFn: api.crearRespaldo,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.respaldos }),
  });
  const restaurar = useMutation({
    mutationFn: (nombre: string) => api.restaurarRespaldo(nombre),
    onSuccess: (r) => {
      setARestaurar(null);
      setRestaurado(r.respaldo_previo);
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
        {restaurado && (
          <span className="text-sm text-success">
            Respaldo restaurado (se guardó una copia previa: {restaurado})
          </span>
        )}
      </div>
      {respaldos.length > 0 && (
        <ul className="divide-y rounded-lg border" aria-label="Respaldos">
          {respaldos.map((r) => (
            <li key={r.nombre} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="flex-1">
                {new Date(r.creado_en).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })}
              </span>
              <span className="text-xs text-muted-foreground">{(r.bytes / 1_000_000).toFixed(1)} MB</span>
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
              onClick={() => aRestaurar && restaurar.mutate(aRestaurar.nombre)}
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
  const resultado = runner.job?.estado === "ok" ? (runner.job.resultado as Diagnostico | null) : null;
  return (
    <Seccion titulo="Diagnóstico de NEXUS">
      <p className="text-sm text-muted-foreground">
        Comprueba que la automatización todavía reconoce las páginas de SIASE y NEXUS.
      </p>
      <Button variant="secondary" onClick={() => runner.start(api.diagnostico)} disabled={runner.running}>
        <Stethoscope /> Ejecutar diagnóstico
      </Button>
      <JobProgress job={runner.job} error={runner.error} onCambio={runner.actualizar} />
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
                {p.selectores_faltantes.length > 0 && (
                  <span className="block font-mono text-[11px] text-danger">
                    Selectores faltantes: {p.selectores_faltantes.join(", ")}
                  </span>
                )}
              </span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{p.ms} ms</span>
            </li>
          ))}
        </ul>
      )}
    </Seccion>
  );
}
