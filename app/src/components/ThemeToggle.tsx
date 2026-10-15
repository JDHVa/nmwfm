import { Monitor, Moon, Sun } from "lucide-react";
import { ETIQUETA_TEMA, ORDEN_TEMAS, useTheme, type Tema } from "@/lib/theme";
import { cn } from "@/lib/utils";

const ICONOS = { sistema: Monitor, claro: Sun, oscuro: Moon } as const;

export function siguienteTema(actual: Tema): Tema {
  return ORDEN_TEMAS[(ORDEN_TEMAS.indexOf(actual) + 1) % ORDEN_TEMAS.length];
}

export function ThemeToggle({ className }: { className?: string }) {
  const { tema, setTema } = useTheme();
  const Icono = ICONOS[tema];
  return (
    <button
      type="button"
      onClick={() => setTema(siguienteTema(tema))}
      aria-label={`Tema: ${ETIQUETA_TEMA[tema]}. Cambiar tema`}
      title={`Tema: ${ETIQUETA_TEMA[tema]}`}
      className={cn(
        "flex size-10 items-center justify-center rounded-full border bg-card text-foreground shadow-card outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <Icono className="size-5" />
    </button>
  );
}

export function ThemeSelector() {
  const { tema, setTema } = useTheme();
  return (
    <div role="radiogroup" aria-label="Tema" className="inline-flex rounded-lg border bg-muted p-1">
      {ORDEN_TEMAS.map((t) => {
        const Icono = ICONOS[t];
        const activo = t === tema;
        return (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={activo}
            onClick={() => setTema(t)}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring",
              activo ? "bg-card text-foreground shadow-card" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icono className="size-4" /> {ETIQUETA_TEMA[t]}
          </button>
        );
      })}
    </div>
  );
}
