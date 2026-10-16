import { TriangleAlert } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { MateriaCalificacion } from "@/lib/api";
import { ETIQUETA_TIPO, nota, promedio, puntosDeMaximo, textoAlertas } from "@/lib/calificaciones";
import { cn } from "@/lib/utils";

function MarcaCuidado({ m }: { m: MateriaCalificacion }) {
  if (!m.en_cuidado) return null;
  const texto = textoAlertas(m);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={`Cuidado: ${texto}`}
          title={texto}
          className="inline-flex shrink-0 text-warning"
        >
          <TriangleAlert className="size-4" />
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{texto}</TooltipContent>
    </Tooltip>
  );
}

const TH = "px-3 py-2 font-medium whitespace-nowrap";

export function TablaResumen({
  materias,
  proyectadas,
  semestre,
  escenario,
}: {
  materias: MateriaCalificacion[];
  proyectadas: Record<string, number>;
  semestre: number;
  escenario: string;
}) {
  const totales = promedio(materias.map((m) => m.total_pts));
  const pcts = promedio(materias.flatMap((m) => (m.pct_evaluado === null ? [] : [m.pct_evaluado])));
  return (
    <section aria-label="Tabla resumen de calificaciones" className="rounded-xl border bg-card shadow-card">
      <div className="overflow-x-auto">
        <TooltipProvider delayDuration={150}>
          <table className="w-full min-w-[44rem] text-sm">
            <caption className="sr-only">Resumen de calificaciones por materia</caption>
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th scope="col" className={TH}>Materia</th>
                <th scope="col" className={TH}>Tipo</th>
                <th scope="col" className={cn(TH, "text-right")}>Portafolio</th>
                <th scope="col" className={cn(TH, "text-right")}>Exámenes</th>
                <th scope="col" className={cn(TH, "text-right")}>Total acumulado</th>
                <th scope="col" className={cn(TH, "text-right")}>% sobre lo evaluado</th>
                <th scope="col" className={cn(TH, "text-right")}>Proyectada · {escenario}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {materias.map((m) => (
                <tr key={m.clave} data-testid={`fila-${m.clave}`} className={cn(m.en_cuidado && "bg-warning/5")}>
                  <th scope="row" className="px-3 py-2 text-left font-medium">
                    <span className="flex items-center gap-1.5">
                      <span className="min-w-0">{m.nombre}</span>
                      <MarcaCuidado m={m} />
                    </span>
                  </th>
                  <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                    {m.tipo === null ? "—" : ETIQUETA_TIPO[m.tipo]}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
                    {puntosDeMaximo(m.portafolio_pts, m.portafolio_max)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
                    {puntosDeMaximo(m.examenes_pts, m.examenes_max)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{nota(m.total_pts)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {m.pct_evaluado === null ? "—" : `${nota(m.pct_evaluado)} %`}
                  </td>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">
                    {nota(proyectadas[m.clave] ?? m.proyectada)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t bg-muted/40 font-semibold">
                <th scope="row" className="px-3 py-2 text-left">Promedio del semestre</th>
                <td />
                <td />
                <td />
                <td className="px-3 py-2 text-right tabular-nums">{totales === null ? "—" : nota(totales)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{pcts === null ? "—" : `${nota(pcts)} %`}</td>
                <td className="px-3 py-2 text-right tabular-nums" data-testid="promedio-proyectado">
                  {nota(semestre)}
                </td>
              </tr>
            </tfoot>
          </table>
        </TooltipProvider>
      </div>
    </section>
  );
}
