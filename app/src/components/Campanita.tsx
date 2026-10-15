import { useState } from "react";
import { Bell, CheckCheck } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { useEscape } from "@/lib/atajos";
import { api, type Novedad } from "@/lib/api";
import { useNav } from "@/lib/app-context";
import { keys } from "@/lib/queries";
import { haceTiempo } from "@/lib/sync";
import { cn } from "@/lib/utils";

export function Campanita({ className }: { className?: string }) {
  const qc = useQueryClient();
  const { go } = useNav();
  const [abierto, setAbierto] = useState(false);
  const { data: novedades = [] } = useQuery({
    queryKey: keys.novedades,
    queryFn: api.novedades,
    refetchInterval: 5 * 60 * 1000,
  });
  const leer = useMutation({
    mutationFn: (ids?: string[]) => api.leerNovedades(ids),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.novedades }),
  });
  useEscape(abierto, () => setAbierto(false));
  const sinLeer = novedades.filter((n) => !n.leida);

  function abrir(n: Novedad) {
    if (!n.leida) leer.mutate([n.id]);
    setAbierto(false);
    go({ name: "tarea", materiaId: n.materia_id, id: n.tarea_id });
  }

  return (
    <div className={cn("relative", className)}>
      <button
        type="button"
        aria-label={sinLeer.length ? `Novedades: ${sinLeer.length} sin leer` : "Novedades"}
        aria-expanded={abierto}
        onClick={() => setAbierto((v) => !v)}
        className="relative flex size-8 items-center justify-center rounded-full border bg-card shadow-card outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Bell className="size-4" />
        {sinLeer.length > 0 && (
          <span className="absolute -right-1 -top-1 flex min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-4 text-white">
            {sinLeer.length}
          </span>
        )}
      </button>
      {abierto && (
        <div className="absolute right-0 top-full z-30 mt-2 w-96 rounded-xl border bg-popover p-2 shadow-pop">
          <div className="flex items-center justify-between px-2 py-1">
            <p className="text-sm font-semibold">Novedades</p>
            <Button
              size="sm"
              variant="ghost"
              disabled={sinLeer.length === 0}
              onClick={() => leer.mutate(undefined)}
            >
              <CheckCheck /> Marcar todas como leídas
            </Button>
          </div>
          {novedades.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">Sin novedades.</p>
          )}
          <ul className="max-h-80 overflow-y-auto">
            {novedades.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => abrir(n)}
                  className="flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm outline-none hover:bg-accent focus-visible:bg-accent"
                >
                  <span
                    aria-hidden
                    className={cn(
                      "mt-1.5 size-2 shrink-0 rounded-full",
                      n.leida ? "bg-transparent" : "bg-primary",
                    )}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{n.titulo}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {n.tipo === "nueva" ? "Tarea nueva" : "Tarea modificada"} · {n.materia_nombre} ·{" "}
                      {haceTiempo(n.detectada_en)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
