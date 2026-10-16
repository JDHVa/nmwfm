import { lazy, Suspense } from "react";
import { useMutation } from "@tanstack/react-query";
import { FileDown, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PortadaCampos, datosDePortada, usePortadaForm } from "@/components/PortadaCampos";
import { api, fileUrl } from "@/lib/api";
import { ImagenesAPdf } from "@/views/ImagenesAPdf";
import { alPulsarEnlace } from "@/lib/opener";

const PdfPreview = lazy(() => import("@/views/tarea/PdfPreview"));

function Vista({ url }: { url: string }) {
  return (
    <div className="w-fit overflow-hidden rounded-lg border bg-white shadow-card">
      <Suspense fallback={<p className="p-4 text-xs text-muted-foreground">Cargando vista previa…</p>}>
        <PdfPreview url={fileUrl(url)} ancho={240} />
      </Suspense>
    </div>
  );
}

function Descarga({ url, etiqueta, icono }: { url: string; etiqueta: string; icono?: "pdf" | "docx" }) {
  const Icono = icono === "docx" ? FileText : FileDown;
  return (
    <a
      href={fileUrl(url)}
      onClick={(e) => alPulsarEnlace(e, fileUrl(url))}
      download
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 rounded-md border bg-secondary px-3 py-1.5 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
    >
      <Icono className="size-4" /> {etiqueta}
    </a>
  );
}

export function HerramientasPanel() {
  return (
    <div className="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
      <ImagenesAPdf />
      <PortadaRapida />
    </div>
  );
}

function PortadaRapida() {
  const { valores, cambiar } = usePortadaForm();
  const crear = useMutation({
    mutationFn: () => api.herramientaPortada({ ...datosDePortada(valores), profesor: valores.profesor.trim() }),
  });

  return (
    <section aria-labelledby="herr-portada" className="space-y-3 rounded-xl border bg-card p-5">
      <h2 id="herr-portada" className="flex items-center gap-2 text-sm font-semibold">
        <FileText className="size-4 text-primary" /> Portada rápida
      </h2>
      <p className="text-xs text-muted-foreground">
        Genera una portada con tu nombre y matrícula, sin necesidad de una tarea.
      </p>
      <PortadaCampos valores={valores} onCambio={cambiar} prefijo="portada" />
      <Button onClick={() => crear.mutate()} disabled={!valores.profesor.trim() || crear.isPending}>
        {crear.isPending ? "Creando…" : "Crear portada"}
      </Button>
      {crear.error && <p className="text-sm text-danger">{crear.error.message}</p>}
      {crear.data && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Descarga url={crear.data.pdf_url} etiqueta="Descargar PDF de la portada" />
            <Descarga url={crear.data.docx_url} etiqueta="Descargar Word de la portada" icono="docx" />
          </div>
          <Vista url={crear.data.pdf_url} />
        </div>
      )}
    </section>
  );
}
