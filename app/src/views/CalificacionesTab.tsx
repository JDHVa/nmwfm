import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";
import { haceTiempo } from "@/lib/sync";

export function CalificacionesTab({ materiaId }: { materiaId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: keys.calificaciones(materiaId),
    queryFn: () => api.calificaciones(materiaId),
  });

  if (isLoading) return <p className="text-muted-foreground">Cargando calificaciones…</p>;
  if (error) return <p className="text-destructive">{error.message}</p>;
  if (!data) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
        Todavía no se han leído las calificaciones de esta materia. Usa «Sincronizar todo de nuevo» en
        Materias para traerlas desde NEXUS.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Actualizadas {haceTiempo(data.actualizada_en)}</p>
      <div className="overflow-x-auto rounded-xl border bg-card shadow-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left">
              {data.columnas.map((c) => (
                <th key={c} scope="col" className="px-4 py-2.5 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.filas.map((fila, i) => (
              <tr key={i}>
                {fila.map((celda, j) => (
                  <td key={j} className={j === 0 ? "px-4 py-2.5" : "px-4 py-2.5 tabular-nums"}>
                    {celda}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
