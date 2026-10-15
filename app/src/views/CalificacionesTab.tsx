import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";
import { cn } from "@/lib/utils";

export function CalificacionesTab({ materiaId }: { materiaId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: keys.calificaciones(materiaId),
    queryFn: () => api.calificaciones(materiaId),
  });

  if (isLoading) return <p className="text-muted-foreground">Cargando calificaciones…</p>;
  if (error) return <p className="text-destructive">{error.message}</p>;
  if (!data) return null;

  const etapas = [...new Set(data.items.map((i) => i.etapa))];
  const porcentaje = data.promedio === null ? 0 : Math.min(100, data.promedio * 10);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-6 rounded-xl border bg-card p-5 shadow-card">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Promedio</p>
          <p className="text-4xl font-semibold tabular-nums" aria-label="Promedio">
            {data.promedio === null ? "—" : data.promedio.toFixed(1)}
            <span className="text-base font-normal text-muted-foreground"> / 10</span>
          </p>
        </div>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
          <div className="h-full rounded-full bg-brand" style={{ width: `${porcentaje}%` }} />
        </div>
      </div>
      {etapas.map((etapa) => (
        <section key={etapa} className="space-y-2">
          <h3 className="text-sm font-semibold text-muted-foreground">{etapa}</h3>
          <table className="w-full overflow-hidden rounded-xl border bg-card text-sm shadow-card">
            <tbody className="divide-y">
              {data.items
                .filter((i) => i.etapa === etapa)
                .map((i) => (
                  <tr key={i.numero + i.titulo}>
                    <td className="w-14 px-4 py-2.5 font-semibold tabular-nums text-primary">{i.numero}</td>
                    <td className="px-2 py-2.5">{i.titulo}</td>
                    <td
                      className={cn(
                        "w-32 px-4 py-2.5 text-right tabular-nums",
                        i.obtenida === null && "text-muted-foreground",
                      )}
                    >
                      {i.obtenida === null ? "Sin calificar" : i.obtenida}
                      {i.maxima !== null && i.obtenida !== null && (
                        <span className="text-muted-foreground"> / {i.maxima}</span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}
