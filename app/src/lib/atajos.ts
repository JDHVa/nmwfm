import { useEffect, useRef } from "react";

export function estaEscribiendo(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el || !el.tagName) return false;
  return (
    el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable
  );
}

export const EVENTO_GENERAR = "nmwfm:generar";

export const ATAJOS: { teclas: string; descripcion: string }[] = [
  { teclas: "Ctrl + K", descripcion: "Buscar tareas" },
  { teclas: "Ctrl + V", descripcion: "Pegar una imagen como insumo (en cualquier paso de una tarea)" },
  { teclas: "G", descripcion: "En una tarea: ir a Generar; una vez ahí, generar" },
  { teclas: "Esc", descripcion: "Cerrar paneles, menús y diálogos" },
  { teclas: "?", descripcion: "Mostrar esta ayuda" },
];

export function useEscape(activo: boolean, cerrar: () => void) {
  const cb = useRef(cerrar);
  useEffect(() => {
    cb.current = cerrar;
  });
  useEffect(() => {
    if (!activo) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") cb.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activo]);
}
