import { FilterX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FILTROS_VACIOS, hayFiltros, type Filtros } from "@/lib/filtros";
import { cn } from "@/lib/utils";

const CAMPO =
  "h-9 rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50";

export function FiltrosTareas({
  valor,
  onChange,
  className,
}: {
  valor: Filtros;
  onChange: (f: Filtros) => void;
  className?: string;
}) {
  const set = <K extends keyof Filtros>(k: K, v: Filtros[K]) => onChange({ ...valor, [k]: v });
  return (
    <div
      role="group"
      aria-label="Filtros"
      className={cn("flex flex-wrap items-end gap-3 rounded-xl border bg-card p-3 shadow-card", className)}
    >
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Tipo
        <select
          className={CAMPO}
          value={valor.tipo}
          onChange={(e) => set("tipo", e.target.value as Filtros["tipo"])}
        >
          <option value="todos">Todos</option>
          <option value="dimension">Dimensión</option>
          <option value="evidencia">Evidencia</option>
          <option value="examen">Examen</option>
          <option value="pia">PIA</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Estado
        <select
          className={CAMPO}
          value={valor.estado}
          onChange={(e) => set("estado", e.target.value as Filtros["estado"])}
        >
          <option value="todos">Todos</option>
          <option value="pendiente">Pendiente</option>
          <option value="generada">Generada</option>
          <option value="entregada">Entregada</option>
          <option value="vencida">Vencida</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Vence desde
        <input
          type="date"
          className={CAMPO}
          value={valor.desde}
          onChange={(e) => set("desde", e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Vence hasta
        <input
          type="date"
          className={CAMPO}
          value={valor.hasta}
          onChange={(e) => set("hasta", e.target.value)}
        />
      </label>
      {hayFiltros(valor) && (
        <Button variant="ghost" size="sm" onClick={() => onChange(FILTROS_VACIOS)}>
          <FilterX /> Limpiar filtros
        </Button>
      )}
    </div>
  );
}
