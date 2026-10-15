import type { EtapaConTareas, Materia, Rubrica, Tarea, TareaDetalle } from "@/lib/api";

export const PROFESOR = "CAVAZOS MARTÍNEZ RAFAEL ALFREDO";
export const PERIODO = "03/AGOSTO/2026 - 18/DICIEMBRE/2026";

const NOMBRES_MATERIAS = [
  "Algoritmos Bio Inspirados",
  "Comunicación Integral en Inglés Técnico I",
  "Desarrollo de Aplicaciones Móviles",
  "Elección Vocacional",
  "Introducción a las Ciencias Sociales",
  "La Mecánica y el Entorno",
  "La Naturaleza de la Vida",
  "Lógica",
  "Redes Neuronales y Aprendizaje Profundo",
  "Sistemas de Calidad",
];

export const MATERIAS: Materia[] = NOMBRES_MATERIAS.map((nombre, i) => ({
  id: `m${i + 1}`,
  nombre,
  profesor: i === 0 ? PROFESOR : null,
  periodo: PERIODO,
  sincronizada_en: i === 0 ? "2026-10-14T09:30:00" : null,
}));

type EtapaSeed = {
  nombre: string;
  descripcion: string;
  tareas: { titulo: string; puntos: number; tipo: "dimension" | "evidencia" | "examen" | "pia" }[];
};

const ETAPAS_BIO: EtapaSeed[] = [
  {
    nombre: "Etapa 1: Algoritmos Evolutivos",
    descripcion:
      "Identifica los algoritmos evolutivos y técnicas metaheurísticas, con el propósito de implementar mecanismos de optimización natural, a través del análisis de fundamentos biológicos y estrategias evolutivas.",
    tareas: [
      { titulo: "Dimensión 1 - Recuperación - Autoevaluación E1", puntos: 0, tipo: "dimension" },
      { titulo: "Dimensión 2 - Comprensión - Ficha Técnica", puntos: 2.5, tipo: "dimension" },
      { titulo: "Dimensión 3 - Análisis - Mapa mental", puntos: 2.5, tipo: "dimension" },
      { titulo: "Evidencia de Aprendizaje - Informe", puntos: 5, tipo: "evidencia" },
      { titulo: "Examen Etapa 1", puntos: 0, tipo: "examen" },
    ],
  },
  {
    nombre: "Etapa 2: Algoritmos Genéticos",
    descripcion:
      "Diseña estructuras de algoritmos genéticos, con el propósito de optimizar la búsqueda de soluciones en espacios complejos, a través de la configuración de operadores de selección, cruza y mutación.",
    tareas: [
      { titulo: "Dimensión 1 - Recuperación - Autoevaluación E2", puntos: 0, tipo: "dimension" },
      { titulo: "Dimensión 2 - Comprensión - Cuadro sinóptico", puntos: 2.5, tipo: "dimension" },
      { titulo: "Dimensión 3 - Análisis - Matriz de análisis", puntos: 2.5, tipo: "dimension" },
      { titulo: "Evidencia de Aprendizaje - Reporte de práctica", puntos: 5, tipo: "evidencia" },
    ],
  },
  {
    nombre: "Etapa 3: Inteligencia de Enjambre",
    descripcion:
      "Utiliza modelos de inteligencia colectiva y comportamientos emergentes, con el propósito de resolver problemas de optimización estocástica, a través de la implementación de algoritmos de partículas y colonias de abejas.",
    tareas: [
      { titulo: "Dimensión 1 - Recuperación - Autoevaluación E3", puntos: 0, tipo: "dimension" },
      { titulo: "Dimensión 2 - Comprensión - Diagrama de flujo", puntos: 2.5, tipo: "dimension" },
      { titulo: "Dimensión 3 - Análisis - Matriz de análisis", puntos: 2.5, tipo: "dimension" },
      { titulo: "Evidencia de Aprendizaje - Reporte de práctica", puntos: 5, tipo: "evidencia" },
    ],
  },
  {
    nombre: "Etapa 4: Colonia de Hormigas",
    descripcion:
      "Desarrolla sistemas de optimización basados en grafos, con el propósito de determinar trayectorias y soluciones eficientes en redes, a través del modelado de feromonas y el algoritmo de colonia de hormigas.",
    tareas: [
      { titulo: "Dimensión 1 - Recuperación - Autoevaluación E4", puntos: 0, tipo: "dimension" },
      { titulo: "Dimensión 2 - Comprensión - Cuadro sinóptico", puntos: 2.5, tipo: "dimension" },
      { titulo: "Dimensión 3 - Análisis - Matriz de análisis", puntos: 2.5, tipo: "dimension" },
      { titulo: "Evidencia de Aprendizaje - Reporte de práctica", puntos: 5, tipo: "evidencia" },
    ],
  },
  {
    nombre: "Producto Integrador de Aprendizaje",
    descripcion: "",
    tareas: [{ titulo: "PIA - Informe", puntos: 10, tipo: "pia" }],
  },
];

