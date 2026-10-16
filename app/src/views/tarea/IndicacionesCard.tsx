import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NotebookPen, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, type TareaDetalle } from "@/lib/api";
import { keys } from "@/lib/queries";

export function IndicacionesCard({ tarea }: { tarea: TareaDetalle }) {
  return <Editor tarea={tarea} />;
}

function Editor({ tarea }: { tarea: TareaDetalle }) {
  const qc = useQueryClient();
  const guardado = tarea.indicaciones ?? "";
  const [edicion, setEdicion] = useState<string | null>(null);
  const texto = edicion ?? guardado;
  const [ok, setOk] = useState(false);
  const guardar = useMutation({
    mutationFn: () => api.indicaciones(tarea.id, texto.trim()),
    onSuccess: (t) => {
      qc.setQueryData(keys.tarea(tarea.id), t);
      setEdicion(null);
      setOk(true);
    },
  });
  const cambiado = edicion !== null && edicion.trim() !== guardado.trim();

  return (
    <section className="space-y-2 rounded-xl border bg-card p-4">
      <h3 className="flex items-center gap-2 text-sm font-medium">
        <NotebookPen className="size-4 text-primary" /> Indicaciones del profesor
      </h3>
      <p className="text-xs text-muted-foreground">
        Lo que el profesor dijo en clase o en el pizarrón (por ejemplo «es en equipo de 3» o «máximo 2
        páginas»). Tienen prioridad sobre la descripción de NEXUS al generar la tarea.
      </p>
      <Textarea
        aria-label="Indicaciones del profesor"
        rows={3}
        value={texto}
        placeholder="Escribe aquí las indicaciones extra…"
        onChange={(e) => {
          setEdicion(e.target.value);
          setOk(false);
        }}
      />
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant="secondary"
          disabled={!cambiado || guardar.isPending}
          onClick={() => guardar.mutate()}
        >
          <Save /> Guardar indicaciones
        </Button>
        {ok && !cambiado && <span className="text-xs text-success">Guardadas</span>}
        {guardar.error && <span className="text-xs text-danger">{guardar.error.message}</span>}
      </div>
    </section>
  );
}
