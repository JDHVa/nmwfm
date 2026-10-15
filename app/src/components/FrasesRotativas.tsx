import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export function FrasesRotativas({
  frases,
  intervalo = 3200,
  className,
}: {
  frases: string[];
  intervalo?: number;
  className?: string;
}) {
  const [indice, setIndice] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndice((i) => (i + 1) % frases.length), intervalo);
    return () => clearInterval(id);
  }, [frases.length, intervalo]);

  return (
    <div className={cn("grid text-foreground", className)}>
      {frases.map((f, i) => (
        <span
          key={f}
          aria-hidden={i !== indice}
          className={cn(
            "col-start-1 row-start-1 transition-[opacity,transform,filter] duration-700 ease-out",
            i === indice ? "translate-y-0 opacity-100 blur-0" : "translate-y-3 opacity-0 blur-sm",
          )}
        >
          {f}
        </span>
      ))}
    </div>
  );
}
