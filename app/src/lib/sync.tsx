import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, emitLocalLog, type Job, type SyncModo, type SyncResultado } from "@/lib/api";
import { keys, useJobRunner } from "@/lib/queries";

type SyncCtx = {
  job: Job | null;
  running: boolean;
  error: string | null;
  minimizado: boolean;
  setMinimizado: (v: boolean) => void;
  iniciar: (modo: SyncModo) => Promise<void>;
  errores: string[];
  resultado: SyncResultado | null;
};

const Ctx = createContext<SyncCtx | null>(null);

export function resultadoDe(job: Job | null): SyncResultado | null {
  const r = job?.resultado as Partial<SyncResultado> | null | undefined;
  if (!r || typeof r !== "object") return null;
  return {
    materias: r.materias ?? 0,
    tareas: r.tareas ?? 0,
    detalles_leidos: r.detalles_leidos ?? 0,
    nuevas: r.nuevas ?? 0,
    errores: r.errores ?? [],
  };
}

export function SyncProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [minimizado, setMinimizado] = useState(false);
  const runner = useJobRunner((j) => {
    qc.invalidateQueries({ queryKey: keys.settings });
    qc.invalidateQueries({ queryKey: keys.materias });
    qc.invalidateQueries({ queryKey: ["etapas"] });
    qc.invalidateQueries({ queryKey: ["tarea"] });
    const errores = resultadoDe(j)?.errores ?? [];
    errores.forEach((e) => emitLocalLog("error", `Sincronización: ${e}`));
    if (j.estado === "error") emitLocalLog("error", `Sincronización: ${j.mensaje ?? "falló"}`);
  });
  const { start } = runner;
  const lanzado = useRef(false);

  useEffect(() => {
    if (lanzado.current) return;
    lanzado.current = true;
    void start(() => api.sync("auto"));
  }, [start]);

  const value = useMemo<SyncCtx>(
    () => ({
      job: runner.job,
      running: runner.running,
      error: runner.error,
      minimizado,
      setMinimizado,
      iniciar: async (modo) => {
        setMinimizado(false);
        await start(() => api.sync(modo));
      },
      errores: resultadoDe(runner.job)?.errores ?? [],
      resultado: resultadoDe(runner.job),
    }),
    [runner.job, runner.running, runner.error, minimizado, start],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSync(): SyncCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("SyncProvider ausente");
  return ctx;
}

export function haceTiempo(iso: string | null, ahora = Date.now()): string {
  if (!iso) return "sin sincronizar";
  const min = Math.max(0, Math.round((ahora - new Date(iso).getTime()) / 60000));
  if (min < 1) return "hace un momento";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  return `hace ${Math.round(h / 24)} d`;
}
