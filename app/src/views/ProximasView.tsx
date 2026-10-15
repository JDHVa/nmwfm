import { CalendarClock, ChevronRight, ClipboardCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { EstadoBadge, TipoBadge, VencimientoBadge } from "@/components/EstadoBadge";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { api, type TareaProxima } from "@/lib/api";
import { useNav } from "@/lib/app-context";
import { keys } from "@/lib/queries";
import { useSync } from "@/lib/sync";
import { ORDEN_GRUPOS, grupoDe, type GrupoProximas } from "@/lib/vencimiento";

export function ProximasView() {
  const { go } = useNav();
  const sync = useSync();
  const { data, isLoading, error } = useQuery({ queryKey: keys.proximas, queryFn: api.proximas });

  const grupos = new Map<GrupoProximas, TareaProxima[]>();
  data?.forEach((t) => {
    const g = grupoDe(t);
    grupos.set(g, [...(grupos.get(g) ?? []), t]);
  });

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-8">
      <PageHeader
        titulo="Próximas entregas"
        descripcion="Tus tareas pendientes, ordenadas por fecha límite."
        acciones={
          <Button variant="secondary" onClick={() => sync.revisar()} disabled={sync.running}>
            <ClipboardCheck /> Revisar tareas entregadas
          </Button>
        }
      />
      {isLoading && <p className="text-muted-foreground">Cargando tareas…</p>}
      {error && <p className="text-destructive">{error.message}</p>}
      {data && data.length === 0 && (
        <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
          No tienes tareas pendientes.
        </div>
      )}
      {ORDEN_GRUPOS.filter((g) => grupos.has(g)).map((g) => (
        <section key={g} aria-labelledby={`grupo-${g}`} className="space-y-2">
          <h2
            id={`grupo-${g}`}
            className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground"
          >
            <CalendarClock className="size-4" /> {g}
            <span className="tabular-nums">({grupos.get(g)!.length})</span>
          </h2>
          <ul className="divide-y rounded-xl border bg-card shadow-card">
            {grupos.get(g)!.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => go({ name: "tarea", materiaId: t.materia_id, id: t.id })}
                  className="flex w-full items-center gap-4 px-4 py-3 text-left outline-none transition-colors hover:bg-accent/40 focus-visible:bg-accent/40"
                >
                  <span className="w-10 shrink-0 text-sm font-semibold tabular-nums text-primary">
                    {t.numero}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{t.titulo}</span>
                    <span className="block truncate text-xs text-muted-foreground">{t.materia_nombre}</span>
                  </span>
                  {t.puntos !== null && (
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      {t.puntos} pts
                    </span>
                  )}
                  <TipoBadge tarea={t} />
                  <VencimientoBadge tarea={t} />
                  {t.estado === "generada" && <EstadoBadge tarea={t} />}
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
