import { lazy, Suspense } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileCog, FileText, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, fileUrl } from "@/lib/api";
import { keys, useGeneracion } from "@/lib/queries";

const PdfViewer = lazy(() => import("./PdfViewer"));

export function RevisarStep({
  tareaId,
  onRegenerar,
  onContinuar,
}: {
  tareaId: string;
  onRegenerar: () => void;
  onContinuar: () => void;
}) {
  const qc = useQueryClient();
  const { data: gen, isLoading } = useGeneracion(tareaId);
  const abrir = useMutation({ mutationFn: () => api.abrirDocx(tareaId) });
  const reconstruir = useMutation({
    mutationFn: () => api.reconstruirPdf(tareaId),
    onSuccess: (g) => qc.setQueryData(keys.generacion(tareaId), g),
  });

  if (isLoading) return <p className="text-muted-foreground">Cargando documento…</p>;

  if (!gen) {
    return (
      <div className="space-y-4 rounded-xl border border-dashed p-10 text-center">
        <p className="text-muted-foreground">Todavía no hay un documento generado para esta tarea.</p>
        <Button onClick={onRegenerar}>
          <ArrowLeft /> Ir a generar
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={() => abrir.mutate()} disabled={abrir.isPending}>
          <FileText /> Abrir en Word
        </Button>
        <Button variant="secondary" onClick={() => reconstruir.mutate()} disabled={reconstruir.isPending}>
          <FileCog /> {reconstruir.isPending ? "Reconstruyendo…" : "Reconstruir PDF"}
        </Button>
        <Button variant="outline" onClick={onRegenerar}>
          <RotateCcw /> Regenerar
        </Button>
        <span className="ml-auto text-xs text-muted-foreground">
          Generado:{" "}
          {new Date(gen.creada_en).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })}
        </span>
      </div>
      {(abrir.error || reconstruir.error) && (
        <p className="text-sm text-destructive">{(abrir.error ?? reconstruir.error)?.message}</p>
      )}
      <p className="text-xs text-muted-foreground">
        Si editas el Word, guárdalo y pulsa «Reconstruir PDF» para actualizar la vista previa.
      </p>
      <Suspense fallback={<p className="text-muted-foreground">Cargando visor…</p>}>
        <PdfViewer key={gen.creada_en} url={fileUrl(gen.pdf_url)} />
      </Suspense>
      <div className="flex justify-end">
        <Button onClick={onContinuar}>Continuar a entregar</Button>
      </div>
    </div>
  );
}
