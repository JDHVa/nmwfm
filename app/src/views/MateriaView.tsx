import { ArrowLeft, ChevronRight } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { EstadoBadge } from "@/components/EstadoBadge";
import { PageHeader } from "@/components/PageHeader";
import type { EtapaConTareas, Tarea } from "@/lib/api";
import { useNav } from "@/lib/app-context";
import { fechaRango } from "@/lib/format";
import { useEtapas, useMaterias } from "@/lib/queries";

export function MateriaView({ id }: { id: string }) {
  const { data: materias } = useMaterias();
  const { data: etapas, isLoading, error } = useEtapas(id);
  const { go } = useNav();
  const materia = materias?.find((m) => m.id === id);

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
      {isLoading && <p className="text-muted-foreground">Cargando etapas…</p>}
      {error && <p className="text-destructive">{error.message}</p>}
      {etapas && (
        <Accordion type="multiple" defaultValue={etapas.slice(0, 1).map((e) => e.id)} className="space-y-3">
          {etapas.map((e) => (
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
                <EstadoBadge estado={t.estado} />
                <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
              </button>
            </li>
          ))}
        </ul>
      </AccordionContent>
    </AccordionItem>
  );
}
