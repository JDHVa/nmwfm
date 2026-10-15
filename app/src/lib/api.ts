import { useEffect, useRef, useState } from "react";

export type Settings = {
  cuenta: string;
  tiene_password: boolean;
  nombre: string;
  matricula: string;
  dev: boolean;
  entregar_sin_revisar: boolean;
  reducir_animaciones: boolean;
  sync_inicial_hecha: boolean;
  ultima_sync: string | null;
};
export type SettingsUpdate = Partial<Settings> & { password?: string };
export type Materia = {
  id: string;
  nombre: string;
  profesor: string | null;
  periodo: string | null;
  sincronizada_en: string | null;
};
export type Etapa = { id: string; materia_id: string; nombre: string; descripcion: string };
export type EstadoTarea = "pendiente" | "generada" | "entregada";
export type Tarea = {
  id: string;
  etapa_id: string;
  materia_id: string;
  numero: string;
  titulo: string;
  tipo: "dimension" | "evidencia" | "examen" | "pia";
  desde: string | null;
  hasta: string | null;
  puntos: number | null;
  modalidad: string | null;
  estado: EstadoTarea;
  entregada_en: string | null;
  vencida: boolean;
};
export type TareaProxima = Tarea & { materia_nombre: string };
export type Rubrica = {
  niveles: string[];
  criterios: { criterio: string; niveles: { puntos: number; descripcion: string }[] }[];
};
export type TareaDetalle = Tarea & {
  actividades: string;
  contenido: string;
  criterios_desempeno: string;
  rubrica: Rubrica | null;
};
export type Insumo = {
  id: string;
  tipo: "imagen" | "texto";
  original_url?: string;
  miniatura_url?: string | null;
  recortada_url?: string;
  texto?: string;
  ocr_texto?: string | null;
  orden: number;
  rotacion: 0 | 90 | 180 | 270;
  usar_recorte: boolean;
};
export type InsumoPatch = Partial<
  Pick<Insumo, "orden" | "rotacion" | "usar_recorte" | "texto" | "ocr_texto">
>;
export type JobTipo = "sync" | "generar" | "entregar" | "login_gemini" | "validar_siase" | "revisar_entregas";
export type JobEstado = "en_cola" | "corriendo" | "esperando_usuario" | "ok" | "error";
export type Job = {
  id: string;
  tipo: JobTipo;
  estado: JobEstado;
  paso: string;
  progreso: number;
  mensaje: string | null;
  resultado: unknown;
};
export type PortadaPreview = {
  imagen_url: string;
  profesor: string;
  titulo: string;
  alumno: string;
  matricula: string;
  fecha: string;
};
export type PortadaOverrides = { profesor?: string; titulo?: string };
export type GeneracionVersion = {
  id: string;
  tarea_id: string;
  version: number;
  creada_en: string;
  pdf_url: string;
  docx_url: string;
  actual: boolean;
  resumen: string;
};
export type Recurso = {
  id: string;
  nombre: string;
  tipo: string;
  tamano: number | null;
  usar: boolean;
};
export type SyncModo = "auto" | "completo" | "incremental";
export type SyncResultado = {
  materias: number;
  tareas: number;
  detalles_leidos: number;
  nuevas: number;
  errores: string[];
};
export type RevisionResultado = {
  revisadas: number;
  entregadas: number;
  pendientes: number;
  errores: string[];
};
export type Generacion = {
  tarea_id: string;
  markdown: string;
  docx_url: string;
  pdf_url: string;
  creada_en: string;
};
export type EtapaConTareas = Etapa & { tareas: Tarea[] };
export type Health = { ok: boolean; version: string };
export type WsMessage = { type: "job"; job: Job } | { type: "log"; level: string; message: string };
export type BackendInfo = { port: number; token: string };

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export type Transport = (url: string, init: RequestInit) => Promise<Response>;

type Connection = { base: string; token: string; transport: Transport };

const defaultTransport: Transport = (url, init) => fetch(url, init);

