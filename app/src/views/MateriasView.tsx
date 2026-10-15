import { BookOpen, CalendarRange, RefreshCw, UserRound } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import SpotlightCard from "@/components/SpotlightCard";
import { Button } from "@/components/ui/button";
import { JobProgress } from "@/components/JobProgress";
import { PageHeader } from "@/components/PageHeader";
import { api } from "@/lib/api";
import { useNav } from "@/lib/app-context";
import { useJobRunner, useMaterias } from "@/lib/queries";

function fechaCorta(iso: string | null): string {
  if (!iso) return "Sin sincronizar";
  return new Date(iso).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
}

export function MateriasView() {
  const { data: materias, isLoading, error } = useMaterias();
  const qc = useQueryClient();
  const { go } = useNav();
  const sync = useJobRunner(() => qc.invalidateQueries());

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-8">
      <PageHeader
        titulo="Materias"
        descripcion="Elige una materia para ver sus etapas y tareas."
        acciones={
          <Button onClick={() => sync.start(api.sync)} disabled={sync.running}>
            <RefreshCw className={sync.running ? "animate-spin" : ""} /> Sincronizar
          </Button>
        }
      />
      <JobProgress job={sync.job} error={sync.error} />

      {isLoading && <p className="text-muted-foreground">Cargando materias…</p>}
      {error && <p className="text-destructive">{error.message}</p>}
      {materias && materias.length === 0 && (
        <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
          Aún no hay materias. Pulsa «Sincronizar» para traerlas desde NEXUS.
        </div>
      )}

      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {materias?.map((m) => (
          <li key={m.id}>
            <SpotlightCard theme="dark" spotlightColor="#8b7bff" className="h-full !p-0">
              <button
                type="button"
                onClick={() => go({ name: "materia", id: m.id })}
                className="flex h-full w-full flex-col gap-4 rounded-[inherit] p-5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
                  <BookOpen className="size-5" />
                </span>
                <span className="text-base font-semibold leading-snug">{m.nombre}</span>
                <span className="mt-auto space-y-1.5 text-xs text-muted-foreground">
                  <span className="flex items-center gap-2">
                    <UserRound className="size-3.5 shrink-0" />
                    {m.profesor ?? "Profesor sin sincronizar"}
                  </span>
                  <span className="flex items-center gap-2">
                    <CalendarRange className="size-3.5 shrink-0" />
                    {m.periodo ?? "Periodo sin sincronizar"}
                  </span>
                  <span className="block pt-1 text-[11px] text-muted-foreground/70">
                    Sincronizada: {fechaCorta(m.sincronizada_en)}
                  </span>
                </span>
              </button>
            </SpotlightCard>
          </li>
        ))}
      </ul>
    </div>
  );
}
