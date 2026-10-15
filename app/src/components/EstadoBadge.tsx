import { Badge } from "@/components/ui/badge";
import type { Tarea } from "@/lib/api";
import { fechaCorta, vencimientoDe, type NivelVencimiento } from "@/lib/vencimiento";
import { cn } from "@/lib/utils";

const CLASES = {
  pendiente: "border-warning/40 bg-warning/10 text-warning",
  generada: "border-info/40 bg-info/10 text-info",
  entregada: "border-success/40 bg-success/10 text-success",
  vencida: "border-danger/40 bg-danger/10 text-danger",
};

type Estado = Pick<Tarea, "estado" | "entregada_en" | "vencida" | "hasta">;

export function EstadoBadge({ tarea }: { tarea: Estado }) {
  let texto: string;
  let clase: string;
  if (tarea.estado === "entregada") {
    texto = tarea.entregada_en ? `Entregada el ${fechaCorta(tarea.entregada_en)}` : "Entregada";
    clase = CLASES.entregada;
  } else if (tarea.vencida || vencimientoDe(tarea)?.nivel === "vencida") {
    texto = "Vencida";
    clase = CLASES.vencida;
  } else if (tarea.estado === "generada") {
    texto = "Generada";
    clase = CLASES.generada;
  } else {
    texto = "Pendiente";
    clase = CLASES.pendiente;
  }
  return (
    <Badge variant="outline" className={cn("font-medium", clase)}>
      {texto}
    </Badge>
  );
}

const NIVELES: Record<NivelVencimiento, string> = {
  neutro: "border-border bg-muted text-muted-foreground",
  aviso: "border-warning/40 bg-warning/10 text-warning",
  urgente: "border-danger/40 bg-danger/10 text-danger",
  vencida: "border-danger/40 bg-danger/10 text-danger",
};

export function VencimientoBadge({
  tarea,
  ahora,
  omitirVencida = false,
}: {
  tarea: Estado;
  ahora?: Date;
  omitirVencida?: boolean;
}) {
  const v = vencimientoDe(tarea, ahora);
  if (!v || (omitirVencida && v.nivel === "vencida")) return null;
  return (
    <Badge variant="outline" className={cn("font-medium", NIVELES[v.nivel])}>
      {v.texto}
    </Badge>
  );
}