let connection: Connection = { base: "http://127.0.0.1:8765", token: "dev", transport: defaultTransport };

export function configureApi(partial: Partial<Connection>) {
  connection = { ...connection, ...partial };
}

export function getConnection(): Readonly<Connection> {
  return connection;
}

export function fileUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (/^(https?:|blob:|data:)/.test(path)) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${connection.base}${path}${sep}token=${encodeURIComponent(connection.token)}`;
}

async function parseError(res: Response): Promise<ApiError> {
  let code = "http_error";
  let message = `Error ${res.status}`;
  try {
    const body = await res.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    message = res.statusText || message;
  }
  return new ApiError(res.status, code, message);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = path === "/health" ? {} : { "X-Token": connection.token };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await connection.transport(`${connection.base}${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "sin_conexion", "No se pudo conectar con el servicio local");
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("GET", "/health"),
  getSettings: () => request<Settings>("GET", "/settings"),
  putSettings: (data: SettingsUpdate) => request<Settings>("PUT", "/settings", data),
  loginGemini: () => request<Job>("POST", "/gemini/login"),
  revisarEntregas: () => request<Job>("POST", "/entregas/revisar"),
  proximas: () => request<TareaProxima[]>("GET", "/tareas/proximas"),
  validarSiase: () => request<Job>("POST", "/siase/validar"),
  sync: (modo: SyncModo = "auto") => request<Job>("POST", "/sync", { modo }),
  materias: () => request<Materia[]>("GET", "/materias"),
  etapas: (materiaId: string) => request<EtapaConTareas[]>("GET", `/materias/${materiaId}/etapas`),
  tarea: (id: string) => request<TareaDetalle>("GET", `/tareas/${id}`),
  insumos: (tareaId: string) => request<Insumo[]>("GET", `/tareas/${tareaId}/insumos`),
  subirImagenes: (tareaId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files[]", f, f.name));
    return request<Insumo[]>("POST", `/tareas/${tareaId}/insumos`, form);
  },
  agregarTexto: (tareaId: string, texto: string) =>
    request<Insumo>("POST", `/tareas/${tareaId}/insumos/texto`, { texto }),
  patchInsumo: (id: string, patch: InsumoPatch) => request<Insumo>("PATCH", `/insumos/${id}`, patch),
  borrarInsumo: (id: string) => request<void>("DELETE", `/insumos/${id}`),
  generar: (tareaId: string, instruccionesExtra?: string, portada?: PortadaOverrides) =>
    request<Job>("POST", `/tareas/${tareaId}/generar`, {
      instrucciones_extra: instruccionesExtra,
      ...(portada?.profesor ? { profesor: portada.profesor } : {}),
      ...(portada?.titulo ? { titulo: portada.titulo } : {}),
    }),
  portadaPreview: (tareaId: string, o: PortadaOverrides = {}) => {
    const q = new URLSearchParams();
    if (o.profesor) q.set("profesor", o.profesor);
    if (o.titulo) q.set("titulo", o.titulo);
    const qs = q.toString();
    return request<PortadaPreview>("GET", `/tareas/${tareaId}/portada-preview${qs ? `?${qs}` : ""}`);
  },
  generacion: (tareaId: string) => request<Generacion | null>("GET", `/tareas/${tareaId}/generacion`),
  generaciones: (tareaId: string) => request<GeneracionVersion[]>("GET", `/tareas/${tareaId}/generaciones`),
  restaurarGeneracion: (tareaId: string, id: string) =>
    request<Generacion>("POST", `/tareas/${tareaId}/generaciones/${id}/restaurar`),
  recursos: (tareaId: string) => request<Recurso[]>("GET", `/tareas/${tareaId}/recursos`),
  usarRecurso: (tareaId: string, id: string, usar: boolean) =>
    request<Recurso>("PATCH", `/tareas/${tareaId}/recursos/${id}`, { usar }),
  abrirDocx: (tareaId: string) => request<void>("POST", `/tareas/${tareaId}/abrir-docx`),
  reconstruirPdf: (tareaId: string) => request<Generacion>("POST", `/tareas/${tareaId}/reconstruir-pdf`),
  entregar: (tareaId: string) => request<Job>("POST", `/tareas/${tareaId}/entregar`, { confirmar: true }),
  job: (id: string) => request<Job>("GET", `/jobs/${id}`),
  continuarJob: (id: string) => request<Job>("POST", `/jobs/${id}/continuar`),
};

