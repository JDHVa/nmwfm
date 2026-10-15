import { useState } from "react";
import { BookOpen, CalendarRange, ChevronDown, RefreshCw, UserRound } from "lucide-react";
import SpotlightCard from "@/components/SpotlightCard";
import { Button } from "@/components/ui/button";
import { JobProgress } from "@/components/JobProgress";
import { PageHeader } from "@/components/PageHeader";
import { token } from "@/lib/tokens";
import { useEscape } from "@/lib/atajos";
import { useNav } from "@/lib/app-context";
import { useMaterias } from "@/lib/queries";
import { useSync } from "@/lib/sync";
import { useTheme } from "@/lib/theme";

function fechaCorta(iso: string | null): string {
  if (!iso) return "Sin sincronizar";
  return new Date(iso).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
}

export function MateriasView() {
  const { data: materias, isLoading, error } = useMaterias();
  const { go } = useNav();
  const sync = useSync();
  const { resuelto } = useTheme();
  const [menu, setMenu] = useState(false);
  useEscape(menu, () => setMenu(false));

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-8">
      <PageHeader
        titulo="Materias"
        descripcion="Elige una materia para ver sus etapas y tareas."
        acciones={
          <div className="relative flex">
            <Button
              className="rounded-r-none"
              onClick={() => sync.iniciar("incremental")}
              disabled={sync.running}
            >
              <RefreshCw className={sync.running ? "animate-spin" : ""} /> Sincronizar
            </Button>
            <Button
              className="rounded-l-none border-l border-primary-foreground/30 px-2"
              aria-label="Más opciones de sincronización"
              aria-expanded={menu}
              disabled={sync.running}
              onClick={() => setMenu((v) => !v)}
            >
              <ChevronDown />
            </Button>
            {menu && (
              <div className="absolute right-0 top-full z-20 mt-2 w-56 rounded-xl border bg-popover p-1 shadow-pop">
                <button
                  type="button"
                  className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => {
                    setMenu(false);
                    sync.iniciar("completo");
                  }}
                >
                  Sincronizar todo de nuevo
                </button>
                <button
                  type="button"
                  className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => {
                    setMenu(false);
                    sync.revisar();
                  }}
                >
                  Revisar tareas entregadas
                </button>
              </div>
            )}
          </div>
        }
      />
      {sync.running && !sync.esRevision && <JobProgress job={sync.job} error={sync.error} />}

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
            <SpotlightCard
              theme={resuelto === "oscuro" ? "dark" : "light"}
              spotlightColor={token("--primary")}
              className="h-full !p-0"
            >
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
