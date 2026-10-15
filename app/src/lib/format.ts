const fmt = new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short", year: "numeric" });

export function fecha(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : fmt.format(d);
}

export function fechaRango(desde: string | null, hasta: string | null): string {
  const a = fecha(desde);
  const b = fecha(hasta);
  if (a && b) return `${a} → ${b}`;
  if (b) return `Hasta ${b}`;
  if (a) return `Desde ${a}`;
  return "Sin fechas";
}
