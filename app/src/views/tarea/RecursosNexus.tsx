import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";

export function RecursosNexus({ tareaId }: { tareaId: string }) {
  const qc = useQueryClient();
  const { data: recursos = [] } = useQuery({
    queryKey: keys.recursos(tareaId),
    queryFn: () => api.recursos(tareaId),
  });
  const usar = useMutation({
    mutationFn: (id: string) => api.usarRecurso(tareaId, id),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.recursos(tareaId) });
      qc.invalidateQueries({ queryKey: keys.insumos(tareaId) });
    },
  });

  if (recursos.length === 0) return null;

  return (
    <section aria-labelledby="titulo-recursos" className="space-y-2 rounded-xl border bg-card p-4">
      <h3 id="titulo-recursos" className="flex items-center gap-2 text-sm font-medium">
        <FileText className="size-4 text-primary" /> Recursos de NEXUS
      </h3>
      <ul className="divide-y rounded-lg border">
        {recursos.map((r) => (
          <li key={r.id}>
            <label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={r.usado}
                disabled={r.usado || !r.descargado || usar.isPending}
                aria-label={`Usar como insumo: ${r.nombre}`}
                onChange={() => usar.mutate(r.id)}
              />
              <span className="min-w-0 flex-1 truncate">{r.nombre}</span>
              <span className="text-xs text-muted-foreground">
                {r.usado ? "Ya es un insumo" : r.descargado ? "Usar como insumo" : "Sin descargar"}
              </span>
            </label>
          </li>
        ))}
      </ul>
      {usar.error && <p className="text-xs text-danger">{usar.error.message}</p>}
    </section>
  );
}
