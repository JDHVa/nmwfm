import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, FileDown, FileImage, GripVertical, ImagePlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, fileUrl } from "@/lib/api";
import { alPulsarEnlace } from "@/lib/opener";
import { cn } from "@/lib/utils";

const PdfPreview = lazy(() => import("@/views/tarea/PdfPreview"));

type Pagina = { id: string; file: File; url: string };

let seqPagina = 0;

export function ImagenesAPdf() {
  const [paginas, setPaginas] = useState<Pagina[]>([]);
  const [recortar, setRecortar] = useState(true);
  const [conPortada, setConPortada] = useState(false);
  const [portada, setPortada] = useState({ profesor: "", materia: "", titulo: "", fecha: "" });
  const [arrastrando, setArrastrando] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const crear = useMutation({
    mutationFn: () =>
      api.herramientaPdf(
        paginas.map((p) => p.file),
        recortar,
        conPortada
          ? {
              profesor: portada.profesor.trim(),
              ...(portada.materia.trim() ? { materia: portada.materia.trim() } : {}),
              ...(portada.titulo.trim() ? { titulo: portada.titulo.trim() } : {}),
              ...(portada.fecha ? { fecha: portada.fecha } : {}),
            }
          : undefined,
      ),
  });

  const agregar = useCallback((lista: FileList | File[] | null | undefined) => {
    const imgs = Array.from(lista ?? []).filter((f) => f.type.startsWith("image/"));
    if (!imgs.length) return;
    setPaginas((a) => [
      ...a,
      ...imgs.map((file) => ({
        id: `pag-${++seqPagina}`,
        file,
        url: typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : "",
      })),
    ]);
  }, []);

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const imgs = Array.from(e.clipboardData?.files ?? []).filter((f) => f.type.startsWith("image/"));
      if (imgs.length) {
        e.preventDefault();
        agregar(imgs);
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [agregar]);

  const urlsRef = useRef<string[]>([]);
  useEffect(() => {
    urlsRef.current = paginas.map((p) => p.url);
  }, [paginas]);
  useEffect(() => () => urlsRef.current.forEach((u) => URL.revokeObjectURL?.(u)), []);

  function mover(desde: number, hacia: number) {
    if (hacia < 0 || hacia >= paginas.length) return;
    setPaginas((a) => arrayMove(a, desde, hacia));
  }

  function alSoltar(e: DragEndEvent) {
    if (!e.over || e.active.id === e.over.id) return;
    const desde = paginas.findIndex((p) => p.id === e.active.id);
    const hacia = paginas.findIndex((p) => p.id === e.over!.id);
    if (desde >= 0 && hacia >= 0) mover(desde, hacia);
  }

  const setP = (k: keyof typeof portada) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setPortada((f) => ({ ...f, [k]: e.target.value }));
  const bloqueado = paginas.length === 0 || (conPortada && !portada.profesor.trim()) || crear.isPending;

  return (
    <section aria-labelledby="herr-pdf" className="space-y-3 rounded-xl border bg-card p-5">
      <h2 id="herr-pdf" className="flex items-center gap-2 text-sm font-semibold">
        <FileImage className="size-4 text-primary" /> Imágenes a PDF
      </h2>
      <p className="text-xs text-muted-foreground">
        Cada imagen es una página, en el orden que elijas. Arrastra, pega con Ctrl+V o elige archivos.
      </p>
      <div
        data-testid="zona-herramienta-pdf"
        onDragOver={(e) => {
          e.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastrando(false);
          agregar(e.dataTransfer.files);
        }}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed p-6 text-center",
          arrastrando ? "border-primary bg-primary/10" : "border-border",
        )}
      >
        <ImagePlus className="size-6 text-primary" />
        <Button variant="secondary" size="sm" onClick={() => input.current?.click()}>
          Elegir imágenes
        </Button>
        <input
          ref={input}
          type="file"
          accept="image/*"
          multiple
          hidden
          data-testid="input-herramienta-pdf"
          onChange={(e) => {
            agregar(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {paginas.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={alSoltar}>
          <SortableContext items={paginas.map((p) => p.id)} strategy={rectSortingStrategy}>
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5" aria-label="Páginas del PDF">
              {paginas.map((p, i) => (
                <PaginaMiniatura
                  key={p.id}
                  pagina={p}
                  numero={i + 1}
                  total={paginas.length}
                  onQuitar={() => setPaginas((a) => a.filter((x) => x.id !== p.id))}
                  onMover={(delta) => mover(i, i + delta)}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-4 accent-primary"
          checked={recortar}
          onChange={(e) => setRecortar(e.target.checked)}
        />
        Recortar cada imagen a la página
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-4 accent-primary"
          checked={conPortada}
          onChange={(e) => setConPortada(e.target.checked)}
        />
        Agregar portada
      </label>
      {conPortada && (
        <div className="grid gap-3 rounded-lg border bg-muted p-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="pdf-portada-profesor">Profesor</Label>
            <Input id="pdf-portada-profesor" value={portada.profesor} onChange={setP("profesor")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pdf-portada-materia">Materia</Label>
            <Input id="pdf-portada-materia" value={portada.materia} onChange={setP("materia")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pdf-portada-titulo">Título</Label>
            <Input id="pdf-portada-titulo" value={portada.titulo} onChange={setP("titulo")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pdf-portada-fecha">Fecha</Label>
            <Input id="pdf-portada-fecha" type="date" value={portada.fecha} onChange={setP("fecha")} />
          </div>
        </div>
      )}
      <Button onClick={() => crear.mutate()} disabled={bloqueado}>
        {crear.isPending ? "Creando…" : "Crear PDF"}
      </Button>
      {crear.error && <p className="text-sm text-danger">{crear.error.message}</p>}
      {crear.data && (
        <div className="space-y-3">
          <a
            href={fileUrl(crear.data.pdf_url)}
            onClick={(e) => alPulsarEnlace(e, fileUrl(crear.data!.pdf_url))}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md border bg-secondary px-3 py-1.5 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
          >
            <FileDown className="size-4" /> Descargar PDF
          </a>
          <div className="w-fit overflow-hidden rounded-lg border bg-white shadow-card">
            <Suspense fallback={<p className="p-4 text-xs text-muted-foreground">Cargando vista previa…</p>}>
              <PdfPreview url={fileUrl(crear.data.pdf_url)} ancho={240} />
            </Suspense>
          </div>
        </div>
      )}
    </section>
  );
}

function PaginaMiniatura({
  pagina,
  numero,
  total,
  onQuitar,
  onMover,
}: {
  pagina: Pagina;
  numero: number;
  total: number;
  onQuitar: () => void;
  onMover: (delta: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: pagina.id,
  });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "relative flex flex-col overflow-hidden rounded-lg border bg-muted",
        isDragging && "z-10 opacity-80 ring-2 ring-primary",
      )}
    >
      <div className="flex items-center justify-between border-b bg-card px-1 py-0.5 text-[11px] text-muted-foreground">
        <button
          type="button"
          aria-label={`Reordenar página ${numero}`}
          className="flex cursor-grab items-center gap-0.5 rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="size-3" /> Pág. {numero}
        </button>
        <button
          type="button"
          aria-label={`Quitar ${pagina.file.name}`}
          onClick={onQuitar}
          className="rounded hover:text-danger"
        >
          <X className="size-3" />
        </button>
      </div>
      <div className="flex aspect-[3/4] items-center justify-center bg-background/40">
        {pagina.url && (
          <img src={pagina.url} alt={pagina.file.name} className="max-h-full max-w-full object-contain" />
        )}
      </div>
      <div className="flex justify-between border-t bg-card px-1 py-0.5">
        <button
          type="button"
          aria-label={`Mover página ${numero} antes`}
          disabled={numero === 1}
          onClick={() => onMover(-1)}
          className="rounded p-0.5 hover:bg-accent disabled:opacity-30"
        >
          <ChevronLeft className="size-3.5" />
        </button>
        <button
          type="button"
          aria-label={`Mover página ${numero} después`}
          disabled={numero === total}
          onClick={() => onMover(1)}
          className="rounded p-0.5 hover:bg-accent disabled:opacity-30"
        >
          <ChevronRight className="size-3.5" />
        </button>
      </div>
    </li>
  );
}
