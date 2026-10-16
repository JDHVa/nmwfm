import { useState } from "react";
import { ChevronDown, GraduationCap, RefreshCw } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { JobProgress } from "@/components/JobProgress";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type EstadoMateria, type MateriaCalificacion, type ResumenCalificaciones, type TipoMateria } from "@/lib/api";
import {
  APROBATORIA,
  ETIQUETA_ESTADO,
  ETIQUETA_TIPO,
  finalSimulada,
  nota,
  ordenarMaterias,
  porcentaje,
  segmentosBarra,
  type OrdenCalificaciones,
} from "@/lib/calificaciones";
import { keys, useJobRunner, useResumenCalificaciones } from "@/lib/queries";
import { haceTiempo } from "@/lib/sync";
import { cn } from "@/lib/utils";

const COLOR_ESTADO: Record<EstadoMateria, string> = {
  bien: "border-success/40 bg-success/10 text-success",
  atento: "border-warning/40 bg-warning/10 text-warning",
  riesgo: "border-destructive/40 bg-destructive/10 text-destructive",
  sin_datos: "border-border bg-muted text-muted-foreground",
};

function useActualizarResumen() {
  const qc = useQueryClient();
  return (data: ResumenCalificaciones) => qc.setQueryData(keys.resumenCalificaciones, data);
}

function NumeroEditable({
  etiqueta,
  valor,
  onGuardar,
  placeholder = "—",
}: {
  etiqueta: string;
  valor: number | null;
  onGuardar: (v: number | null) => void;
  placeholder?: string;
}) {
  const [texto, setTexto] = useState(valor === null ? "" : String(valor));
  const [previo, setPrevio] = useState(valor);
  if (previo !== valor) {
    setPrevio(valor);
    setTexto(valor === null ? "" : String(valor));
  }

  function guardar() {
    const limpio = texto.trim();
    if (limpio === "") {
      if (valor !== null) onGuardar(null);
      return;
    }
    const n = Number(limpio);
    if (!Number.isFinite(n)) {
      setTexto(valor === null ? "" : String(valor));
      return;
    }
    const acotado = Math.min(100, Math.max(0, n));
    setTexto(String(acotado));
    if (acotado !== valor) onGuardar(acotado);
  }

  return (
    <input
      type="number"
      inputMode="decimal"
      min={0}
      max={100}
      aria-label={etiqueta}
      placeholder={placeholder}
      value={texto}
      onChange={(e) => setTexto(e.target.value)}
      onBlur={guardar}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      className="h-8 w-20 rounded-md border bg-background px-2 text-sm tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-ring"
    />
  );
}

function BarraComponentes({ m }: { m: MateriaCalificacion }) {
  const s = segmentosBarra(m);
  return (
    <div>
      <div
        role="img"
        aria-label={`Asegurado ${nota(s.asegurado)} de 100, pendiente ${nota(s.pendiente)}, perdido ${nota(s.perdido)}`}
        className="flex h-2.5 overflow-hidden rounded-full bg-muted"
      >
        <div className="bg-success" style={{ width: `${s.asegurado}%` }} />
        <div className="bg-primary/35" style={{ width: `${s.pendiente}%` }} />
        <div className="bg-destructive/60" style={{ width: `${s.perdido}%` }} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
        <span>
          <span className="mr-1 inline-block size-2 rounded-full bg-success" />
          Asegurado {nota(s.asegurado)}
        </span>
        <span>
          <span className="mr-1 inline-block size-2 rounded-full bg-primary/35" />
          Pendiente {nota(s.pendiente)}
        </span>
        <span>
          <span className="mr-1 inline-block size-2 rounded-full bg-destructive/60" />
          Perdido {nota(s.perdido)}
        </span>
      </div>
    </div>
  );
}

