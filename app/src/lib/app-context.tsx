import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useSettings } from "@/lib/queries";

export type View =
  | { name: "config" }
  | { name: "materias" }
  | { name: "materia"; id: string }
  | { name: "tarea"; materiaId: string; id: string };

type Nav = { view: View; go: (view: View) => void };

const NavContext = createContext<Nav | null>(null);

export function NavProvider({ initial, children }: { initial: View; children: ReactNode }) {
  const [view, setView] = useState<View>(initial);
  return <NavContext.Provider value={{ view, go: setView }}>{children}</NavContext.Provider>;
}

export function useNav(): Nav {
  const ctx = useContext(NavContext);
  if (!ctx) throw new Error("NavProvider ausente");
  return ctx;
}

function usePrefersReduced(): boolean {
  const [value, setValue] = useState(
    () =>
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setValue(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return value;
}

export function useReducedMotion(): boolean {
  const { data } = useSettings();
  const prefers = usePrefersReduced();
  return prefers || !!data?.reducir_animaciones;
}