export type LogEntry = { id: number; level: string; message: string; at: number };

export interface Socket {
  close: () => void;
  onmessage: ((ev: { data: string }) => void) | null;
  onopen: (() => void) | null;
  onclose: (() => void) | null;
}

export type SocketFactory = (url: string) => Socket;

let socketFactory: SocketFactory = (url) => new WebSocket(url) as unknown as Socket;

export function configureSocket(factory: SocketFactory) {
  socketFactory = factory;
}

type Listener = (msg: WsMessage) => void;
const listeners = new Set<Listener>();
let socket: Socket | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;
let connected = false;
const statusListeners = new Set<(c: boolean) => void>();

function setConnected(value: boolean) {
  connected = value;
  statusListeners.forEach((l) => l(value));
}

function openSocket() {
  if (socket || listeners.size === 0) return;
  const wsBase = connection.base.replace(/^http/, "ws");
  const s = socketFactory(`${wsBase}/ws?token=${encodeURIComponent(connection.token)}`);
  socket = s;
  s.onopen = () => setConnected(true);
  s.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data) as WsMessage;
      listeners.forEach((l) => l(msg));
    } catch {
      return;
    }
  };
  s.onclose = () => {
    socket = null;
    setConnected(false);
    if (listeners.size > 0 && !retry) {
      retry = setTimeout(() => {
        retry = null;
        openSocket();
      }, 1500);
    }
  };
}

export function emitLocalLog(level: string, message: string) {
  listeners.forEach((l) => l({ type: "log", level, message }));
}

export function subscribeWs(listener: Listener): () => void {
  listeners.add(listener);
  openSocket();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      if (retry) clearTimeout(retry);
      retry = null;
      const s = socket;
      socket = null;
      s?.close();
      setConnected(false);
    }
  };
}

export function useWs(handler: Listener) {
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => subscribeWs((m) => ref.current(m)), []);
}

export function useWsStatus(): boolean {
  const [value, setValue] = useState(connected);
  useEffect(() => {
    statusListeners.add(setValue);
    return () => {
      statusListeners.delete(setValue);
    };
  }, []);
  return value;
}

const MAX_LOGS = 500;
let logSeq = 0;

export function useLogs(): { logs: LogEntry[]; clear: () => void } {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  useWs((m) => {
    if (m.type !== "log") return;
    setLogs((prev) =>
      [...prev, { id: ++logSeq, level: m.level, message: m.message, at: Date.now() }].slice(-MAX_LOGS),
    );
  });
  return { logs, clear: () => setLogs([]) };
}

export function useJobUpdates(jobId: string | null | undefined, onJob: (job: Job) => void) {
  const cb = useRef(onJob);
  useEffect(() => {
    cb.current = onJob;
  });
  useEffect(() => {
    if (!jobId) return;
    let alive = true;
    const unsub = subscribeWs((m) => {
      if (m.type === "job" && m.job.id === jobId) cb.current(m.job);
    });
    const check = async () => {
      try {
        const j = await api.job(jobId);
        if (alive) cb.current(j);
      } catch {
        return;
      }
    };
    const first = setTimeout(check, 300);
    const poll = setInterval(check, 2500);
    return () => {
      alive = false;
      clearTimeout(first);
      clearInterval(poll);
      unsub();
    };
  }, [jobId]);
}

export function jobActivo(job: Job | null | undefined): boolean {
  return (
    !!job && (job.estado === "en_cola" || job.estado === "corriendo" || job.estado === "esperando_usuario")
  );
}
