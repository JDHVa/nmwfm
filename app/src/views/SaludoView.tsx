import { useEffect, useRef } from "react";
import BlurText from "@/components/BlurText";
import { Logo } from "@/components/Logo";
import { useReducedMotion } from "@/lib/app-context";

export const DURACION_SALUDO = 1200;

export function SaludoView({ nombre, onTerminar }: { nombre: string; onTerminar: () => void }) {
  const reducido = useReducedMotion();
  const fin = useRef(onTerminar);
  useEffect(() => {
    fin.current = onTerminar;
  });
  useEffect(() => {
    const t = setTimeout(() => fin.current(), DURACION_SALUDO);
    return () => clearTimeout(t);
  }, []);

  const primero = nombre.trim().split(/\s+/)[0] ?? "";
  const texto = primero ? `Hola, ${primero}` : "Hola";

  return (
    <button
      type="button"
      onClick={onTerminar}
      aria-label={`${texto}. Pulsa para continuar`}
      className="flex h-full w-full cursor-pointer flex-col items-center justify-center gap-6 outline-none"
    >
      <Logo className="size-16" />
      {reducido ? (
        <span className="text-4xl font-semibold tracking-tight">{texto}</span>
      ) : (
        <BlurText
          text={texto}
          animateBy="letters"
          delay={60}
          className="justify-center text-4xl font-semibold tracking-tight"
        />
      )}
    </button>
  );
}
