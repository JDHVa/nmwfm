import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type Tema = "sistema" | "claro" | "oscuro";
export type TemaResuelto = "claro" | "oscuro";

const CLAVE = "nmwfm.tema";
const CONSULTA = "(prefers-color-scheme: dark)";

function sistemaOscuro(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(CONSULTA).matches
    : false;
}

export function leerTema(): Tema {
  try {
    const v = localStorage.getItem(CLAVE);
    if (v === "claro" || v === "oscuro" || v === "sistema") return v;
  } catch {
    return "sistema";
  }
  return "sistema";
}

function guardarTema(tema: Tema) {
  try {
    localStorage.setItem(CLAVE, tema);
  } catch {
    return;
  }
}

function aplicar(resuelto: TemaResuelto, animar: boolean) {
  const el = document.documentElement;
  if (animar) {
    el.classList.add("theme-anim");
    setTimeout(() => el.classList.remove("theme-anim"), 450);
  }
  el.dataset.theme = resuelto === "oscuro" ? "dark" : "light";
  el.style.colorScheme = resuelto === "oscuro" ? "dark" : "light";
}

type Ctx = { tema: Tema; resuelto: TemaResuelto; setTema: (t: Tema) => void };

const ThemeContext = createContext<Ctx>({ tema: "sistema", resuelto: "claro", setTema: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [tema, setTemaState] = useState<Tema>(leerTema);
  const [sistema, setSistema] = useState<boolean>(sistemaOscuro);
  const primera = useRef(true);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(CONSULTA);
    const on = () => setSistema(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const resuelto: TemaResuelto = tema === "sistema" ? (sistema ? "oscuro" : "claro") : tema;

  useLayoutEffect(() => {
    aplicar(resuelto, !primera.current);
    primera.current = false;
  }, [resuelto]);

  const setTema = useCallback((t: Tema) => {
    guardarTema(t);
    setTemaState(t);
  }, []);

  const value = useMemo(() => ({ tema, resuelto, setTema }), [tema, resuelto, setTema]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Ctx {
  return useContext(ThemeContext);
}

export const ORDEN_TEMAS: Tema[] = ["sistema", "claro", "oscuro"];
export const ETIQUETA_TEMA: Record<Tema, string> = { sistema: "Sistema", claro: "Claro", oscuro: "Oscuro" };
