import type {
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
import { MATERIAS, crearEtapas, detalleDe } from "./data";

type Emitter = (msg: WsMessage) => void;

export type MockOptions = { stepMs?: number };

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
  let settings: Settings = {
    cuenta: "",
    tiene_password: false,
    nombre: "",
    matricula: "",
    dev: true,
    entregar_sin_revisar: false,
    reducir_animaciones: false,
  };
  const materias = MATERIAS.map((m) => ({ ...m }));
  const etapas = crearEtapas();
  const insumos = new Map<string, Insumo[]>();
  const generaciones = new Map<string, Generacion>();
  const jobs = new Map<string, Job>();
  const emitters = new Set<Emitter>();
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

  function lanzarJob(tipo: JobTipo, pasos: string[], alTerminar?: () => unknown): Job {
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
        setTimeout(tick, stepMs);
      } else {
        job.resultado = alTerminar?.() ?? null;
        job.estado = "ok";
        job.paso = "Terminado";
        job.progreso = 100;
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
    if (path === "/settings" && method === "GET") return json(settings);
    if (path === "/settings" && method === "PUT") {
      const { password, ...rest } = body as Partial<Settings> & { password?: string };
      settings = { ...settings, ...rest, tiene_password: password ? true : settings.tiene_password };
      return json(settings);
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
      return json(
        lanzarJob(
          "sync",
          ["Iniciando sesión en SIASE", "Entrando a NEXUS", "Leyendo materias", "Leyendo etapas y tareas"],
          () => {
            const ahora = new Date().toISOString();
            materias.forEach((x) => (x.sincronizada_en = ahora));
            return { materias: materias.length };
          },
        ),
      );
    }
    if (path === "/materias") return json(materias);
    if ((m = path.match(/^\/materias\/([^/]+)\/etapas$/))) {
      const lista = etapas[m[1]];
      return lista ? json(lista) : fallo(404, "no_encontrada", "Materia no encontrada");
    }
    if ((m = path.match(/^\/tareas\/([^/]+)$/))) {
      const t = buscarTarea(m[1]);
      return t ? json(detalleDe(t)) : fallo(404, "no_encontrada", "Tarea no encontrada");
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
            generaciones.set(t.id, {
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
      generaciones.set(m[1], nueva);
      return json(nueva);
    }
    if ((m = path.match(/^\/tareas\/([^/]+)\/entregar$/))) {
      const t = buscarTarea(m[1]);
      if (!t) return fallo(404, "no_encontrada", "Tarea no encontrada");
      if (!(body as { confirmar?: boolean })?.confirmar)
        return fallo(400, "sin_confirmacion", "Falta confirmar");
      return json(
        lanzarJob("entregar", ["Abriendo NEXUS", "Subiendo PDF", "Confirmando entrega"], () => {
          t.estado = "entregada";
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
