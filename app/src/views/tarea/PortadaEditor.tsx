import { useQuery } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type PortadaOverrides } from "@/lib/api";
import { useDebounced } from "@/lib/debounce";

export function PortadaEditor({
  tareaId,
  valor,
  onChange,
  disabled,
}: {
  tareaId: string;
  valor: PortadaOverrides;
  onChange: (v: PortadaOverrides) => void;
  disabled?: boolean;
}) {
  const debounced = useDebounced(valor);
  const base = useQuery({
    queryKey: ["portada", tareaId, "base"],
    queryFn: () => api.portadaPreview(tareaId),
  });
  const vista = useQuery({
    queryKey: ["portada", tareaId, debounced.profesor ?? "", debounced.titulo ?? ""],
    queryFn: () => api.portadaPreview(tareaId, debounced),
    placeholderData: (previa) => previa,
  });

  return (
    <section
      aria-labelledby="titulo-portada"
      className="grid gap-4 rounded-xl border bg-card p-4 md:grid-cols-[1fr_220px]"
    >
      <div className="space-y-3">
        <h3 id="titulo-portada" className="text-sm font-medium">
          Portada del documento
        </h3>
        <p className="text-xs text-muted-foreground">
          Así se verá la primera hoja. Puedes cambiar el profesor o el título antes de generar.
        </p>
        <div className="space-y-2">
          <Label htmlFor="portada-profesor">Profesor</Label>
          <Input
            id="portada-profesor"
            disabled={disabled}
            value={valor.profesor ?? base.data?.profesor ?? ""}
            onChange={(e) => onChange({ ...valor, profesor: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="portada-titulo">Título</Label>
          <Input
            id="portada-titulo"
            disabled={disabled}
            value={valor.titulo ?? base.data?.titulo ?? ""}
            onChange={(e) => onChange({ ...valor, titulo: e.target.value })}
          />
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border bg-white shadow-card">
        {vista.data ? (
          <img src={vista.data.imagen_url} alt="Vista previa de la portada" className="w-full" />
        ) : (
          <div className="flex aspect-[3/4] items-center justify-center text-xs text-muted-foreground">
            {vista.isError ? "Sin vista previa" : "Cargando…"}
          </div>
        )}
      </div>
    </section>
  );
}
