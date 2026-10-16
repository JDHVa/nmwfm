import { useState } from "react";
import { ArrowDown, ArrowUp, Check, Pencil, Plus, RotateCcw, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { InstruccionFija, Settings } from "@/lib/api";
import { useSaveSettings } from "@/lib/queries";

export const INSTRUCCIONES_PREDETERMINADAS: InstruccionFija[] = [
  {
    id: "rubrica_maxima",
    texto: "Cumple cada criterio de la rúbrica en su nivel máximo.",
    activa: true,
    sistema: true,
  },
  {
    id: "cubrir_contenido",
    texto: "Cubre todo el contenido indicado en la tarea sin dejar temas fuera.",
    activa: true,
    sistema: true,
  },
  {
    id: "tono_preparatoria",
    texto: "Usa un tono claro y académico adecuado para preparatoria.",
    activa: true,
    sistema: true,
  },
  {
    id: "no_mencionar_rubrica",
    texto: "No menciones la rúbrica ni los criterios en el texto.",
    activa: true,
    sistema: true,
  },
  {
    id: "referencias_apa7",
    texto:
      "Termina con una sección ## Referencias en formato APA 7 con fuentes reales y verificables; no inventes referencias.",
    activa: true,
    sistema: true,
  },
];

function idNuevo() {
  return `u-${Math.random().toString(36).slice(2, 10)}`;
}

export function InstruccionesFijasSeccion({ settings }: { settings: Settings }) {
  const guardar = useSaveSettings();
  const lista = settings.instrucciones_fijas ?? [];
  const [editando, setEditando] = useState<string | null>(null);
  const [borrador, setBorrador] = useState("");
  const [nueva, setNueva] = useState("");
  const [espera, setEspera] = useState<string | null>(null);

  const guardarLista = (siguiente: InstruccionFija[]) => guardar.mutate({ instrucciones_fijas: siguiente });
  const cambiar = (id: string, parche: Partial<InstruccionFija>) =>
    guardarLista(lista.map((i) => (i.id === id ? { ...i, ...parche } : i)));
  const mover = (indice: number, delta: number) => {
    const copia = [...lista];
    const [item] = copia.splice(indice, 1);
    copia.splice(indice + delta, 0, item);
    guardarLista(copia);
  };

  function confirmarEdicion() {
    const texto = borrador.trim();
    if (editando && texto) cambiar(editando, { texto });
    setEditando(null);
  }

  function agregar() {
    const texto = nueva.trim();
    if (!texto) return;
    guardarLista([...lista, { id: idNuevo(), texto, activa: true, sistema: false }]);
    setNueva("");
  }

  function guardarEspera() {
    if (espera === null) return;
    const n = Math.min(15, Math.max(0, Math.round(Number(espera) || 0)));
    setEspera(null);
    guardar.mutate({ gemini_espera_envio_s: n });
  }

  return (
    <section
      aria-label="Lo que siempre se manda a Gemini"
      className="space-y-4 rounded-xl border bg-card p-6"
    >
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Lo que siempre se manda a Gemini
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Estas instrucciones van en cada prompt, en este orden. Puedes ajustarlas para una sola tarea al
          generarla.
        </p>
      </div>
      <ul aria-label="Instrucciones fijas" className="space-y-2">
        {lista.map((ins, i) => (
          <li
            key={ins.id}
            className="flex items-start gap-3 rounded-lg border bg-background/60 p-3"
            data-testid={`instruccion-${ins.id}`}
          >
            <Switch
              aria-label={`Activar: ${ins.texto}`}
              checked={ins.activa}
              onCheckedChange={(v) => cambiar(ins.id, { activa: v })}
              className="mt-0.5"
            />
            <div className="min-w-0 flex-1">
              {editando === ins.id ? (
                <div className="space-y-2">
                  <Textarea
                    aria-label="Texto de la instrucción"
                    rows={3}
                    value={borrador}
                    onChange={(e) => setBorrador(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <Button size="sm" onClick={confirmarEdicion} disabled={!borrador.trim()}>
                      <Check /> Guardar texto
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditando(null)}>
                      <X /> Cancelar
                    </Button>
                  </div>
                </div>
              ) : (
                <p className={ins.activa ? "text-sm" : "text-sm text-muted-foreground line-through"}>
                  {ins.texto}
                </p>
              )}
            </div>
            {editando !== ins.id && (
              <div className="flex shrink-0 gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Subir"
                  disabled={i === 0}
                  onClick={() => mover(i, -1)}
                >
                  <ArrowUp />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Bajar"
                  disabled={i === lista.length - 1}
                  onClick={() => mover(i, 1)}
                >
                  <ArrowDown />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Editar"
                  onClick={() => {
                    setEditando(ins.id);
                    setBorrador(ins.texto);
                  }}
                >
                  <Pencil />
                </Button>
                {!ins.sistema && (
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label="Borrar"
                    onClick={() => guardarLista(lista.filter((x) => x.id !== ins.id))}
                  >
                    <Trash2 />
                  </Button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>

      <div className="space-y-2">
        <label htmlFor="instruccion-nueva" className="text-sm font-medium">
          Agregar instrucción
        </label>
        <Textarea
          id="instruccion-nueva"
          rows={2}
          placeholder="Por ejemplo: incluye siempre un ejemplo práctico."
          value={nueva}
          onChange={(e) => setNueva(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={agregar} disabled={!nueva.trim()}>
            <Plus /> Agregar
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => guardarLista(INSTRUCCIONES_PREDETERMINADAS.map((i) => ({ ...i })))}
          >
            <RotateCcw /> Restaurar predeterminadas
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 border-t pt-4">
        <div>
          <label htmlFor="espera-gemini" className="text-sm font-medium">
            Espera antes de enviar a Gemini (segundos)
          </label>
          <p className="text-xs text-muted-foreground">
            Pausa tras pegar el prompt y adjuntar el PDF, de 0 a 15.
          </p>
        </div>
        <Input
          id="espera-gemini"
          type="number"
          min={0}
          max={15}
          className="w-20"
          value={espera ?? String(settings.gemini_espera_envio_s ?? 3)}
          onChange={(e) => setEspera(e.target.value)}
          onBlur={guardarEspera}
          onKeyDown={(e) => e.key === "Enter" && guardarEspera()}
        />
      </div>
    </section>
  );
}
