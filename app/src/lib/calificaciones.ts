import type {
  ClaveHistorial,
  Escenario,
  EstadoMateria,
  MateriaCalificacion,
  PresetEscenario,
  TipoAlerta,
  TipoMateria,
} from "@/lib/api";

export const APROBATORIA = 70;

export const ETIQUETA_ESTADO: Record<EstadoMateria, string> = {
  bien: "Vas bien",
  atento: "Atento",
  riesgo: "En riesgo",
  sin_datos: "Sin datos",
};

export const ETIQUETA_TIPO: Record<TipoMateria, string> = {
  bachillerato: "Bachillerato",
  carrera: "Carrera",
  portafolio: "Solo portafolio",
};

const ORDEN_ESTADO: Record<EstadoMateria, number> = { riesgo: 0, atento: 1, bien: 2, sin_datos: 3 };

export type OrdenCalificaciones = "riesgo" | "nombre" | "proyectada";

export function ordenarMaterias(
  materias: MateriaCalificacion[],
  orden: OrdenCalificaciones,
): MateriaCalificacion[] {
  const copia = [...materias];
  if (orden === "nombre") return copia.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  if (orden === "proyectada") return copia.sort((a, b) => a.proyectada - b.proyectada);
  return copia.sort(
    (a, b) => ORDEN_ESTADO[a.estado] - ORDEN_ESTADO[b.estado] || a.proyectada - b.proyectada,
  );
}

export function finalSimulada(m: MateriaCalificacion, valores: Record<number, number>): number {
  const extra = m.pendientes.reduce((suma, p, i) => suma + ((valores[i] ?? 0) * p.peso) / 100, 0);
  return Math.round((m.asegurados + extra) * 100) / 100;
}

export function porcentaje(p: number | null): string {
  if (p === null) return "—";
  if (p > 0 && p < 0.005) return "<1 %";
  return `${Math.round(p * 100)} %`;
}

export function nota(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function segmentosBarra(m: MateriaCalificacion): {
  asegurado: number;
  pendiente: number;
  perdido: number;
} {
  const asegurado = Math.min(100, Math.max(0, m.asegurados));
  const pendiente = Math.min(100 - asegurado, Math.max(0, m.maximo_posible - m.asegurados));
  return { asegurado, pendiente, perdido: Math.max(0, 100 - asegurado - pendiente) };
}

export const ETIQUETA_ALERTA: Record<TipoAlerta, string> = {
  bajo_historico: "Por debajo de tu histórico",
  examen_bajo: "Examen bajo",
  puntos_perdidos: "Puntos perdidos",
};

export const ETIQUETA_PRESET: Record<PresetEscenario, string> = {
  pesimista: "Pesimista",
  realista: "Realista",
  optimista: "Optimista",
  mio: "Mío",
  personalizado: "Personalizado",
};

export const ETIQUETA_HISTORIAL: Record<ClaveHistorial, string> = {
  par1: "Parcial 1",
  par2: "Parcial 2",
  emt: "Medio término",
  eg: "Examen global",
  portafolio: "Portafolio",
  total: "Total",
};

export function textoAlertas(m: MateriaCalificacion): string {
  return m.alertas.map((a) => `${ETIQUETA_ALERTA[a.tipo]}: ${a.detalle}`).join(" · ");
}

export function puntosDeMaximo(pts: number, max: number): string {
  return max === 0 ? "—" : `${nota(pts)} / ${nota(max)}`;
}

export function promedio(valores: number[]): number | null {
  return valores.length === 0 ? null : Math.round((valores.reduce((s, v) => s + v, 0) / valores.length) * 100) / 100;
}

export const ESCENARIO_INICIAL: Escenario = { preset: "mio" };
