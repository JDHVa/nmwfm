import type {
  ClaveComponente,
  ComponenteNota,
  ElementoPortafolio,
  EstadoMateria,
  MateriaCalificacion,
  Pendiente,
  ResumenCalificaciones,
  TipoMateria,
} from "@/lib/api";

type Tarea = { titulo: string; valor: number; cal: number | null; perdida: boolean };
type Base = {
  clave: string;
  nombre: string;
  auto: TipoMateria;
  par1: number | null;
  emt: number | null;
  par2: number | null;
  eg: number | null;
  tareas: Tarea[];
};

const t = (titulo: string, valor: number, cal: number | null, perdida = false): Tarea => ({
  titulo,
  valor,
  cal,
  perdida,
});

export const BASES: Base[] = [
  {
    clave: "015",
    nombre: "Introducción a las Ciencias Sociales",
    auto: "bachillerato",
    par1: 100,
    emt: 70,
    par2: null,
    eg: null,
    tareas: [
      t("Mapa conceptual", 8, 92),
      t("Línea del tiempo", 8, 85),
      t("Ensayo", 12, 90),
      t("Proyecto integrador", 12, null),
    ],
  },
  {
    clave: "019",
    nombre: "Elección Vocacional",
    auto: "portafolio",
    par1: null,
    emt: null,
    par2: null,
    eg: null,
    tareas: [t("Test de intereses", 30, null), t("Entrevista", 30, null), t("Plan de carrera", 40, null)],
  },
  {
    clave: "026",
    nombre: "La Mecánica y el Entorno",
    auto: "bachillerato",
    par1: 100,
    emt: 40,
    par2: null,
    eg: null,
    tareas: [
      t("Práctica de fuerzas", 10, 80),
      t("Reporte de laboratorio", 10, 0, true),
      t("Problemario", 10, 70),
      t("Proyecto final", 10, null),
    ],
  },
  {
    clave: "030",
    nombre: "La Naturaleza de la Vida",
    auto: "bachillerato",
    par1: 100,
    emt: 80,
    par2: null,
    eg: null,
    tareas: [
      t("Cuadro comparativo", 10, 90),
      t("Reporte de práctica", 10, 80),
      t("Infografía", 10, 85),
      t("Evidencia final", 10, null),
    ],
  },
  {
    clave: "033",
    nombre: "Lógica",
    auto: "bachillerato",
    par1: 96,
    emt: null,
    par2: null,
    eg: null,
    tareas: [
      t("Tabla de verdad", 10, 95),
      t("Argumentos", 10, 90),
      t("Silogismos", 10, null),
      t("Proyecto", 10, null),
    ],
  },
  {
    clave: "095",
    nombre: "Sistemas de Calidad",
    auto: "carrera",
    par1: 95,
    emt: 92,
    par2: null,
    eg: null,
    tareas: [
      t("Diagrama de Ishikawa", 12.5, 95),
      t("Pareto", 12.5, 90),
      t("Auditoría simulada", 12.5, 88),
      t("Manual de calidad", 12.5, null),
    ],
  },
  {
    clave: "644",
    nombre: "Redes Neuronales y Aprendizaje Profundo",
    auto: "carrera",
    par1: 96,
    emt: null,
    par2: null,
    eg: null,
    tareas: [
      t("Perceptrón", 12.5, 100),
      t("Clasificador con Keras", 12.5, 90),
      t("CNN", 12.5, null),
      t("Proyecto final", 12.5, null),
    ],
  },
  {
    clave: "645",
    nombre: "Algoritmos Bio Inspirados",
    auto: "carrera",
    par1: 100,
    emt: 83,
    par2: null,
    eg: null,
    tareas: [
      t("Algoritmo genético", 12.5, 92),
      t("Colonia de hormigas", 12.5, 88),
      t("Enjambre de partículas", 12.5, null),
      t("Reporte", 12.5, null),
    ],
  },
  {
    clave: "646",
    nombre: "Comunicación Integral en Inglés Técnico I",
    auto: "bachillerato",
    par1: 100,
    emt: 88,
    par2: null,
    eg: null,
    tareas: [
      t("Technical email", 10, 100),
      t("Glossary", 10, 95),
      t("Oral presentation", 10, null),
      t("Final report", 10, null),
    ],
  },
  {
    clave: "672",
    nombre: "Desarrollo de Aplicaciones Móviles",
    auto: "carrera",
    par1: 100,
    emt: 33,
    par2: null,
    eg: null,
    tareas: [
      t("Interfaz en Figma", 12.5, 90),
      t("App de notas", 12.5, 0, true),
      t("Consumo de API", 12.5, null),
      t("Proyecto final", 12.5, null),
    ],
  },
];

