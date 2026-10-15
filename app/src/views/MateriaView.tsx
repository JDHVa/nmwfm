import { ArrowLeft, ChevronRight } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { useState } from "react";
import { CalificacionesTab } from "@/views/CalificacionesTab";
import { FiltrosTareas } from "@/components/FiltrosTareas";
import { Button } from "@/components/ui/button";
import { EstadoBadge, TipoBadge, VencimientoBadge } from "@/components/EstadoBadge";
import { PageHeader } from "@/components/PageHeader";
import type { EtapaConTareas, Tarea } from "@/lib/api";
import { useNav } from "@/lib/app-context";
import { fechaRango } from "@/lib/format";
import { FILTROS_VACIOS, cumpleFiltros, hayFiltros, type Filtros } from "@/lib/filtros";
import { useEtapas, useMaterias } from "@/lib/queries";

export function MateriaView({ id }: { id: string }) {
  const { data: materias } = useMaterias();
  const { data: etapas, isLoading, error } = useEtapas(id);
  const { go } = useNav();
  const materia = materias?.find((m) => m.id === id);
  const [pestana, setPestana] = useState<"tareas" | "calificaciones">("tareas");
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_VACIOS);
  const filtrando = hayFiltros(filtros);
  const visibles = etapas
    ?.map((e) => ({ ...e, tareas: e.tareas.filter((t) => cumpleFiltros(t, filtros)) }))
    .filter((e) => !filtrando || e.tareas.length > 0);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-8">
      <PageHeader
        atras={
          <Button variant="ghost" size="sm" className="-ml-2" onClick={() => go({ name: "materias" })}>
            <ArrowLeft /> Materias
          </Button>
        }
        titulo={materia?.nombre ?? "Materia"}
        descripcion={materia ? [materia.profesor, materia.periodo].filter(Boolean).join(" · ") : undefined}
      />
      <div
        role="tablist"
        aria-label="Vista de la materia"
        className="inline-flex rounded-lg border bg-muted p-1"
      >
        {(["tareas", "calificaciones"] as const).map((p) => (
          <button
            key={p}
            type="button"
            role="tab"
            aria-selected={pestana === p}
            onClick={() => setPestana(p)}
            className={
              "rounded-md px-4 py-1.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring " +
              (pestana === p
                ? "bg-card text-foreground shadow-card"
                : "text-muted-foreground hover:text-foreground")
            }
          >
            {p === "tareas" ? "Tareas" : "Calificaciones"}
          </button>
        ))}
      </div>
      {pestana === "calificaciones" && <CalificacionesTab materiaId={id} />}
      {pestana === "tareas" && isLoading && <p className="text-muted-foreground">Cargando etapas…</p>}
      {pestana === "tareas" && error && <p className="text-destructive">{error.message}</p>}
      {pestana === "tareas" && etapas && <FiltrosTareas valor={filtros} onChange={setFiltros} />}
      {pestana === "tareas" && visibles && filtrando && visibles.length === 0 && (
        <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          Ninguna tarea coincide con los filtros.
        </p>
      )}
      {pestana === "tareas" && visibles && (
        <Accordion
          key={filtrando ? "filtrado" : "normal"}
          type="multiple"
          defaultValue={filtrando ? visibles.map((e) => e.id) : visibles.slice(0, 1).map((e) => e.id)}
          className="space-y-3"
        >
          {visibles.map((e) => (
            <EtapaItem key={e.id} etapa={e} onOpen={(t) => go({ name: "tarea", materiaId: id, id: t.id })} />
          ))}
        </Accordion>
      )}
    </div>
  );
}

function EtapaItem({ etapa, onOpen }: { etapa: EtapaConTareas; onOpen: (t: Tarea) => void }) {
  const entregadas = etapa.tareas.filter((t) => t.estado === "entregada").length;
  return (
    <AccordionItem value={etapa.id} className="rounded-xl border bg-card px-5 last:border-b">
      <AccordionTrigger className="hover:no-underline">
        <span className="flex flex-col items-start gap-1 text-left">
          <span className="text-base font-semibold">{etapa.nombre}</span>
          <span className="text-xs font-normal text-muted-foreground">
            {entregadas} de {etapa.tareas.length} entregadas
          </span>
        </span>
      </AccordionTrigger>
      <AccordionContent>
        {etapa.descripcion && <p className="mb-4 text-sm text-muted-foreground">{etapa.descripcion}</p>}
        <ul className="divide-y rounded-lg border">
          {etapa.tareas.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => onOpen(t)}
                className="flex w-full items-center gap-4 px-4 py-3 text-left outline-none transition-colors hover:bg-accent/40 focus-visible:bg-accent/40"
              >
                <span className="w-10 shrink-0 text-sm font-semibold tabular-nums text-primary">
                  {t.numero}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{t.titulo}</span>
                  <span className="block text-xs text-muted-foreground">
                    {fechaRango(t.desde, t.hasta)}
                    {t.modalidad ? ` · ${t.modalidad}` : ""}
                  </span>
                </span>
                {t.puntos !== null && (
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{t.puntos} pts</span>
                )}
                <TipoBadge tarea={t} />
                <VencimientoBadge tarea={t} omitirVencida />
                {(t.tipo !== "examen" || t.estado === "entregada" || t.vencida) && <EstadoBadge tarea={t} />}
                <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
              </button>
            </li>
          ))}
        </ul>
      </AccordionContent>
    </AccordionItem>
  );
}
