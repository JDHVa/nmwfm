import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, jobActivo, useJobUpdates, type InsumoPatch, type Job, type SettingsUpdate } from "@/lib/api";

export const keys = {
  settings: ["settings"] as const,
  materias: ["materias"] as const,
  proximas: ["proximas"] as const,
  novedades: ["novedades"] as const,
  alertas: ["alertas"] as const,
  etapas: (id: string) => ["etapas", id] as const,
  tarea: (id: string) => ["tarea", id] as const,
  insumos: (id: string) => ["insumos", id] as const,
  recursos: (id: string) => ["recursos", id] as const,
  generacion: (id: string) => ["generacion", id] as const,
  generaciones: (id: string) => ["generaciones", id] as const,
};

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: api.getSettings });
}

export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SettingsUpdate) => api.putSettings(data),
    onSuccess: (data) => qc.setQueryData(keys.settings, data),
  });
}

export function useMaterias() {
  return useQuery({ queryKey: keys.materias, queryFn: api.materias });
}

export function useEtapas(materiaId: string) {
  return useQuery({ queryKey: keys.etapas(materiaId), queryFn: () => api.etapas(materiaId) });
}

export function useTarea(id: string) {
  return useQuery({ queryKey: keys.tarea(id), queryFn: () => api.tarea(id) });
}

export function useInsumos(tareaId: string) {
  return useQuery({ queryKey: keys.insumos(tareaId), queryFn: () => api.insumos(tareaId) });
}

export function useGeneracion(tareaId: string) {
  return useQuery({ queryKey: keys.generacion(tareaId), queryFn: () => api.generacion(tareaId) });
}

export function usePatchInsumo(tareaId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: InsumoPatch }) => api.patchInsumo(id, patch),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.insumos(tareaId) }),
  });
}

export function useJobRunner(onFinish?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const finish = useRef(onFinish);
  useEffect(() => {
    finish.current = onFinish;
  });
  const seen = useRef<string | null>(null);

  useJobUpdates(job && jobActivo(job) ? job.id : null, (j) => {
    setJob(j);
    if (!jobActivo(j) && seen.current !== j.id) {
      seen.current = j.id;
      finish.current?.(j);
    }
  });

  async function start(launch: () => Promise<Job>) {
    setError(null);
    try {
      const j = await launch();
      seen.current = null;
      setJob(j);
      return j;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      return null;
    }
  }

  return { job, error, start, running: jobActivo(job), reset: () => setJob(null) };
}
