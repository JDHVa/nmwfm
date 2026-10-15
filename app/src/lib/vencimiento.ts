import type { Tarea } from "@/lib/api";

export type NivelVencimiento = "neutro" | "aviso" | "urgente" | "vencida";
export type Vencimiento = { texto: string; nivel: NivelVencimiento };
export type GrupoProximas = "Hoy" | "Esta semana" | "Más adelante" | "Vencidas";

function inicioDeDia(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function diasHasta(hasta: string, ahora: Date): number {
  return Math.round((inicioDeDia(new Date(hasta)) - inicioDeDia(ahora)) / 86_400_000);
}

export function vencimientoDe(
  t: Pick<Tarea, "hasta" | "estado" | "vencida">,
  ahora: Date = new Date(),
): Vencimiento | null {
  if (t.estado === "entregada" || !t.hasta) return null;
  const fin = new Date(t.hasta);
  if (Number.isNaN(fin.getTime())) return null;
  if (fin.getTime() < ahora.getTime()) return { texto: "Vencida", nivel: "vencida" };
  const dias = diasHasta(t.hasta, ahora);
  if (dias <= 0) return { texto: "Vence hoy", nivel: "urgente" };
  if (dias === 1) return { texto: "Vence mañana", nivel: "aviso" };
  if (dias <= 3) return { texto: `Vence en ${dias} días`, nivel: "aviso" };
  return { texto: `Vence en ${dias} días`, nivel: "neutro" };
}

export function grupoDe(
  t: Pick<Tarea, "hasta" | "estado" | "vencida">,
  ahora: Date = new Date(),
): GrupoProximas {
  const v = vencimientoDe(t, ahora);
  if (v?.nivel === "vencida") return "Vencidas";
  if (!t.hasta) return "Más adelante";
  const dias = diasHasta(t.hasta, ahora);
  if (dias <= 0) return "Hoy";
  if (dias <= 7) return "Esta semana";
  return "Más adelante";
}

export const ORDEN_GRUPOS: GrupoProximas[] = ["Hoy", "Esta semana", "Más adelante", "Vencidas"];

export function fechaCorta(iso: string): string {
  return new Date(iso).toLocaleDateString("es-MX", { day: "numeric", month: "short" }).replace(".", "");
}
