import { Badge } from "@/components/ui/badge";
import type { EstadoTarea } from "@/lib/api";
import { cn } from "@/lib/utils";

const ESTADOS: Record<EstadoTarea, { texto: string; clase: string }> = {
  pendiente: { texto: "Pendiente", clase: "border-warning/40 bg-warning/10 text-warning" },
  generada: { texto: "Generada", clase: "border-info/40 bg-info/10 text-info" },
  entregada: { texto: "Entregada", clase: "border-success/40 bg-success/10 text-success" },
};

export function EstadoBadge({ estado }: { estado: EstadoTarea }) {
  const e = ESTADOS[estado];
  return (
    <Badge variant="outline" className={cn("font-medium", e.clase)}>
      {e.texto}
    </Badge>
  );
}
