import { Badge } from "@/components/ui/badge";
import type { EstadoTarea } from "@/lib/api";
import { cn } from "@/lib/utils";

const ESTADOS: Record<EstadoTarea, { texto: string; clase: string }> = {
  pendiente: { texto: "Pendiente", clase: "border-amber-400/40 bg-amber-400/10 text-amber-300" },
  generada: { texto: "Generada", clase: "border-sky-400/40 bg-sky-400/10 text-sky-300" },
  entregada: { texto: "Entregada", clase: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300" },
};

export function EstadoBadge({ estado }: { estado: EstadoTarea }) {
  const e = ESTADOS[estado];
  return (
    <Badge variant="outline" className={cn("font-medium", e.clase)}>
      {e.texto}
    </Badge>
  );
}
