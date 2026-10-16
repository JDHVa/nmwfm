import type {
  EventoChat,
  Novedad,
  Respaldo,
  EtapaConTareas,
  Generacion,
  Insumo,
  Job,
  JobTipo,
  Settings,
  Socket,
  Transport,
  WsMessage,
} from "@/lib/api";
import { MATERIAS, crearEtapas, detalleDe, marcarVencida } from "./data";

type Emitter = (msg: WsMessage) => void;

export type MockOptions = { stepMs?: number; asistenteDisponible?: boolean };

function svgDataUrl(label: string, hue: number, w = 420, h = 560): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="100%" height="100%" fill="hsl(${hue},30%,92%)"/><rect x="24" y="24" width="${w - 48}" height="${h - 48}" fill="white" stroke="hsl(${hue},40%,60%)" stroke-width="3"/>${Array.from({ length: 9 }, (_, i) => `<rect x="48" y="${64 + i * 40}" width="${120 + ((i * 53) % 200)}" height="10" fill="hsl(${hue},25%,70%)"/>`).join("")}<text x="48" y="${h - 48}" font-family="sans-serif" font-size="22" fill="hsl(${hue},40%,35%)">${label}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function minimalPdf(lines: string[]): Uint8Array {
  const esc = (s: string) => s.replace(/[\\()]/g, "\\$&").replace(/[^\x20-\x7e]/g, "?");
  const content = `BT /F1 14 Tf 56 760 Td 18 TL ${lines.map((l) => `(${esc(l)}) '`).join(" ")} ET`;
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objs.forEach((o, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  offsets.forEach((o) => {
    out += `${String(o).padStart(10, "0")} 00000 n \n`;
  });
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new TextEncoder().encode(out);
}

function pdfDe(lineas: string[]): string {
  const bytes = minimalPdf(lineas);
  const buf = new ArrayBuffer(bytes.length);
  new Uint8Array(buf).set(bytes);
  return URL.createObjectURL(new Blob([buf], { type: "application/pdf" }));
}

function pdfUrl(titulo: string): string {
  const bytes = minimalPdf([
    "Universidad Autonoma de Nuevo Leon",
    titulo,
    "",
    "Documento de ejemplo generado por el servicio simulado.",
    "Aqui apareceria el contenido redactado por Gemini.",
  ]);
  const buf = new ArrayBuffer(bytes.length);
  new Uint8Array(buf).set(bytes);
  return URL.createObjectURL(new Blob([buf], { type: "application/pdf" }));
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => resolve(svgDataUrl(file.name, 200));
    reader.readAsDataURL(file);
  });
}