const ETAPAS_GENERICAS: EtapaSeed[] = [
  {
    nombre: "Etapa 1",
    descripcion: "Primera etapa de la unidad de aprendizaje.",
    tareas: [
      { titulo: "Dimensión 1 - Recuperación - Autoevaluación E1", puntos: 0, tipo: "dimension" },
      { titulo: "Dimensión 2 - Comprensión - Ficha Técnica", puntos: 2.5, tipo: "dimension" },
      { titulo: "Dimensión 3 - Análisis - Mapa mental", puntos: 2.5, tipo: "dimension" },
      { titulo: "Evidencia de Aprendizaje - Informe", puntos: 5, tipo: "evidencia" },
    ],
  },
  {
    nombre: "Producto Integrador de Aprendizaje",
    descripcion: "",
    tareas: [{ titulo: "PIA - Informe", puntos: 10, tipo: "pia" }],
  },
];

const OFFSETS = [-10, -3, 0, 2, 5, 9, 14, 21, 30, 45];

function pad(n: number) {
  return String(n).padStart(2, "0");
}

export function isoLocal(offsetDias: number, h = 23, m = 59): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDias);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(h)}:${pad(m)}:00`;
}

export function marcarVencida(t: Tarea) {
  t.vencida = t.estado !== "entregada" && !!t.hasta && new Date(t.hasta).getTime() < Date.now();
}

function construirEtapas(materiaId: string, mi: number, seeds: EtapaSeed[]): EtapaConTareas[] {
  let k = 0;
  return seeds.map((seed, ei) => {
    const etapaId = `${materiaId}-e${ei + 1}`;
    const esPia = seed.nombre.startsWith("Producto");
    const tareas: Tarea[] = seed.tareas
      .map((t, ti) => ({ t, ti }))
      .filter(({ t }) => !t.titulo.includes("Autoevaluación"))
      .map(({ t, ti }): Tarea => {
        const numero = esPia ? "PIA" : `${ei + 1}.${ti + 1}`;
        const offset = OFFSETS[(k + mi) % OFFSETS.length];
        const entregada = mi === 0 && k === 0;
        k += 1;
        const tarea: Tarea = {
          id: `${materiaId}-t${ei + 1}${ti + 1}`,
          etapa_id: etapaId,
          materia_id: materiaId,
          numero,
          titulo: t.titulo,
          tipo: t.tipo,
          desde: isoLocal(offset - 30, 0, 0),
          hasta: isoLocal(offset),
          puntos: t.puntos,
          modalidad: "Individual",
          estado: entregada ? "entregada" : "pendiente",
          entregada_en: entregada ? isoLocal(-11, 18, 30) : null,
          vencida: false,
        };
        marcarVencida(tarea);
        return tarea;
      });
    return {
      id: etapaId,
      materia_id: materiaId,
      nombre: seed.nombre,
      descripcion: seed.descripcion,
      tareas,
    };
  });
}

export function crearEtapas(): Record<string, EtapaConTareas[]> {
  const out: Record<string, EtapaConTareas[]> = {};
  MATERIAS.forEach((m, i) => {
    out[m.id] = construirEtapas(m.id, i, i === 0 ? ETAPAS_BIO : ETAPAS_GENERICAS);
  });
  return out;
}

export const RUBRICA: Rubrica = {
  niveles: ["Evidencia Completa", "Evidencia Suficiente", "Evidencia Débil", "Sin Evidencia"],
  criterios: [
    {
      criterio: "Demuestra y relaciona correctamente los conceptos clave en la representación del problema.",
      niveles: [
        {
          puntos: 2,
          descripcion:
            "Demuestra un dominio de los conceptos de optimización, espacio de búsqueda, funciones matemáticas y teoría de grafos, estableciendo correctamente la relación entre ellos para representar el problema planteado.",
        },
        {
          puntos: 1.5,
          descripcion:
            "Demuestra comprensión de la mayoría de los conceptos fundamentales, aunque presenta algunas imprecisiones menores en la relación entre los elementos del problema y su representación.",
        },
        {
          puntos: 1,
          descripcion:
            "El informe evidencia conocimientos parciales o presenta errores conceptuales que dificultan la comprensión del modelo propuesto.",
        },
        { puntos: 0, descripcion: "Sin Evidencia" },
      ],
    },
    {
      criterio:
        "Estructura correctamente el problema de optimización y justifica con coherencia su modelado matemático y gráfico.",
      niveles: [
        {
          puntos: 2,
          descripcion:
            "Formaliza correctamente el problema de optimización identificando objetivo, variables, restricciones y espacio de búsqueda. La representación mediante funciones matemáticas y teoría de grafos es adecuada, coherente y está debidamente justificada.",
        },
        {
          puntos: 1.5,
          descripcion:
            "Formaliza el problema e integra la mayoría de los elementos requeridos; la representación presenta pequeñas inconsistencias, pero permite comprender el modelo propuesto.",
        },
        {
          puntos: 1,
          descripcion:
            "La formalización del problema es incompleta o presenta errores importantes en la representación mediante funciones o grafos, afectando la interpretación del modelo.",
        },
        { puntos: 0, descripcion: "Sin Evidencia" },
      ],
    },
    {
      criterio: "Muestra compromiso y responsabilidad en la realización del trabajo.",
      niveles: [
        {
          puntos: 1,
          descripcion:
            "Entrega el informe en el tiempo establecido, con excelente organización, redacción, presentación y formato, incluyendo todos los apartados solicitados.",
        },
        {
          puntos: 0.75,
          descripcion:
            "Entrega el informe con ligeros detalles de organización, presentación o formato, sin afectar significativamente su comprensión.",
        },
        {
          puntos: 0.5,
          descripcion:
            "El informe presenta deficiencias importantes de organización, formato o redacción, o es entregado fuera del tiempo establecido.",
        },
        { puntos: 0, descripcion: "Sin Evidencia" },
      ],
    },
  ],
};

const CONTENIDO_E1 = [
  "Contenido Conceptual:",
  "- Introducción a Algoritmos Evolutivos",
  "- Historia",
  "- Aplicaciones",
  "- Algoritmos evolutivos y biología",
  "- Programación Evolutiva",
  "- Técnicas metaheurísticas",
  "- Estrategias Evolutivas",
  "",
  "Contenido Procedimental:",
  "- Analizar los antecedentes y fundamentos biológicos de la computación evolutiva para comprender su origen y aplicaciones.",
  "- Identificar las características de las técnicas metaheurísticas para diferenciar su uso en problemas de búsqueda y optimización.",
  "- Comparar la programación evolutiva con las estrategias evolutivas para seleccionar la técnica adecuada según el entorno del problema.",
  "",
  "Contenido Actitudinal:",
  "- Demuestra responsabilidad.",
  "- Trabaja en equipo.",
  "- Acepta las ideas de sus compañeros.",
  "- Muestra la capacidad de trabajo autónomo.",
].join("\n");

const CRITERIOS_E1 = [
  "- Identifica los fundamentos evolutivos, mediante el análisis de su historia y bases biológicas.",
  "- Distingue diversas técnicas metaheurísticas, a través de la comparación de sus mecanismos de búsqueda.",
  "- Relaciona la programación y estrategias evolutivas, por medio del estudio de sus diferencias conceptuales.",
].join("\n");

const ACTIVIDAD_FICHA =
  "Explora diferentes funciones matemáticas utilizando herramientas computacionales para generar representaciones gráficas. A partir de la observación e interpretación de las gráficas, identifica el espacio de búsqueda, los máximos y mínimos locales y globales, así como los elementos que caracterizan un problema de optimización. Finalmente, organiza y explica los conceptos adquiridos mediante la elaboración de una ficha técnica del espacio de búsqueda y optimización, integrando definiciones construidas con sus propias palabras, representaciones gráficas e interpretaciones que evidencien la comprensión de los fundamentos de la optimización en el contexto de los algoritmos evolutivos.";

export function detalleDe(tarea: Tarea): TareaDetalle {
  const esFicha = tarea.numero === "1.2";
  return {
    ...tarea,
    actividades: esFicha
      ? ACTIVIDAD_FICHA
      : `Desarrolla la actividad «${tarea.titulo}» siguiendo las indicaciones del curso y entrega el resultado en formato PDF.`,
    contenido: CONTENIDO_E1,
    criterios_desempeno: CRITERIOS_E1,
    rubrica: tarea.tipo === "evidencia" || tarea.tipo === "pia" ? RUBRICA : null,
  };
}
