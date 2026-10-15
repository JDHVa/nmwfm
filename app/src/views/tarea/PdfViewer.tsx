import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export default function PdfViewer({ url }: { url: string }) {
  const [paginas, setPaginas] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [ancho, setAncho] = useState(640);
  const [fallo, setFallo] = useState<string | null>(null);
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setAncho(Math.max(280, el.clientWidth - 32)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2 text-sm">
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="size-8"
            aria-label="Página anterior"
            disabled={pagina <= 1}
            onClick={() => setPagina((p) => p - 1)}
          >
            <ChevronLeft />
          </Button>
          <span className="min-w-20 text-center tabular-nums text-muted-foreground">
            {paginas ? `${pagina} / ${paginas}` : "—"}
          </span>
          <Button
            size="icon"
            variant="ghost"
            className="size-8"
            aria-label="Página siguiente"
            disabled={pagina >= paginas}
            onClick={() => setPagina((p) => p + 1)}
          >
            <ChevronRight />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="size-8"
            aria-label="Alejar"
            disabled={zoom <= 0.5}
            onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
          >
            <Minus />
          </Button>
          <span className="w-12 text-center tabular-nums text-muted-foreground">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            size="icon"
            variant="ghost"
            className="size-8"
            aria-label="Acercar"
            disabled={zoom >= 2}
            onClick={() => setZoom((z) => Math.min(2, z + 0.25))}
          >
            <Plus />
          </Button>
        </div>
      </div>
      <div ref={caja} className="flex max-h-[70vh] min-h-64 justify-center overflow-auto bg-muted p-4">
        {fallo ? (
          <p className="self-center text-sm text-destructive">{fallo}</p>
        ) : (
          <Document
            file={url}
            loading={<p className="self-center text-sm text-muted-foreground">Cargando PDF…</p>}
            error={<p className="self-center text-sm text-destructive">No se pudo abrir el PDF.</p>}
            onLoadSuccess={(d) => setPaginas(d.numPages)}
            onLoadError={(e) => setFallo(e.message)}
          >
            <Page
              pageNumber={pagina}
              width={ancho * zoom}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              className="shadow-2xl"
            />
          </Document>
        )}
      </div>
    </div>
  );
}