export function createMockBackend(options: MockOptions = {}) {
  const stepMs = options.stepMs ?? 700;
  const asistenteDisponible = options.asistenteDisponible ?? true;
  let settings: Settings = {
    cuenta: "",
    tiene_password: false,
    nombre: "",
    matricula: "",
    dev: true,
    entregar_sin_revisar: false,
    reducir_animaciones: false,
    sync_cada_horas: 0,
    asistente_modelo: "qwen3:4b",
    sync_inicial_hecha: false,
    ultima_sync: null,
  };
  const materias = MATERIAS.map((m) => ({ ...m }));
  const etapas = crearEtapas();
  const insumos = new Map<string, Insumo[]>();
  const generaciones = new Map<string, Generacion>();
  const historial = new Map<string, Generacion[]>();
  let genSeq = 0;
  const registrar = (g: Omit<Generacion, "id" | "avisos"> & { avisos?: string[] }): Generacion => {
    const completa: Generacion = { avisos: [], ...g, id: ++genSeq };
    generaciones.set(g.tarea_id, completa);
    historial.set(g.tarea_id, [completa, ...(historial.get(g.tarea_id) ?? [])]);
    return completa;
  };
  const jobs = new Map<string, Job>();
  const emitters = new Set<Emitter>();
  let password = "";
  const novedades: Novedad[] = [];
  const sembrarNovedades = () => {
    if (novedades.length) return;
    const ahora = Date.now();
    [
      ["m1-t13", "nueva", 2, "Tarea nueva en NEXUS"],
      ["m1-t14", "modificada", 26, "Cambió la fecha de entrega"],
      ["m2-t12", "nueva", 50, "Tarea nueva en NEXUS"],
    ].forEach(([id, tipo, horas, detalle], i) => {
      const t = buscarTarea(id as string);
      if (!t) return;
      novedades.push({
        id: i + 1,
        tarea_id: t.id,
        materia_id: t.materia_id,
        materia_nombre: materias.find((x) => x.id === t.materia_id)?.nombre ?? "",
        numero: t.numero,
        titulo: t.titulo,
        tipo: tipo as "nueva" | "modificada",
        detalle: detalle as string,
        creada_en: new Date(ahora - (horas as number) * 3_600_000).toISOString(),
        leida: false,
      });
    });
  };
  const respaldos: Respaldo[] = [];
  const indicaciones = new Map<string, string>();
  const confirmaciones = new Map<string, string>();
  let syncActivo: string | null = null;
  let revisionActiva: string | null = null;
  let seq = 0;
  let hue = 200;

  const emit = (msg: WsMessage) => emitters.forEach((e) => e(msg));
  const log = (level: string, message: string) => emit({ type: "log", level, message });

  function buscarTarea(id: string) {
    for (const lista of Object.values(etapas)) {
      for (const e of lista) {
        const t = e.tareas.find((x) => x.id === id);
        if (t) return t;
      }
    }
    return undefined;
  }

  function lanzarJob(
    tipo: JobTipo,
    pasos: string[],
    alTerminar?: () => unknown,
    rechazo?: () => string | null,
    ritmo = 1,
  ): Job {
    const job: Job = {
      id: `job-${++seq}`,
      tipo,
      estado: "en_cola",
      paso: "En cola",
      progreso: 0,
      mensaje: null,
      resultado: null,
    };
    jobs.set(job.id, job);
    let i = 0;
    const tick = () => {
      if (i < pasos.length) {
        job.estado = "corriendo";
        job.paso = pasos[i];
        job.progreso = Math.round((i / pasos.length) * 100);
        log("info", pasos[i]);
        emit({ type: "job", job: { ...job } });
        i += 1;
        setTimeout(tick, stepMs * ritmo);
      } else {
        const motivo = rechazo?.() ?? null;
        if (motivo) {
          job.estado = "error";
          job.paso = "Error";
          job.mensaje = motivo;
          log("error", motivo);
          emit({ type: "job", job: { ...job } });
          return;
        }
        job.resultado = alTerminar?.() ?? null;
        job.estado = "ok";
        job.paso = "Terminado";
        job.progreso = 100;
        if (tipo === "entregar") job.mensaje = "La Tarea ha sido cargada y entregada con éxito";
        log("info", `Trabajo ${tipo} terminado`);
        emit({ type: "job", job: { ...job } });
      }
    };
    setTimeout(tick, 30);
    return { ...job };
  }

  function ordenar(lista: Insumo[]) {
    lista.sort((a, b) => a.orden - b.orden);
  }

  const sse = (eventos: EventoChat[]) => {
    const encoder = new TextEncoder();
    let i = 0;
    const stream = new ReadableStream<Uint8Array>({
      async pull(controller) {
        if (i >= eventos.length) {
          controller.close();
          return;
        }
        const e = eventos[i++];
        await new Promise((r) => setTimeout(r, Math.max(1, Math.round(stepMs / 4))));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(e)}\n\n`));
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  };

  const palabras = (texto: string): EventoChat[] =>
    texto.split(/(?<=\s)/).map((p) => ({ type: "token", text: p }));

  const sinAcentos = (t: string) =>
    t
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();

  function todasLasTareas() {
    return Object.values(etapas)
      .flat()
      .flatMap((e) => e.tareas);
  }

  function guionAsistente(texto: string, tareaId?: string): EventoChat[] {
    const q = sinAcentos(texto);
    const fin: EventoChat = { type: "fin" };
    if (/vence|semana|proxim/.test(q)) {
      const pendientes = todasLasTareas()
        .filter((t) => t.estado !== "entregada" && !t.vencida && t.hasta)
        .sort((a, b) => new Date(a.hasta!).getTime() - new Date(b.hasta!).getTime())
        .slice(0, 4);
      const lista = pendientes.map((t) => `- **${t.numero}** ${t.titulo}`).join("\n");
      return [
        { type: "tool_call", nombre: "proximas_entregas", args: { dias: 7 } },
        {
          type: "tool_result",
          nombre: "proximas_entregas",
          resultado: pendientes.map((t) => ({
            id: t.id,
            numero: t.numero,
            titulo: t.titulo,
            hasta: t.hasta,
          })),
        },
        ...palabras(
          `Estas son tus próximas entregas:\n\n${lista}\n\nLa más urgente es la **${pendientes[0]?.numero ?? "-"}**.`,
        ),
        fin,
      ];
    }
    if (/equipo|indicaci/.test(q)) {
      const objetivo =
        todasLasTareas().find((t) => t.numero === "2.3" && t.materia_id === "m1") ?? todasLasTareas()[0];
      const nota = texto.trim();
      indicaciones.set(objetivo.id, [indicaciones.get(objetivo.id), nota].filter(Boolean).join("\n"));
      return [
        { type: "tool_call", nombre: "agregar_indicaciones", args: { tarea_id: objetivo.id, texto: nota } },
        {
          type: "tool_result",
          nombre: "agregar_indicaciones",
          resultado: { ok: true, tarea_id: objetivo.id },
        },
        ...palabras(
          `Listo, guardé esa indicación en la tarea **${objetivo.numero} ${objetivo.titulo}**. Tendrá prioridad sobre la descripción de NEXUS al generar.`,
        ),
        fin,
      ];
    }
    if (/explic|1\.4/.test(q)) {
      const objetivo = todasLasTareas().find((t) => t.numero === "1.4" && t.materia_id === "m1")!;
      return [
        { type: "tool_call", nombre: "buscar_tareas", args: { consulta: "1.4 Algoritmos" } },
        {
          type: "tool_result",
          nombre: "buscar_tareas",
          resultado: [{ id: objetivo.id, numero: objetivo.numero, titulo: objetivo.titulo }],
        },
        { type: "tool_call", nombre: "ver_tarea", args: { tarea_id: objetivo.id } },
        {
          type: "tool_result",
          nombre: "ver_tarea",
          resultado: { titulo: objetivo.titulo, puntos: objetivo.puntos, hasta: objetivo.hasta },
        },
        ...palabras(
          `La **${objetivo.numero} ${objetivo.titulo}** vale ${objetivo.puntos} puntos.\n\n1. Revisa el contenido de la etapa.\n2. Redacta el informe con los criterios de la rúbrica.\n3. Entrega el PDF antes de la fecha límite.`,
        ),
        fin,
      ];
    }
    if (/entreg/.test(q)) {
      const objetivo = (tareaId && buscarTarea(tareaId)) || todasLasTareas()[1];
      const id = `conf-${++seq}`;
      confirmaciones.set(id, objetivo.id);
      return [
        ...palabras("Puedo entregarla, pero necesito tu confirmación."),
        {
          type: "confirmar",
          accion: "entregar_tarea",
          args: { tarea_id: objetivo.id, titulo: `${objetivo.numero} ${objetivo.titulo}` },
          id,
        },
        fin,
      ];
    }
    if (/portada|profe/.test(q)) {
      const profesor = /profe\w*\s+([^.,]+)/i.exec(texto)?.[1]?.trim() ?? "el profesor";
      const pdf = pdfDe(["Portada", `Profesor: ${profesor}`]);
      return [
        { type: "tool_call", nombre: "generar_portada", args: { profesor } },
        {
          type: "tool_result",
          nombre: "generar_portada",
          resultado: { docx_url: "/files/portada-suelta.docx", pdf_url: pdf },
        },
        ...palabras(`Preparé la portada para **${profesor}**: [Descargar PDF](${pdf}).`),
        fin,
      ];
    }
    if (/pdf|foto|imagen/.test(q)) {
      return [...palabras("Adjunta las imágenes con el clip del chat y las convierto en un solo PDF."), fin];
    }
    return [
      ...palabras(
        "Soy el asistente simulado. Puedo **buscar tareas**, explicarlas, guardar indicaciones del profesor, crear PDFs y portadas.",
      ),
      fin,
    ];
  }

  const json = (data: unknown, status = 200) =>
    new Response(status === 204 ? null : JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const fallo = (status: number, code: string, message: string) => json({ error: { code, message } }, status);

  const transport: Transport = async (url, init) => {
    const method = (init.method ?? "GET").toUpperCase();
    const path = new URL(url).pathname;
    const headers = new Headers(init.headers);
    if (headers.get("X-Token") !== "dev") return fallo(401, "token_invalido", "Token inválido");
    const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
    let m: RegExpMatchArray | null;

    if (path === "/health") return json({ ok: true, version: "mock" });
    if ((m = path.match(/^\/tareas\/([^/]+)\/indicaciones$/)) && method === "PUT") {
      const t = buscarTarea(m[1]);
      if (!t) return fallo(404, "no_encontrada", "Tarea no encontrada");
      indicaciones.set(t.id, (body as { indicaciones: string }).indicaciones);
      return json({ ...detalleDe(t), indicaciones: indicaciones.get(t.id) });
    }
    if (path === "/asistente/estado") {
      return json({
        ollama: asistenteDisponible,
        modelo: settings.asistente_modelo ?? "qwen3:4b",
        modelo_instalado: asistenteDisponible,
        error: asistenteDisponible ? null : "No se pudo conectar con Ollama en 127.0.0.1:11434",
      });
    }
    if (path === "/asistente/confirmar") {
      const { id, aceptar } = body as { id: string; aceptar: boolean };
      const tareaId = confirmaciones.get(id);
      if (!tareaId) return fallo(404, "no_encontrada", "La confirmación ya no existe");
      confirmaciones.delete(id);
      if (!aceptar) return json({ ok: true, mensaje: "Acción cancelada" });
      const t = buscarTarea(tareaId);
      if (t) {
        t.estado = "entregada";
        t.entregada_en = new Date().toISOString();
      }
      return json({ ok: true, mensaje: "La tarea se entregó en NEXUS" });
    }
    if (path === "/asistente/chat") {
      if (!asistenteDisponible) return fallo(503, "sin_ollama", "El asistente no está disponible");
      const { mensajes, tarea_id } = body as {
        mensajes: { rol: string; contenido: string }[];
        tarea_id?: string;
      };
      const ultimo = [...mensajes].reverse().find((x) => x.rol === "user")?.contenido ?? "";
      return sse(guionAsistente(ultimo, tarea_id));
    }
    if (path === "/herramientas/pdf") {
      const form = body as FormData;
      const n = form.getAll("files[]").length;
      if (n === 0) return fallo(400, "sin_archivos", "Sube al menos una imagen");
      return json({
        pdf_url: pdfDe(["Imagenes unidas", `${n} imagen(es)`, `Recorte: ${form.get("recortar")}`]),
      });
    }
    if (path === "/herramientas/portada") {
      const d = body as { profesor: string; materia?: string; titulo?: string; fecha?: string };
      return json({
        docx_url: "/files/portada-suelta.docx",
        pdf_url: pdfDe([
          "Universidad Autonoma de Nuevo Leon",
          "",
          d.titulo ?? "",
          d.materia ?? "",
          `Alumno: ${settings.nombre}`,
          `Matricula: ${settings.matricula}`,
          `Profesor: ${d.profesor}`,
          `Fecha: ${d.fecha ?? new Date().toLocaleDateString("es-MX")}`,
        ]),
      });
    }
    if (path === "/settings" && method === "GET") return json(settings);
    if (path === "/settings" && method === "PUT") {
      const { password: nueva, ...rest } = body as Partial<Settings> & { password?: string };
      if (nueva) password = nueva;
      settings = { ...settings, ...rest, tiene_password: password !== "" };
      return json(settings);
    }
    if (path === "/siase/validar") {
      return json(
        lanzarJob("validar_siase", ["Abriendo SIASE", "Verificando credenciales"], undefined, () =>
          !settings.cuenta || !password || password === "mala"
            ? "La cuenta o la contraseña son incorrectas"
            : null,
        ),
      );
    }
    if (path === "/gemini/login") {
      return json(
        lanzarJob("login_gemini", [
          "Abriendo Chrome",
          "Esperando inicio de sesión en Gemini",
          "Sesión detectada",
        ]),
      );
    }
    if (path === "/sync") {
      if (!settings.cuenta || !settings.tiene_password) {
        return fallo(400, "sin_credenciales", "Configura tu cuenta y contraseña antes de sincronizar");
      }
      const activo = syncActivo && jobs.get(syncActivo);
      if (activo && (activo.estado === "en_cola" || activo.estado === "corriendo")) return json(activo);
      const pedido = (body as { modo?: string } | undefined)?.modo ?? "auto";
      const completo = pedido === "completo" || (pedido === "auto" && !settings.sync_inicial_hecha);
      const pasos = completo
        ? [
            "Iniciando sesión en SIASE",
            "Entrando a NEXUS",
            "Leyendo materias",
            ...materias.map(
              (m, i) => `Leyendo detalle de tareas · ${i + 1} de ${materias.length}: ${m.nombre}`,
            ),
          ]
        : ["Iniciando sesión en SIASE", "Revisando cambios en NEXUS"];
      const job = lanzarJob(
        "sync",
        pasos,
        () => {
          const ahora = new Date().toISOString();
          materias.forEach((x) => (x.sincronizada_en = ahora));
          settings = { ...settings, sync_inicial_hecha: true, ultima_sync: ahora };
          const tareas = Object.values(etapas)
            .flat()
            .reduce((n, e) => n + e.tareas.length, 0);
          return {
            materias: materias.length,
            tareas,
            detalles_leidos: completo ? tareas : 0,
            nuevas: 0,
            errores: [],
          };
        },
        undefined,
        completo ? 1 : 0.3,
      );
      syncActivo = job.id;
      return json(job);
    }
    if (path === "/respaldo" && method === "GET") return json([...respaldos].reverse());
    if (path === "/respaldo" && method === "POST") {
      const n = respaldos.length + 1;
      const nombre = `respaldo-20261015-12${String(n).padStart(2, "0")}00.zip`;
      const r = {
        nombre,
        url: `/files/respaldos/${nombre}`,
        bytes: 1_250_000 + n * 4000,
        creado_en: new Date().toISOString(),
      };
      respaldos.push(r);
      log("info", "Respaldo creado");
      return json(r);
    }
    if (path === "/respaldo/restaurar") {
      const nombre = (body as { nombre?: string } | undefined)?.nombre;
      if (!respaldos.some((r) => r.nombre === nombre)) {
        return fallo(400, "respaldo_invalido", "El respaldo no existe o no es válido");
      }
      log("info", "Respaldo restaurado");
      return json({ restaurados: 42, respaldo_previo: "pre-restauracion-20261015-121500.zip" });
    }
    if (path === "/diagnostico") {
      return json(
        lanzarJob(
          "diagnostico",
          [
            "Abriendo NEXUS",
            "Comprobando selectores de materias",
            "Comprobando selectores de tareas",
            "Comprobando pestaña Entregas",
          ],
          () => ({
            ok: false,
            pasos: [
              {
                nombre: "Inicio de sesión en SIASE",
                ok: true,
                ms: 2300,
                detalle: "Entró correctamente",
                selectores_faltantes: [],
              },
              {
                nombre: "Lista de materias",
                ok: true,
                ms: 1800,
                detalle: "10 materias encontradas",
                selectores_faltantes: [],
              },
              {
                nombre: "Estructura de etapas",
                ok: true,
                ms: 950,
                detalle: "5 etapas en la primera materia",
                selectores_faltantes: [],
              },
              {
                nombre: "Pestaña Entregas",
                ok: false,
                ms: 3100,
                detalle: "No se encontró el botón «Entregar» (selector desactualizado)",
                selectores_faltantes: ["button.entregar"],
              },
            ],
          }),
        ),
      );
    }
    if (path === "/novedades" && method === "GET") {
      sembrarNovedades();
      const soloNuevas = new URL(url).searchParams.get("no_leidas") === "1";
      return json(soloNuevas ? novedades.filter((n) => !n.leida) : novedades);
    }
    if (path === "/novedades/leidas") {
      const ids = (body as { ids?: number[] } | undefined)?.ids;
      let marcadas = 0;
      novedades.forEach((n) => {
        if ((!ids || ids.includes(n.id)) && !n.leida) {
          n.leida = true;
          marcadas += 1;
        }
      });
      return json({ marcadas });
    }
    if (path === "/alertas") {
      const ahora = new Date();
      const inicio = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
      const lista = Object.values(etapas)
        .flat()
        .flatMap((e) => e.tareas)
        .filter((t) => t.estado !== "entregada" && t.hasta && new Date(t.hasta).getTime() >= ahora.getTime())
        .map((t) => ({ t, dias: Math.round((inicio(new Date(t.hasta!)) - inicio(ahora)) / 86_400_000) }))
        .filter(({ dias }) => dias <= 1)
        .map(({ t, dias }) => ({
          ...t,
          materia_nombre: materias.find((x) => x.id === t.materia_id)?.nombre ?? "",
          dias,
        }));
      return json(lista);
    }
    if (path === "/tareas/proximas") {
      const todas = Object.values(etapas)
        .flat()
        .flatMap((e) =>
          e.tareas.map((t) => {
            marcarVencida(t);
            return { ...t, materia_nombre: materias.find((x) => x.id === t.materia_id)?.nombre ?? "" };
          }),
        );
      const pendientes = todas.filter((t) => t.estado !== "entregada");
      const t = (x: { hasta: string | null }) => new Date(x.hasta ?? 0).getTime();
      const vigentes = pendientes.filter((x) => !x.vencida).sort((a, b) => t(a) - t(b));
      const vencidas = pendientes.filter((x) => x.vencida).sort((a, b) => t(a) - t(b));
      return json([...vigentes, ...vencidas]);
    }
    if (path === "/entregas/revisar") {
      const activo = revisionActiva && jobs.get(revisionActiva);
      if (activo && (activo.estado === "en_cola" || activo.estado === "corriendo")) return json(activo);
      const job = lanzarJob(
        "revisar_entregas",
        [
          "Abriendo NEXUS",
          ...materias.map((_, i) => `Revisando entregas · materia ${i + 1}/${materias.length}`),
        ],
        () => {
          const todas = Object.values(etapas)
            .flat()
            .flatMap((e) => e.tareas);
          const entregadas = todas.filter((x) => x.estado === "entregada").length;
          return { revisadas: todas.length, entregadas, pendientes: todas.length - entregadas, errores: [] };
        },
        undefined,
        0.5,
      );
      revisionActiva = job.id;
      return json(job);
    }
    if (path === "/materias") return json(materias);
    if ((m = path.match(/^\/materias\/([^/]+)\/calificaciones$/))) {
      const lista = etapas[m[1]];
      if (!lista) return fallo(404, "no_encontrada", "Materia no encontrada");
      if (m[1] !== "m1") return json(null);
      const filas = lista.flatMap((e) =>
        e.tareas
          .filter((t) => t.tipo !== "examen" && t.puntos)
          .map((t) => [
            `${t.numero} ${t.titulo}`,
            t.estado === "entregada" ? String(Math.round(t.puntos! * 0.9 * 10) / 10) : "-",
            String(t.puntos),
          ]),
      );
      return json({
        columnas: ["Actividad", "Calificación", "Puntos"],
        filas,
        actualizada_en: new Date().toISOString(),
      });
    }
    if ((m = path.match(/^\/materias\/([^/]+)\/etapas$/))) {
      const lista = etapas[m[1]];
      lista?.forEach((e) => e.tareas.forEach(marcarVencida));
      return lista ? json(lista) : fallo(404, "no_encontrada", "Materia no encontrada");
    }
    if ((m = path.match(/^\/tareas\/([^/]+)$/))) {
      const t = buscarTarea(m[1]);
      if (t) marcarVencida(t);
      return t
        ? json({ ...detalleDe(t), indicaciones: indicaciones.get(t.id) ?? "" })
        : fallo(404, "no_encontrada", "Tarea no encontrada");
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/insumos$/))) {
      const id = m[1];
      const lista = insumos.get(id) ?? [];
      insumos.set(id, lista);
      if (method === "GET") {
        ordenar(lista);
        return json(lista);
      }
      const form = body as FormData;
      const files = form.getAll("files[]") as File[];
      const nuevos: Insumo[] = [];
      for (const f of files) {
        hue = (hue + 47) % 360;
        const original = f.type.startsWith("image/") ? await readAsDataUrl(f) : svgDataUrl(f.name, hue);
        nuevos.push({
          id: `ins-${++seq}`,
          tipo: "imagen",
          original_url: original,
          recortada_url: svgDataUrl(`${f.name} (recorte)`, hue, 360, 480),
          orden: lista.length + nuevos.length,
          rotacion: 0,
          usar_recorte: true,
          ocr_texto: `Texto detectado en ${f.name}: apuntes de clase, definiciones y un ejemplo resuelto.`,
        });
      }
      lista.push(...nuevos);
      log("info", `${nuevos.length} imagen(es) recortada(s)`);
      return json(nuevos);
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/insumos\/texto$/))) {
      const lista = insumos.get(m[1]) ?? [];
      insumos.set(m[1], lista);
      const nuevo: Insumo = {
        id: `ins-${++seq}`,
        tipo: "texto",
        texto: (body as { texto: string }).texto,
        orden: lista.length,
        rotacion: 0,
        usar_recorte: false,
      };
      lista.push(nuevo);
      return json(nuevo);
    }
    if ((m = path.match(/^\/insumos\/([^/]+)$/))) {
      for (const lista of insumos.values()) {
        const idx = lista.findIndex((x) => x.id === m![1]);
        if (idx < 0) continue;
        if (method === "DELETE") {
          lista.splice(idx, 1);
          lista.forEach((x, i) => (x.orden = i));
          return json(null, 204);
        }
        const patch = body as Partial<Insumo>;
        Object.assign(lista[idx], patch);
        if (patch.orden !== undefined) {
          const [item] = lista.splice(idx, 1);
          lista.splice(patch.orden, 0, item);
          lista.forEach((x, i) => (x.orden = i));
        }
        return json(lista.find((x) => x.id === m![1]));
      }
      return fallo(404, "no_encontrado", "Insumo no encontrado");
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/portada-preview$/))) {
      const t = buscarTarea(m[1]);
      if (!t) return fallo(404, "no_encontrada", "Tarea no encontrada");
      const materia = materias.find((x) => x.id === t.materia_id);
      return json({
        pdf_url: pdfDe([
          "Universidad Autonoma de Nuevo Leon",
          "",
          t.titulo,
          "",
          `Alumno: ${settings.nombre}`,
          `Matricula: ${settings.matricula}`,
          `Profesor: ${materia?.profesor ?? ""}`,
          `Fecha: ${new Date().toLocaleDateString("es-MX")}`,
        ]),
      });
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/generar$/))) {
      const t = buscarTarea(m[1]);
      if (!t) return fallo(404, "no_encontrada", "Tarea no encontrada");
      if (!insumos.get(t.id)?.length) {
        return fallo(400, "sin_insumos", "Agrega al menos un insumo antes de generar");
      }
      return json(
        lanzarJob(
          "generar",
          [
            "Uniendo insumos en PDF",
            "Enviando a Gemini",
            "Esperando respuesta",
            "Armando documento Word",
            "Convirtiendo a PDF",
            ...(settings.entregar_sin_revisar ? ["Entregando en NEXUS"] : []),
          ],
          () => {
            t.estado = settings.entregar_sin_revisar ? "entregada" : "generada";
            if (t.estado === "entregada") t.entregada_en = new Date().toISOString();
            registrar({
              tarea_id: t.id,
              markdown: `# ${t.titulo}`,
              docx_url: `/files/${t.id}.docx`,
              pdf_url: pdfUrl(t.titulo),
              creada_en: new Date().toISOString(),
            });
            return null;
          },
        ),
      );
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/generacion$/))) return json(generaciones.get(m[1]) ?? null);
    if ((m = path.match(/^\/tareas\/([^/]+)\/generaciones$/))) {
      const actual = generaciones.get(m[1]);
      return json((historial.get(m[1]) ?? []).map((g) => ({ ...g, actual: actual?.id === g.id })));
    }
    if ((m = path.match(/^\/generaciones\/(\d+)\/restaurar$/))) {
      for (const lista of historial.values()) {
        const g = lista.find((x) => x.id === Number(m![1]));
        if (g) {
          generaciones.set(g.tarea_id, g);
          return json(g);
        }
      }
      return fallo(404, "no_encontrada", "Generación no encontrada");
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/abrir-docx$/))) {
      log("info", "Abriendo documento en Word");
      return json(null, 204);
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/reconstruir-pdf$/))) {
      const t = buscarTarea(m[1]);
      const actual = generaciones.get(m[1]);
      if (!t || !actual) return fallo(404, "sin_generacion", "Aún no hay un documento generado");
      const nueva = {
        ...actual,
        pdf_url: pdfUrl(`${t.titulo} (reconstruido)`),
        creada_en: new Date().toISOString(),
      };
      return json(registrar(nueva));
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/entregar$/))) {
      const t = buscarTarea(m[1]);
      if (!t) return fallo(404, "no_encontrada", "Tarea no encontrada");
      if (!(body as { confirmar?: boolean })?.confirmar)
        return fallo(400, "sin_confirmacion", "Falta confirmar");
      return json(
        lanzarJob("entregar", ["Abriendo NEXUS", "Subiendo PDF", "Confirmando entrega"], () => {
          t.estado = "entregada";
          t.entregada_en = new Date().toISOString();
          return null;
        }),
      );
    }
    if ((m = path.match(/^\/jobs\/([^/]+)$/))) {
      const j = jobs.get(m[1]);
      return j ? json(j) : fallo(404, "no_encontrado", "Trabajo no encontrado");
    }
    if ((m = path.match(/^\/jobs\/([^/]+)\/continuar$/))) {
      const j = jobs.get(m[1]);
      return j ? json(j) : fallo(404, "no_encontrado", "Trabajo no encontrado");
    }
    return fallo(404, "no_encontrado", `Ruta desconocida: ${path}`);
  };

  const createSocket = (): Socket => {
    const sock: Socket = {
      close: () => emitters.delete(handler),
      onmessage: null,
      onopen: null,
      onclose: null,
    };
    const handler: Emitter = (msg) => sock.onmessage?.({ data: JSON.stringify(msg) });
    emitters.add(handler);
    setTimeout(() => {
      sock.onopen?.();
      log("info", "Conectado al servicio simulado");
    }, 0);
    return sock;
  };

  return { transport, createSocket, etapas: etapas as Record<string, EtapaConTareas[]> };
}
