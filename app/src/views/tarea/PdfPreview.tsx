import { Document, Page } from "react-pdf";
import "@/lib/pdfConfig";

export default function PdfPreview({ url, ancho = 220 }: { url: string; ancho?: number }) {
  return (
    <Document
      file={url}
      loading={<p className="p-4 text-xs text-muted-foreground">Cargando…</p>}
      error={<p className="p-4 text-xs text-danger">No se pudo abrir la portada.</p>}
    >
      <Page pageNumber={1} width={ancho} renderTextLayer={false} renderAnnotationLayer={false} />
    </Document>
  );
}
