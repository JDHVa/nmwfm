import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useQueries } from "@tanstack/react-query";
import { TipoBadge } from "@/components/EstadoBadge";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useNav } from "@/lib/app-context";
import { buscarTareas, type ResultadoBusqueda } from "@/lib/filtros";
import { keys, useMaterias } from "@/lib/queries";
import { cn } from "@/lib/utils";

export function useTodasLasTareas(): ResultadoBusqueda[] {
  const { data: materias = [] } = useMaterias();
  const consultas = useQueries({
    queries: materias.map((m) => ({ queryKey: keys.etapas(m.id), queryFn: () => api.etapas(m.id) })),
  });
  return useMemo(
    () =>
      consultas.flatMap((c, i) =>
        (c.data ?? []).flatMap((e) => e.tareas.map((tarea) => ({ tarea, materia: materias[i].nombre }))),
      ),
    [consultas, materias],
  );
}

export function PaletaBusqueda({ abierto, onCerrar }: { abierto: boolean; onCerrar: () => void }) {
  const { go } = useNav();
  const todas = useTodasLasTareas();
  const [consulta, setConsulta] = useState("");
  const [activo, setActivo] = useState(0);
  const resultados = useMemo(() => buscarTareas(todas, consulta), [todas, consulta]);
  const indice = Math.min(activo, Math.max(0, resultados.length - 1));

  function abrir(r: ResultadoBusqueda | undefined) {
    if (!r) return;
    onCerrar();
    go({ name: "tarea", materiaId: r.tarea.materia_id, id: r.tarea.id });
  }

  return (
    <Dialog
      open={abierto}
      onOpenChange={(v) => {
        if (!v) {
          onCerrar();
          setConsulta("");
          setActivo(0);
        }
      }}
    >
      <DialogContent showCloseButton={false} className="top-[20%] translate-y-0 gap-0 p-0 sm:max-w-xl">
        <DialogTitle className="sr-only">Buscar tareas</DialogTitle>
        <DialogDescription className="sr-only">
          Busca por título, materia o número. Usa las flechas y Enter para abrir.
        </DialogDescription>
        <div className="flex items-center gap-3 border-b px-4">
          <Search className="size-4 text-muted-foreground" />
          <input
            autoFocus
            role="combobox"
            aria-expanded
            aria-controls="resultados-busqueda"
            aria-label="Buscar tareas"
            placeholder="Buscar por título, materia o número…"
            value={consulta}
            onChange={(e) => {
              setConsulta(e.target.value);
              setActivo(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActivo((i) => Math.min(i + 1, resultados.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActivo((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                abrir(resultados[indice]);
              }
            }}
            className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <ul id="resultados-busqueda" role="listbox" className="max-h-80 overflow-y-auto p-2">
          {resultados.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">Sin resultados.</li>
          )}
          {resultados.map((r, i) => (
            <li key={r.tarea.id} role="option" aria-selected={i === indice}>
              <button
                type="button"
                onMouseEnter={() => setActivo(i)}
                onClick={() => abrir(r)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm outline-none",
                  i === indice && "bg-accent",
                )}
              >
                <span className="w-10 shrink-0 font-semibold tabular-nums text-primary">
                  {r.tarea.numero}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{r.tarea.titulo}</span>
                  <span className="block truncate text-xs text-muted-foreground">{r.materia}</span>
                </span>
                <TipoBadge tarea={r.tarea} />
              </button>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