function Simulador({ m }: { m: MateriaCalificacion }) {
  const [valores, setValores] = useState<Record<number, number>>(() =>
    Object.fromEntries(m.pendientes.map((_, i) => [i, 80])),
  );
  if (m.pendientes.length === 0) {
    return <p className="text-sm text-muted-foreground">No queda nada pendiente por simular.</p>;
  }
  const final = finalSimulada(m, valores);
  const aprueba = final >= APROBATORIA;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold">¿Y si saco…?</h4>
        <p className="text-sm" aria-live="polite">
          Final exacta:{" "}
          <strong data-testid={`final-${m.clave}`} className="tabular-nums">
            {nota(final)}
          </strong>{" "}
          <span className={aprueba ? "text-success" : "text-destructive"}>
            {aprueba ? "aprobarías" : "no aprobarías"}
          </span>
        </p>
      </div>
      <ul className="space-y-2">
        {m.pendientes.map((p, i) => (
          <li key={`${p.clave}-${i}`} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 sm:grid-cols-[14rem_1fr_auto]">
            <label htmlFor={`sim-${m.clave}-${i}`} className="min-w-0 truncate text-sm">
              {p.titulo} <span className="text-xs text-muted-foreground">({nota(p.peso)} pts)</span>
            </label>
            <input
              id={`sim-${m.clave}-${i}`}
              type="range"
              min={0}
              max={100}
              step={1}
              value={valores[i] ?? 0}
              onChange={(e) => setValores({ ...valores, [i]: Number(e.target.value) })}
              className="order-3 col-span-2 w-full accent-primary sm:order-none sm:col-span-1"
            />
            <span className="w-8 text-right text-sm tabular-nums">{valores[i] ?? 0}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Detalle({ m }: { m: MateriaCalificacion }) {
  return (
    <div className="space-y-5 border-t pt-4">
      <div>
        <h4 className="mb-2 text-sm font-semibold">Componentes</h4>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th scope="col" className="py-1 font-medium">Componente</th>
              <th scope="col" className="py-1 text-right font-medium">Peso</th>
              <th scope="col" className="py-1 text-right font-medium">Calificación</th>
              <th scope="col" className="py-1 text-right font-medium">Puntos</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {m.componentes.map((c) => (
              <tr key={c.clave}>
                <td className="py-1.5">{c.nombre}</td>
                <td className="py-1.5 text-right tabular-nums">{nota(c.peso)}</td>
                <td className="py-1.5 text-right tabular-nums">
                  {c.calificacion === null ? <span className="text-muted-foreground">sin calificar</span> : nota(c.calificacion)}
                </td>
                <td className="py-1.5 text-right tabular-nums">{c.puntos === null ? "—" : nota(c.puntos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {m.portafolio.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">Portafolio por tarea</h4>
          <ul className="divide-y text-sm">
            {m.portafolio.map((p) => (
              <li key={p.titulo} className="flex items-center justify-between gap-3 py-1.5">
                <span className="min-w-0 truncate">{p.titulo}</span>
                <span className="flex shrink-0 items-center gap-2 tabular-nums">
                  {p.perdida ? (
                    <Badge variant="destructive">Perdida</Badge>
                  ) : p.puntos === null ? (
                    <span className="text-muted-foreground">sin calificar</span>
                  ) : (
                    <span>{nota(p.puntos)}</span>
                  )}
                  <span className="text-muted-foreground">/ {nota(p.valor)}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <Simulador m={m} />
    </div>
  );
}

function TarjetaMateria({ m }: { m: MateriaCalificacion }) {
  const [abierta, setAbierta] = useState(false);
  const actualizar = useActualizarResumen();
  const objetivo = useMutation({
    mutationFn: (v: number | null) => api.putObjetivos({ materias: { [m.clave]: v } }),
    onSuccess: actualizar,
  });
  const tipo = useMutation({
    mutationFn: (t: TipoMateria | null) => api.putTipoMateria(m.clave, t),
    onSuccess: actualizar,
  });
  const sinDatos = m.estado === "sin_datos";

  return (
    <article
      aria-label={m.nombre}
      className={cn("space-y-4 rounded-xl border bg-card p-5 shadow-card", m.estado === "riesgo" && "border-destructive/40")}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold leading-tight">{m.nombre}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-medium", COLOR_ESTADO[m.estado])}>
              {ETIQUETA_ESTADO[m.estado]}
            </span>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              Tipo
              <select
                aria-label={`Tipo de ${m.nombre}`}
                value={m.tipo ?? ""}
                disabled={tipo.isPending}
                onChange={(e) => tipo.mutate(e.target.value === "" ? null : (e.target.value as TipoMateria))}
                className="h-7 rounded-md border bg-background px-1.5 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {m.tipo === null && <option value="">Sin definir</option>}
                {(Object.keys(ETIQUETA_TIPO) as TipoMateria[]).map((t) => (
                  <option key={t} value={t}>
                    {ETIQUETA_TIPO[t]}
                  </option>
                ))}
              </select>
            </label>
            {m.tipo_manual && (
              <button
                type="button"
                onClick={() => tipo.mutate(null)}
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              >
                Detectar solo
              </button>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-semibold tabular-nums leading-none">{sinDatos ? "—" : nota(m.proyectada)}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {sinDatos ? "proyectada" : `proyectada · rango ${nota(m.rango[0])}–${nota(m.rango[1])}`}
          </p>
        </div>
      </div>

      <BarraComponentes m={m} />

      <div className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Objetivo</span>
          <NumeroEditable
            etiqueta={`Objetivo de ${m.nombre}`}
            valor={m.objetivo}
            onGuardar={(v) => objetivo.mutate(v)}
          />
        </div>
        <p>
          {m.objetivo === null || m.necesario === null ? (
            <span className="text-muted-foreground">
              {m.objetivo === null ? "Pon un objetivo para ver cuánto necesitas." : "Ya no queda nada pendiente."}
            </span>
          ) : m.alcanzable ? (
            <>
              Necesitas <strong className="tabular-nums">{nota(m.necesario)}</strong> en lo que falta
            </>
          ) : (
            <strong className="text-destructive">No alcanzable</strong>
          )}
        </p>
        <p>
          <span className="text-muted-foreground">Probabilidad de objetivo</span>{" "}
          <strong className="tabular-nums">{sinDatos ? "—" : porcentaje(m.prob_objetivo)}</strong>
        </p>
        <p>
          <span className="text-muted-foreground">Probabilidad de aprobar (≥ {APROBATORIA})</span>{" "}
          <strong className="tabular-nums">{sinDatos ? "—" : porcentaje(m.prob_aprobar)}</strong>
        </p>
      </div>

      <button
        type="button"
        aria-expanded={abierta}
        onClick={() => setAbierta((v) => !v)}
        className="flex items-center gap-1 rounded text-sm font-medium text-primary outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronDown className={cn("size-4 transition-transform", abierta && "rotate-180")} />
        {abierta ? "Ocultar detalle" : "Ver detalle y simulador"}
      </button>
      {abierta && <Detalle m={m} />}
    </article>
  );
}

function EncabezadoSemestre({ resumen }: { resumen: ResumenCalificaciones }) {
  const { semestre: s } = resumen;
  const actualizar = useActualizarResumen();
  const objetivo = useMutation({
    mutationFn: (v: number | null) => api.putObjetivos({ semestre: v }),
    onSuccess: actualizar,
  });
  return (
    <section aria-label="Resumen del semestre" className="grid gap-4 rounded-xl border bg-card p-5 shadow-card sm:grid-cols-2 lg:grid-cols-5">
      <Dato titulo="Promedio actual" valor={nota(s.actual)} />
      <Dato titulo="Proyectado" valor={nota(s.proyectada)} detalle={`rango ${nota(s.rango[0])}–${nota(s.rango[1])}`} />
      <div>
        <p className="text-xs text-muted-foreground">Objetivo del semestre</p>
        <div className="mt-1">
          <NumeroEditable etiqueta="Objetivo del semestre" valor={s.objetivo} onGuardar={(v) => objetivo.mutate(v)} />
        </div>
      </div>
      <Dato titulo="Probabilidad de alcanzarlo" valor={porcentaje(s.prob_objetivo)} />
      <Dato
        titulo="Promedio necesario"
        valor={s.necesario_promedio === null ? "—" : nota(s.necesario_promedio)}
        detalle={s.necesario_promedio !== null && s.necesario_promedio > 100 ? "no alcanzable" : undefined}
      />
    </section>
  );
}

function Dato({ titulo, valor, detalle }: { titulo: string; valor: string; detalle?: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{titulo}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums leading-none">{valor}</p>
      {detalle && <p className="mt-1 text-xs text-muted-foreground">{detalle}</p>}
    </div>
  );
}

const FILTROS: { id: EstadoMateria | "todas"; etiqueta: string }[] = [
  { id: "todas", etiqueta: "Todas" },
  { id: "riesgo", etiqueta: ETIQUETA_ESTADO.riesgo },
  { id: "atento", etiqueta: ETIQUETA_ESTADO.atento },
  { id: "bien", etiqueta: ETIQUETA_ESTADO.bien },
  { id: "sin_datos", etiqueta: ETIQUETA_ESTADO.sin_datos },
];

export function CalificacionesView() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useResumenCalificaciones();
  const runner = useJobRunner(() => void qc.invalidateQueries({ queryKey: keys.resumenCalificaciones }));
  const [filtro, setFiltro] = useState<EstadoMateria | "todas">("todas");
  const [orden, setOrden] = useState<OrdenCalificaciones>("riesgo");

  const materias = data
    ? ordenarMaterias(data.materias, orden).filter((m) => filtro === "todas" || m.estado === filtro)
    : [];

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-8">
      <PageHeader
        titulo="Calificaciones"
        descripcion={
          data?.siase_leida_en
            ? `Leídas de SIASE ${haceTiempo(data.siase_leida_en)}.`
            : "Aún no se han leído las calificaciones de SIASE."
        }
        acciones={
          <Button variant="secondary" disabled={runner.running} onClick={() => void runner.start(api.calificacionesSiase)}>
            <RefreshCw /> Revisar calificaciones en SIASE
          </Button>
        }
      />
      <JobProgress job={runner.job} error={runner.error} onCambio={runner.actualizar} />
      {isLoading && <p className="text-muted-foreground">Cargando calificaciones…</p>}
      {error && <p className="text-destructive">{error.message}</p>}
      {data && (
        <>
          <EncabezadoSemestre resumen={data} />
          {data.materias.length === 0 ? (
            <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
              <GraduationCap className="mx-auto mb-2 size-6" />
              Todavía no hay calificaciones. Usa «Revisar calificaciones en SIASE» para leerlas.
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div role="group" aria-label="Filtrar por estado" className="flex flex-wrap gap-1.5">
                  {FILTROS.map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      aria-pressed={filtro === f.id}
                      onClick={() => setFiltro(f.id)}
                      className={cn(
                        "rounded-full border px-3 py-1 text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        filtro === f.id ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
                      )}
                    >
                      {f.etiqueta}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  Ordenar
                  <select
                    aria-label="Ordenar materias"
                    value={orden}
                    onChange={(e) => setOrden(e.target.value as OrdenCalificaciones)}
                    className="h-8 rounded-md border bg-background px-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="riesgo">En riesgo primero</option>
                    <option value="proyectada">Menor proyectada</option>
                    <option value="nombre">Nombre</option>
                  </select>
                </label>
              </div>
              {materias.length === 0 && (
                <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
                  Ninguna materia coincide con el filtro.
                </div>
              )}
              <div className="space-y-4">
                {materias.map((m) => (
                  <TarjetaMateria key={m.clave} m={m} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
