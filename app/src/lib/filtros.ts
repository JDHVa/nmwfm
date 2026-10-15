import type { Tarea } from "@/lib/api";

export type Filtros = {
  tipo: "todos" | Tarea["tipo"];
  estado: "todos" | "pendiente" | "generada" | "entregada" | "vencida";
  desde: string;
  hasta: string;
};

export const FILTROS_VACIOS: Filtros = { tipo: "todos", estado: "todos", desde: "", hasta: "" };

export function hayFiltros(f: Filtros): boolean {
  return f.tipo !== "todos" || f.estado !== "todos" || !!f.desde || !!f.hasta;
}

function dia(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function cumpleFiltros(t: Tarea, f: Filtros): boolean {
  if (f.tipo !== "todos" && t.tipo !== f.tipo) return false;
  if (f.estado === "vencida") {
    if (!(t.vencida && t.estado !== "entregada")) return false;
  } else if (f.estado !== "todos" && t.estado !== f.estado) return false;
  if (f.desde || f.hasta) {
    if (!t.hasta) return false;
    const d = dia(t.hasta);
    if (f.desde && d < f.desde) return false;
    if (f.hasta && d > f.hasta) return false;
  }
  return true;
}

export function normalizar(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export type ResultadoBusqueda = { tarea: Tarea; materia: string };

export function buscarTareas(items: ResultadoBusqueda[], consulta: string, limite = 30): ResultadoBusqueda[] {
  const q = normalizar(consulta.trim());
  if (!q) return items.slice(0, limite);
  const palabras = q.split(/\s+/);
  return items
    .filter(({ tarea, materia }) => {
      const pajar = normalizar(`${tarea.numero} ${tarea.titulo} ${materia}`);
      return palabras.every((p) => pajar.includes(p));
    })
    .slice(0, limite);
}
