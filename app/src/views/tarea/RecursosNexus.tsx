import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";

function tamano(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1_000_000) return `${Math.round(bytes / 1000)} KB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

export function RecursosNexus({ tareaId }: { tareaId: string }) {
  const qc = useQueryClient();
  const { data: recursos = [] } = useQuery({
    queryKey: keys.recursos(tareaId),
    queryFn: () => api.recursos(tareaId),
  });
  const usar = useMutation({
    mutationFn: ({ id, valor }: { id: string; valor: boolean }) => api.usarRecurso(tareaId, id, valor),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.recursos(tareaId) }),
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
                checked={r.usar}
                aria-label={`Usar como insumo: ${r.nombre}`}
                onChange={(e) => usar.mutate({ id: r.id, valor: e.target.checked })}
              />
              <span className="min-w-0 flex-1 truncate">{r.nombre}</span>
              <span className="text-xs text-muted-foreground">{tamano(r.tamano)}</span>
              <span className="text-xs text-muted-foreground">Usar como insumo</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
