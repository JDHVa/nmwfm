import { useId, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DatosPortada } from "@/lib/api";
import { useProfesores, useSettings } from "@/lib/queries";

export type CamposPortada = Required<DatosPortada>;
const CLAVES = ["aula", "grupo", "turno", "especialidad"] as const;

export function usePortadaForm(profesorInicial = "") {
  const { data: settings } = useSettings();
  const [cambios, setCambios] = useState<Partial<CamposPortada>>({});
  const valores: CamposPortada = {
    profesor: cambios.profesor ?? profesorInicial,
    aula: cambios.aula ?? settings?.aula ?? "",
    grupo: cambios.grupo ?? settings?.grupo ?? "",
    turno: cambios.turno ?? settings?.turno ?? "",
    especialidad: cambios.especialidad ?? settings?.especialidad ?? "",
  };
  const cambiar = (campo: keyof CamposPortada, valor: string) => setCambios((c) => ({ ...c, [campo]: valor }));
  return { valores, cambiar };
}

export function datosDePortada(valores: CamposPortada): DatosPortada {
  return Object.fromEntries(
    Object.entries(valores)
      .map(([k, v]) => [k, v.trim()])
      .filter(([, v]) => v),
  );
}

const ETIQUETAS: Record<(typeof CLAVES)[number], string> = {
  aula: "Aula",
  grupo: "Grupo",
  turno: "Turno",
  especialidad: "Especialidad",
};

export function PortadaCampos({
  valores,
  onCambio,
  prefijo,
}: {
  valores: CamposPortada;
  onCambio: (campo: keyof CamposPortada, valor: string) => void;
  prefijo: string;
}) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <ProfesorCombobox
          id={`${prefijo}-profesor`}
          value={valores.profesor}
          onChange={(v) => onCambio("profesor", v)}
        />
        {CLAVES.map((k) => (
          <div key={k} className="space-y-1.5">
            <Label htmlFor={`${prefijo}-${k}`}>{ETIQUETAS[k]}</Label>
            <Input id={`${prefijo}-${k}`} value={valores[k]} onChange={(e) => onCambio(k, e.target.value)} />
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        La fecha de la portada es siempre la de hoy ({new Date().toLocaleDateString("es-MX")}). Aula, grupo,
        turno y especialidad vienen de Configuración y aquí solo cambian esta portada.
      </p>
    </div>
  );
}

function ProfesorCombobox({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const { data: profesores = [] } = useProfesores();
  const [abierto, setAbierto] = useState(false);
  const lista = useId();
  const filtro = value.trim().toLowerCase();
  const opciones = profesores.filter((p) => p.nombre.toLowerCase().includes(filtro));

  return (
    <div className="relative space-y-1.5">
      <Label htmlFor={id}>Profesor</Label>
      <Input
        id={id}
        role="combobox"
        aria-expanded={abierto && opciones.length > 0}
        aria-controls={lista}
        aria-autocomplete="list"
        autoComplete="off"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setAbierto(true);
        }}
        onFocus={() => setAbierto(true)}
        onBlur={() => setAbierto(false)}
        onKeyDown={(e) => e.key === "Escape" && setAbierto(false)}
      />
      {abierto && opciones.length > 0 && (
        <ul
          id={lista}
          role="listbox"
          aria-label="Profesores guardados"
          className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {opciones.map((p) => (
            <li
              key={p.nombre}
              role="option"
              aria-selected={p.nombre === value}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(p.nombre);
                setAbierto(false);
              }}
              className="cursor-pointer rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground"
            >
              <span className="block">{p.nombre}</span>
              {p.materias.length > 0 && (
                <span className="block text-xs text-muted-foreground">{p.materias.join(", ")}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