const PESOS: Record<TipoMateria, Record<ClaveComponente, number>> = {
  bachillerato: { par1: 10, emt: 15, par2: 10, eg: 25, portafolio: 40 },
  carrera: { par1: 10, emt: 15, par2: 10, eg: 15, portafolio: 50 },
  portafolio: { par1: 0, emt: 0, par2: 0, eg: 0, portafolio: 100 },
};
const NOMBRES: Record<ClaveComponente, string> = {
  par1: "Parcial 1",
  emt: "Examen de medio término",
  par2: "Parcial 2",
  eg: "Examen global",
  portafolio: "Portafolio",
};
const ORDEN: ClaveComponente[] = ["par1", "emt", "par2", "eg", "portafolio"];

const redondear = (n: number) => Math.round(n * 100) / 100;

function cdf(z: number): number {
  const x = Math.abs(z) / Math.SQRT2;
  const tt = 1 / (1 + 0.3275911 * x);
  const poly =
    tt * (0.254829592 + tt * (-0.284496736 + tt * (1.421413741 + tt * (-1.453152027 + tt * 1.061405429))));
  const erf = 1 - poly * Math.exp(-x * x);
  return z >= 0 ? 0.5 * (1 + erf) : 0.5 * (1 - erf);
}

function probSuperar(meta: number, media: number, sd: number): number {
  if (sd === 0) return media >= meta ? 1 : 0;
  return Math.round((1 - cdf((meta - media) / sd)) * 100) / 100;
}

export type EstadoCalificaciones = {
  objetivos: Record<string, number | null>;
  tipos: Record<string, TipoMateria | null>;
  objetivoSemestre: number | null;
  leidaEn: string | null;
};

