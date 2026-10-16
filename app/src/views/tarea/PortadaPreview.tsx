import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, fileUrl } from "@/lib/api";

const PdfPreview = lazy(() => import("./PdfPreview"));

export function PortadaPreview({ tareaId }: { tareaId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["portada", tareaId],
    queryFn: () => api.portadaPreview(tareaId),
    retry: false,
  });

  return (
    <section
      aria-labelledby="titulo-portada"
      className="grid gap-4 rounded-xl border bg-card p-4 md:grid-cols-[1fr_240px]"
    >
      <div className="space-y-2">
        <h3 id="titulo-portada" className="text-sm font-medium">
          Portada del documento
        </h3>
        <p className="text-xs text-muted-foreground">
          Así se verá la primera hoja, con tu nombre, tu matrícula, el profesor de la materia y la fecha de
          hoy.
        </p>
        {error && <p className="text-xs text-danger">No se pudo generar la vista previa: {error.message}</p>}
      </div>
      <div className="overflow-hidden rounded-lg border bg-white shadow-card">
        {data ? (
          <Suspense fallback={<p className="p-4 text-xs text-muted-foreground">Cargando…</p>}>
            <PdfPreview url={fileUrl(data.pdf_url)} />
          </Suspense>
        ) : (
          <div className="flex aspect-[3/4] items-center justify-center text-xs text-muted-foreground">
            {isLoading ? "Cargando…" : "Sin vista previa"}
          </div>
        )}
      </div>
    </section>
  );
}
