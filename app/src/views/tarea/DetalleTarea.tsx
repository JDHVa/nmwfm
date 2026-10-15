import type { Rubrica, TareaDetalle } from "@/lib/api";
import { fechaRango } from "@/lib/format";
import { cn } from "@/lib/utils";

const COLORES_NIVEL = [
  "bg-success/10 border-success/30",
  "bg-info/10 border-info/30",
  "bg-warning/10 border-warning/30",
  "bg-danger/10 border-danger/30",
];
const COLORES_TITULO = ["text-success", "text-info", "text-warning", "text-danger"];

function Bloque({ titulo, texto }: { titulo: string; texto: string }) {
  if (!texto.trim()) return null;
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{titulo}</h3>
      <p className="whitespace-pre-wrap text-sm leading-relaxed">{texto}</p>
    </section>
  );
}

export function TablaRubrica({ rubrica }: { rubrica: Rubrica }) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr>
            <th className="w-1/5 border-b bg-muted/40 p-3 text-left font-medium">Criterios</th>
            {rubrica.niveles.map((n, i) => (
              <th
                key={n}
                className={cn(
                  "border-b border-l p-3 text-left font-medium",
                  COLORES_NIVEL[Math.min(i, 3)],
                  COLORES_TITULO[Math.min(i, 3)],
                )}
              >
                {n}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rubrica.criterios.map((c) => (
            <tr key={c.criterio} className="align-top">
              <th scope="row" className="border-b bg-muted/20 p-3 text-left font-medium last:border-b-0">
                {c.criterio}
              </th>
              {c.niveles.map((n, i) => (
                <td
                  key={i}
                  className={cn("border-b border-l p-3 leading-relaxed", COLORES_NIVEL[Math.min(i, 3)])}
                >
                  <span className={cn("mb-1 block text-xs font-semibold", COLORES_TITULO[Math.min(i, 3)])}>
                    {n.puntos} pts
                  </span>
                  {n.descripcion}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DetalleTarea({ tarea }: { tarea: TareaDetalle }) {
  return (
    <div className="space-y-5 rounded-xl border bg-card p-6">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>{fechaRango(tarea.desde, tarea.hasta)}</span>
        {tarea.puntos !== null && <span>{tarea.puntos} pts</span>}
        {tarea.modalidad && <span>{tarea.modalidad}</span>}
      </div>
      <Bloque titulo="Actividades de aprendizaje" texto={tarea.actividades} />
      <Bloque titulo="Contenido" texto={tarea.contenido} />
      <Bloque titulo="Criterios de desempeño" texto={tarea.criterios_desempeno} />
      {tarea.rubrica && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Rúbrica</h3>
          <TablaRubrica rubrica={tarea.rubrica} />
        </section>
      )}
    </div>
  );
}
