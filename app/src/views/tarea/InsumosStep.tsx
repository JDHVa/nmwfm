import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import {
  Columns2,
  Crop,
  FileText,
  GripVertical,
  ImagePlus,
  RotateCw,
  Trash2,
  Type,
  UploadCloud,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, fileUrl, type Insumo } from "@/lib/api";
import { keys, useInsumos, usePatchInsumo } from "@/lib/queries";
import { cn } from "@/lib/utils";

export function InsumosStep({ tareaId, onContinuar }: { tareaId: string; onContinuar: () => void }) {
  const qc = useQueryClient();
  const { data: insumos = [] } = useInsumos(tareaId);
  const patch = usePatchInsumo(tareaId);
  const [arrastrando, setArrastrando] = useState(false);
  const [texto, setTexto] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const subir = useMutation({
    mutationFn: (files: File[]) => api.subirImagenes(tareaId, files),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.insumos(tareaId) }),
  });
  const agregarTexto = useMutation({
    mutationFn: (t: string) => api.agregarTexto(tareaId, t),
    onSuccess: () => {
      setTexto("");
      qc.invalidateQueries({ queryKey: keys.insumos(tareaId) });
    },
  });
  const borrar = useMutation({
    mutationFn: (id: string) => api.borrarInsumo(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.insumos(tareaId) }),
  });

  const { mutate: subirArchivos } = subir;
  const recibir = useCallback(
    (files: FileList | File[] | null | undefined) => {
      const imgs = Array.from(files ?? []).filter((f) => f.type.startsWith("image/"));
      if (imgs.length) subirArchivos(imgs);
    },
    [subirArchivos],
  );

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const files = Array.from(e.clipboardData?.files ?? []);
      if (files.some((f) => f.type.startsWith("image/"))) {
        e.preventDefault();
        recibir(files);
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [recibir]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function onDragEnd(e: DragEndEvent) {
    if (!e.over || e.active.id === e.over.id) return;
    const from = insumos.findIndex((i) => i.id === e.active.id);
    const to = insumos.findIndex((i) => i.id === e.over!.id);
    if (from < 0 || to < 0) return;
    qc.setQueryData(keys.insumos(tareaId), arrayMove(insumos, from, to));
    patch.mutate({ id: String(e.active.id), patch: { orden: to } });
  }

  return (
    <div className="space-y-5">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastrando(false);
          recibir(e.dataTransfer.files);
        }}
        data-testid="zona-arrastre"
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 text-center transition-colors",
          arrastrando ? "border-primary bg-primary/10" : "border-border bg-card/40",
        )}
      >
        <UploadCloud className="size-8 text-primary" />
        <p className="text-sm">
          Arrastra imágenes aquí, pega con <kbd className="rounded border px-1.5 py-0.5 text-xs">Ctrl</kbd>+
          <kbd className="rounded border px-1.5 py-0.5 text-xs">V</kbd> o
        </p>
        <Button variant="secondary" onClick={() => inputRef.current?.click()} disabled={subir.isPending}>
          <ImagePlus /> {subir.isPending ? "Subiendo…" : "Elegir archivos"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          hidden
          data-testid="input-archivos"
          onChange={(e) => {
            recibir(e.target.files);
            e.target.value = "";
          }}
        />
        {subir.error && <p className="text-sm text-destructive">{subir.error.message}</p>}
      </div>

      {insumos.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={insumos.map((i) => i.id)} strategy={rectSortingStrategy}>
            <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4" aria-label="Insumos">
              {insumos.map((ins, idx) => (
                <TarjetaInsumo
                  key={ins.id}
                  insumo={ins}
                  numero={idx + 1}
                  onPatch={(p) => patch.mutate({ id: ins.id, patch: p })}
                  onBorrar={() => borrar.mutate(ins.id)}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
      )}

      <div className="space-y-2 rounded-xl border bg-card p-4">
        <label htmlFor="texto-propio" className="flex items-center gap-2 text-sm font-medium">
          <Type className="size-4 text-primary" /> Texto propio
        </label>
        <Textarea
          id="texto-propio"
          placeholder="Notas, datos o contexto adicional que Gemini debe considerar…"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          rows={4}
        />
        <Button
          variant="secondary"
          size="sm"
          disabled={!texto.trim() || agregarTexto.isPending}
          onClick={() => agregarTexto.mutate(texto.trim())}
        >
          Agregar texto
        </Button>
      </div>

      <div className="flex justify-end">
        <Button onClick={onContinuar} disabled={insumos.length === 0}>
          Continuar a generar
        </Button>
      </div>
    </div>
  );
}

function TarjetaInsumo({
  insumo,
  numero,
  onPatch,
  onBorrar,
}: {
  insumo: Insumo;
  numero: number;
  onPatch: (p: { rotacion?: Insumo["rotacion"]; usar_recorte?: boolean }) => void;
  onBorrar: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: insumo.id,
  });
  const [comparar, setComparar] = useState(false);
  const esImagen = insumo.tipo === "imagen";
  const url = fileUrl(
    insumo.usar_recorte
      ? (insumo.miniatura_url ?? insumo.recortada_url ?? insumo.original_url)
      : insumo.original_url,
  );
  const girar = () => onPatch({ rotacion: ((insumo.rotacion + 90) % 360) as Insumo["rotacion"] });

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-xl border bg-card",
        isDragging && "z-10 opacity-80 shadow-2xl ring-2 ring-primary",
      )}
    >
      <div className="flex items-center justify-between border-b px-2 py-1.5 text-xs text-muted-foreground">
        <button
          type="button"
          aria-label={`Reordenar insumo ${numero}`}
          className="flex cursor-grab items-center gap-1 rounded px-1 outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="size-4" /> {numero}
        </button>
        {esImagen && <span>{insumo.usar_recorte ? "Recortada" : "Original"}</span>}
      </div>

      <div className="flex aspect-[3/4] items-center justify-center overflow-hidden bg-muted p-2">
        {!esImagen && (
          <div className="h-full w-full overflow-hidden text-xs leading-relaxed text-muted-foreground">
            <FileText className="mb-2 size-4 text-primary" />
            {insumo.texto}
          </div>
        )}
        {esImagen && comparar && (
          <div className="grid h-full w-full grid-cols-2 gap-1">
            <figure className="flex min-h-0 flex-col items-center gap-1">
              <img src={fileUrl(insumo.original_url)} alt="Antes" className="min-h-0 flex-1 object-contain" />
              <figcaption className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Antes
              </figcaption>
            </figure>
            <figure className="flex min-h-0 flex-col items-center gap-1">
              <img
                src={fileUrl(insumo.recortada_url ?? insumo.original_url)}
                alt="Después"
                className="min-h-0 flex-1 object-contain"
              />
              <figcaption className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Después
              </figcaption>
            </figure>
          </div>
        )}
        {esImagen && !comparar && (
          <img
            src={url}
            alt={`Insumo ${numero}`}
            className="max-h-full max-w-full object-contain transition-transform"
            style={{ transform: `rotate(${insumo.rotacion}deg)` }}
          />
        )}
      </div>

      <div className="flex items-center justify-end gap-0.5 border-t p-1">
        {esImagen && (
          <>
            <Button
              size="icon"
              variant="ghost"
              className="size-8"
              title="Comparar antes y después"
              aria-label="Comparar antes y después"
              aria-pressed={comparar}
              onClick={() => setComparar((v) => !v)}
            >
              <Columns2 />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="size-8"
              title="Rotar 90°"
              aria-label="Rotar"
              onClick={girar}
            >
              <RotateCw />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className={cn("size-8", insumo.usar_recorte && "text-primary")}
              title="Alternar recorte"
              aria-label="Alternar recorte"
              aria-pressed={insumo.usar_recorte}
              onClick={() => onPatch({ usar_recorte: !insumo.usar_recorte })}
            >
              <Crop />
            </Button>
          </>
        )}
        <Button
          size="icon"
          variant="ghost"
          className="size-8 text-destructive hover:text-destructive"
          title="Borrar"
          aria-label="Borrar"
          onClick={onBorrar}
        >
          <Trash2 />
        </Button>
      </div>
    </li>
  );
}
