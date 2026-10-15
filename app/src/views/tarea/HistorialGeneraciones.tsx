import { lazy, Suspense, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, fileUrl } from "@/lib/api";
import { keys } from "@/lib/queries";
import { haceTiempo } from "@/lib/sync";

const PdfViewer = lazy(() => import("./PdfViewer"));

export function HistorialGeneraciones({ tareaId }: { tareaId: string }) {
  const qc = useQueryClient();
  const { data: versiones = [] } = useQuery({
    queryKey: keys.generaciones(tareaId),
    queryFn: () => api.generaciones(tareaId),
  });
  const [seleccion, setSeleccion] = useState<string[]>([]);
  const restaurar = useMutation({
    mutationFn: (id: string) => api.restaurarGeneracion(tareaId, id),
    onSuccess: (g) => {
      qc.setQueryData(keys.generacion(tareaId), g);
      qc.invalidateQueries({ queryKey: keys.generaciones(tareaId) });
    },
  });

  if (versiones.length < 2) return null;

  const alternar = (id: string) =>
    setSeleccion((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s.slice(-1), id]));
  const comparadas = versiones.filter((v) => seleccion.includes(v.id));

  return (
    <section aria-labelledby="titulo-historial" className="space-y-3 rounded-xl border bg-card p-4">
      <h3 id="titulo-historial" className="flex items-center gap-2 text-sm font-semibold">
        <History className="size-4 text-primary" /> Historial de versiones
      </h3>
      <ul className="divide-y rounded-lg border">
        {[...versiones].reverse().map((v) => (
          <li key={v.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={seleccion.includes(v.id)}
                onChange={() => alternar(v.id)}
                aria-label={`Comparar versión ${v.version}`}
              />
              <span className="font-medium">Versión {v.version}</span>
            </label>
            <span className="text-xs text-muted-foreground">{haceTiempo(v.creada_en)}</span>
            {v.actual && (
              <Badge variant="outline" className="border-success/40 bg-success/10 text-success">
                Actual
              </Badge>
            )}
            {!v.actual && (
              <Button
                size="sm"
                variant="secondary"
                className="ml-auto"
                aria-label={`Restaurar versión ${v.version}`}
                disabled={restaurar.isPending}
                onClick={() => restaurar.mutate(v.id)}
              >
                <RotateCcw /> Restaurar
              </Button>
            )}
          </li>
        ))}
      </ul>
      {comparadas.length === 2 && (
        <div role="region" aria-label="Comparación" className="grid gap-3 lg:grid-cols-2">
          {comparadas.map((v) => (
            <div key={v.id} className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Versión {v.version}</p>
              <Suspense fallback={<p className="text-muted-foreground">Cargando visor…</p>}>
                <PdfViewer url={fileUrl(v.pdf_url)} />
              </Suspense>
            </div>
          ))}
        </div>
      )}
      {comparadas.length === 1 && (
        <p className="text-xs text-muted-foreground">Marca otra versión para compararlas lado a lado.</p>
      )}
    </section>
  );
}