function calcularMateria(base: Base, est: EstadoCalificaciones): MateriaCalificacion {
  const manual = est.tipos[base.clave] ?? null;
  const tipo = manual ?? base.auto;
  const pesos = PESOS[tipo];
  const componentes: ComponenteNota[] = [];
  const pendientes: Pendiente[] = [];
  const portafolio: ElementoPortafolio[] = [];
  const notas: number[] = [];
  let asegurados = 0;

  for (const clave of ORDEN) {
    const peso = pesos[clave];
    if (peso === 0) continue;
    if (clave === "portafolio") {
      const escala = peso / base.tareas.reduce((s, x) => s + x.valor, 0);
      let ganados = 0;
      let calificados = 0;
      for (const x of base.tareas) {
        const valor = redondear(x.valor * escala);
        const puntos = x.cal === null ? null : redondear((x.cal * valor) / 100);
        portafolio.push({ titulo: x.titulo, valor, puntos, perdida: x.perdida });
        if (x.perdida) {
          calificados += valor;
        } else if (puntos === null) {
          pendientes.push({ clave, titulo: x.titulo, peso: valor });
        } else {
          ganados += puntos;
          calificados += valor;
          notas.push(x.cal!);
        }
      }
      asegurados += ganados;
      componentes.push({
        clave,
        nombre: NOMBRES[clave],
        peso,
        calificacion: calificados ? redondear((ganados / calificados) * 100) : null,
        puntos: calificados ? redondear(ganados) : null,
      });
      continue;
    }
    const cal = base[clave];
    const puntos = cal === null ? null : redondear((cal * peso) / 100);
    componentes.push({ clave, nombre: NOMBRES[clave], peso, calificacion: cal, puntos });
    if (puntos === null) {
      pendientes.push({ clave, titulo: NOMBRES[clave], peso });
    } else {
      asegurados += puntos;
      notas.push(cal!);
    }
  }

  asegurados = redondear(asegurados);
  const pesoPendiente = pendientes.reduce((s, p) => s + p.peso, 0);
  const maximo = redondear(asegurados + pesoPendiente);
  const hayDatos = notas.length > 0 || base.tareas.some((x) => x.perdida);
  const media = notas.length ? notas.reduce((s, x) => s + x, 0) / notas.length : 80;
  const proyectada = redondear(asegurados + (pesoPendiente * media) / 100);
  const sd = (Math.sqrt(pendientes.reduce((s, p) => s + p.peso ** 2, 0)) * 12) / 100;
  const rango: [number, number] = [
    redondear(Math.max(asegurados, proyectada - 1.2816 * sd)),
    redondear(Math.min(maximo, proyectada + 1.2816 * sd)),
  ];
  const objetivo = est.objetivos[base.clave] ?? null;
  const necesario =
    objetivo === null || pesoPendiente === 0
      ? null
      : Math.max(0, redondear(((objetivo - asegurados) / pesoPendiente) * 100));
  const necesarioAprobar = pesoPendiente === 0 ? 0 : ((70 - asegurados) / pesoPendiente) * 100;
  const probAprobar = hayDatos ? probSuperar(70, proyectada, sd) : 0;
  const probObjetivo = objetivo === null ? null : probSuperar(objetivo, proyectada, sd);
  let estado: EstadoMateria;
  if (!hayDatos) estado = "sin_datos";
  else if (probAprobar < 0.6 || necesarioAprobar > 90) estado = "riesgo";
  else if (probObjetivo !== null && probObjetivo < 0.5) estado = "atento";
  else estado = "bien";

  return {
    clave: base.clave,
    nombre: base.nombre,
    materia_id: null,
    tipo,
    tipo_manual: manual !== null,
    componentes,
    portafolio,
    pendientes,
    asegurados,
    maximo_posible: maximo,
    proyectada,
    rango,
    objetivo,
    necesario,
    alcanzable: necesario === null || necesario <= 100,
    prob_objetivo: probObjetivo,
    prob_aprobar: probAprobar,
    estado,
  };
}

export function calcularResumen(est: EstadoCalificaciones): ResumenCalificaciones {
  const materias = BASES.map((b) => calcularMateria(b, est));
  const n = materias.length;
  const prom = (f: (m: MateriaCalificacion) => number) => redondear(materias.reduce((s, m) => s + f(m), 0) / n);
  const proyectada = prom((m) => m.proyectada);
  const actual = prom((m) => m.asegurados);
  const sd = Math.sqrt(materias.reduce((s, m) => s + ((m.rango[1] - m.rango[0]) / 2.563) ** 2, 0)) / n;
  const objetivo = est.objetivoSemestre;
  const pendiente = materias.reduce((s, m) => s + (m.maximo_posible - m.asegurados), 0) / n;
  return {
    materias,
    semestre: {
      actual,
      proyectada,
      rango: [
        redondear(Math.max(actual, proyectada - 1.2816 * sd)),
        redondear(Math.min(100, proyectada + 1.2816 * sd)),
      ],
      objetivo,
      prob_objetivo: objetivo === null ? null : probSuperar(objetivo, proyectada, sd),
      necesario_promedio:
        objetivo === null || pendiente <= 0 ? null : Math.max(0, redondear(((objetivo - actual) / pendiente) * 100)),
    },
    siase_leida_en: est.leidaEn,
  };
}
