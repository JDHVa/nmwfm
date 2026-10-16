import { useQuery } from "@tanstack/react-query";
import { api, type ClaveHistorial } from "@/lib/api";
import { ETIQUETA_HISTORIAL, nota, porcentaje } from "@/lib/calificaciones";
import { keys } from "@/lib/queries";

const CLAVES: ClaveHistorial[] = ["par1", "par2", "emt", "eg", "portafolio", "total"];

export function HistorialSeccion() {
  const { data, error } = useQuery({ queryKey: keys.historial, queryFn: api.historial });
  const periodos = data?.semestres.length ?? 0;
  return (
    <section aria-label="Historial" className="space-y-3 rounded-xl border bg-card p-5 shadow-card">
      <div>
        <h3 className="font-semibold">Historial</h3>
        <p className="text-xs text-muted-foreground">
          {periodos > 0
            ? `Resumen de ${periodos} ${periodos === 1 ? "semestre anterior" : "semestres anteriores"}. Alimenta la predicción «Mío».`
            : "Todavía no hay semestres anteriores registrados."}
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error.message}</p>}
      {data && periodos > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[26rem] text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th scope="col" className="py-1 font-medium">Componente</th>
                <th scope="col" className="py-1 text-right font-medium">Media</th>
                <th scope="col" className="py-1 text-right font-medium">Muestras</th>
                <th scope="col" className="py-1 text-right font-medium">Sacó 100</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {CLAVES.map((c) => {
                const r = data.resumen[c];
                return (
                  <tr key={c}>
                    <th scope="row" className="py-1.5 text-left font-normal">{ETIQUETA_HISTORIAL[c]}</th>
                    <td className="py-1.5 text-right tabular-nums">{r.n === 0 ? "—" : nota(r.media)}</td>
                    <td className="py-1.5 text-right tabular-nums">{r.n}</td>
                    <td className="py-1.5 text-right tabular-nums">{r.n === 0 ? "—" : porcentaje(r.prob_100)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
