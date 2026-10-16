import { useState } from "react";
import { ChevronDown, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { AjusteMateria, Escenario, MateriaCalificacion, PresetEscenario, ResultadoEscenario } from "@/lib/api";
import { ESCENARIO_INICIAL, ETIQUETA_PRESET, nota, promedio } from "@/lib/calificaciones";
import { cn } from "@/lib/utils";
import { NumeroEditable } from "./NumeroEditable";

const PRESETS: PresetEscenario[] = ["pesimista", "realista", "optimista", "mio", "personalizado"];

function Deslizador({
  id,
  etiqueta,
  valor,
  auto,
  onCambio,
}: {
  id: string;
  etiqueta: string;
  valor: number;
  auto?: boolean;
  onCambio: (v: number) => void;
}) {
  return (
    <div className="grid grid-cols-[6rem_1fr_3rem] items-center gap-3 text-sm">
      <label htmlFor={id} className="text-muted-foreground">
        {etiqueta}
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={1}
        value={valor}
        onChange={(e) => onCambio(Number(e.target.value))}
        className="w-full accent-primary"
      />
      <span className={cn("text-right tabular-nums", auto && "text-muted-foreground")}>{valor}</span>
    </div>
  );
}

function AjusteDeMateria({
  m,
  ajuste,
  resultado,
  onCambio,
}: {
  m: MateriaCalificacion;
  ajuste: AjusteMateria;
  resultado: ResultadoEscenario["materias"][number] | undefined;
  onCambio: (a: AjusteMateria) => void;
}) {
  const [abierta, setAbierta] = useState(false);
  const mediaGrupo = (grupo: "examenes" | "tareas") =>
    promedio(
      (resultado?.pendientes ?? [])
        .filter((p) => (p.clave === "portafolio") === (grupo === "tareas"))
        .map((p) => p.nota),
    );
  const hayExamenes = m.pendientes.some((p) => p.clave !== "portafolio");
  const hayTareas = m.pendientes.some((p) => p.clave === "portafolio");
  const modificada = ajuste.examenes !== undefined || ajuste.tareas !== undefined || !!ajuste.esfuerzo || !!ajuste.pendientes;

  function cambiarPendiente(i: number, v: number | null) {
    const resto = { ...(ajuste.pendientes ?? {}) };
    if (v === null) delete resto[i];
    else resto[i] = v;
    onCambio({ ...ajuste, pendientes: Object.keys(resto).length > 0 ? resto : undefined });
  }

  return (
    <li className="rounded-lg border">
      <button
        type="button"
        aria-expanded={abierta}
        onClick={() => setAbierta((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronDown className={cn("size-4 shrink-0 transition-transform", abierta && "rotate-180")} />
        <span className="min-w-0 flex-1 truncate font-medium">{m.nombre}</span>
        {modificada && <span className="text-xs text-primary">ajustada</span>}
        <span className="tabular-nums text-muted-foreground">{resultado ? nota(resultado.final) : "—"}</span>
      </button>
      {abierta && (
        <div className="space-y-3 border-t px-3 py-3">
          {m.pendientes.length === 0 ? (
            <p className="text-sm text-muted-foreground">No queda nada pendiente.</p>
          ) : (
            <>
              {hayExamenes && (
                <Deslizador
                  id={`esc-ex-${m.clave}`}
                  etiqueta={`Exámenes de ${m.nombre}`}
                  valor={ajuste.examenes ?? Math.round(mediaGrupo("examenes") ?? 80)}
                  auto={ajuste.examenes === undefined}
                  onCambio={(v) => onCambio({ ...ajuste, examenes: v })}
                />
              )}
              {hayTareas && (
                <Deslizador
                  id={`esc-ta-${m.clave}`}
                  etiqueta={`Tareas de ${m.nombre}`}
                  valor={ajuste.tareas ?? Math.round(mediaGrupo("tareas") ?? 80)}
                  auto={ajuste.tareas === undefined}
                  onCambio={(v) => onCambio({ ...ajuste, tareas: v })}
                />
              )}
              <ul className="space-y-1.5">
                {m.pendientes.map((p, i) => {
                  const supuesta = resultado?.pendientes[i]?.nota;
                  return (
                    <li key={`${p.clave}-${i}`} className="flex items-center justify-between gap-3 text-sm">
                      <span className="min-w-0 truncate">
                        {p.titulo} <span className="text-xs text-muted-foreground">({nota(p.peso)} pts)</span>
                      </span>
                      <NumeroEditable
                        etiqueta={`Nota de ${p.titulo} en ${m.nombre}`}
                        valor={ajuste.pendientes?.[i] ?? null}
                        placeholder={supuesta === undefined ? "—" : nota(supuesta)}
                        onGuardar={(v) => cambiarPendiente(i, v)}
                      />
                    </li>
                  );
                })}
              </ul>
              <label className="flex items-center justify-between gap-3 text-sm">
                <span>
                  Le voy a echar ganas
                  <span className="block text-xs text-muted-foreground">En el escenario optimista, la pone en 100.</span>
                </span>
                <Switch
                  aria-label={`Le voy a echar ganas en ${m.nombre}`}
                  checked={!!ajuste.esfuerzo}
                  onCheckedChange={(v) => onCambio({ ...ajuste, esfuerzo: v })}
                />
              </label>
            </>
          )}
        </div>
      )}
    </li>
  );
}

export function PanelEscenarios({
  materias,
  escenario,
  onCambio,
  resultado,
}: {
  materias: MateriaCalificacion[];
  escenario: Escenario;
  onCambio: (e: Escenario) => void;
  resultado: ResultadoEscenario | undefined;
}) {
  function ajustar(clave: string, a: AjusteMateria) {
    onCambio({ ...escenario, materias: { ...(escenario.materias ?? {}), [clave]: a } });
  }
  const media = (grupo: "examenes" | "tareas") =>
    promedio(
      (resultado?.materias ?? []).flatMap((r) =>
        r.pendientes.filter((p) => (p.clave === "portafolio") === (grupo === "tareas")).map((p) => p.nota),
      ),
    );
  const globalValor = (grupo: "examenes" | "tareas") => escenario[grupo] ?? Math.round(media(grupo) ?? 80);

  return (
    <section aria-label="Escenarios" className="space-y-4 rounded-xl border bg-card p-5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Escenarios</h3>
          <p className="text-xs text-muted-foreground">Supón qué sacarás en lo que falta y mira cómo quedaría el semestre.</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => onCambio(ESCENARIO_INICIAL)}>
          <RotateCcw /> Restablecer
        </Button>
      </div>

      <div role="group" aria-label="Escenario" className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={escenario.preset === p}
            onClick={() => onCambio({ preset: p, materias: escenario.materias })}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring",
              escenario.preset === p ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
            )}
          >
            {ETIQUETA_PRESET[p]}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        <Deslizador
          id="esc-global-examenes"
          etiqueta="Exámenes"
          valor={globalValor("examenes")}
          auto={escenario.examenes === undefined}
          onCambio={(v) => onCambio({ ...escenario, preset: "personalizado", examenes: v })}
        />
        <Deslizador
          id="esc-global-tareas"
          etiqueta="Tareas"
          valor={globalValor("tareas")}
          auto={escenario.tareas === undefined}
          onCambio={(v) => onCambio({ ...escenario, preset: "personalizado", tareas: v })}
        />
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold">Por materia</h4>
        <ul className="space-y-2">
          {materias.map((m) => (
            <AjusteDeMateria
              key={m.clave}
              m={m}
              ajuste={escenario.materias?.[m.clave] ?? {}}
              resultado={resultado?.materias.find((r) => r.clave === m.clave)}
              onCambio={(a) => ajustar(m.clave, a)}
            />
          ))}
        </ul>
      </div>
    </section>
  );
}
