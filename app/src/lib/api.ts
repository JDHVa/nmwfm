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
  aula: string;
  grupo: string;
  turno: string;
  especialidad: string;
  sync_cada_horas?: number;
  asistente_modelo?: string;
  asistente_keep_alive_s?: number;
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
  indicaciones?: string;
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
export type JobTipo =
  "sync" | "generar" | "entregar" | "login_gemini" | "validar_siase" | "revisar_entregas" | "diagnostico";
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
export type PortadaPreview = { pdf_url: string };
export type Novedad = {
  id: number;
  tarea_id: string;
  materia_id: string;
  materia_nombre: string;
  numero: string;
  titulo: string;
  tipo: "nueva" | "modificada";
  detalle: string;
  creada_en: string;
  leida: boolean;
};
export type Alerta = {
  tarea_id: string;
  materia_id: string;
  materia_nombre: string;
  titulo: string;
  hasta: string;
  cuando: "hoy" | "manana";
};
export type AlertaApi = Tarea & { materia_nombre: string; dias: 0 | 1 };
export type Respaldo = { nombre: string; url: string; bytes: number; creado_en: string };
export type RestauracionResultado = { restaurados: number; respaldo_previo: string };
export type PasoDiagnostico = {
  nombre: string;
  ok: boolean;
  ms: number;
  detalle: string;
  selectores_faltantes: string[];
};
export type Diagnostico = { ok: boolean; pasos: PasoDiagnostico[] };
export type Calificaciones = { columnas: string[]; filas: string[][]; actualizada_en: string };
export type MensajeChat = { rol: "user" | "assistant" | "tool"; contenido: string; herramienta?: string };
export type EstadoAsistente = {
  ollama: boolean;
  modelo: string;
  modelo_instalado: boolean;
  error: string | null;
};
export type EventoChat =
  | { type: "token"; text: string }
  | { type: "tool_call"; nombre: string; args: unknown }
  | { type: "tool_result"; nombre: string; resultado: unknown }
  | { type: "confirmar"; accion: string; args: unknown; id: string }
  | { type: "estado"; estado?: "cargando" | "pensando"; mensaje?: string }
  | { type: "fin" }
  | { type: "error"; message: string };
export type ConfirmacionResultado = { ok?: boolean; mensaje?: string } & Record<string, unknown>;
export type DatosPortada = {
  profesor?: string;
  aula?: string;
  grupo?: string;
  turno?: string;
  especialidad?: string;
};
export type PortadaSuelta = DatosPortada & { profesor: string };
export type ProfesorSugerido = { nombre: string; materias: string[] };
export type PortadaSueltaResultado = { docx_url: string; pdf_url: string };
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
  id: number;
  tarea_id: string;
  markdown: string;
  docx_url: string;
  pdf_url: string;
  creada_en: string;
  avisos: string[];
};
export type GeneracionHistorial = Generacion & { actual: boolean };
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
  generar: (tareaId: string, instruccionesExtra?: string, portada?: DatosPortada) =>
    request<Job>("POST", `/tareas/${tareaId}/generar`, {
      instrucciones_extra: instruccionesExtra,
      ...(portada ? { portada } : {}),
    }),
  portadaPreview: (tareaId: string, datos: DatosPortada = {}) => {
    const qs = new URLSearchParams(Object.entries(datos).filter(([, v]) => v));
    const sufijo = qs.size ? `?${qs}` : "";
    return request<PortadaPreview>("GET", `/tareas/${tareaId}/portada-preview${sufijo}`);
  },
  profesores: () => request<ProfesorSugerido[]>("GET", "/profesores"),
  generacion: (tareaId: string) => request<Generacion | null>("GET", `/tareas/${tareaId}/generacion`),
  generaciones: (tareaId: string) => request<GeneracionHistorial[]>("GET", `/tareas/${tareaId}/generaciones`),
  restaurarGeneracion: (id: number) => request<Generacion>("POST", `/generaciones/${id}/restaurar`),
  novedades: () => request<Novedad[]>("GET", "/novedades"),
  leerNovedades: (ids?: number[]) =>
    request<{ marcadas: number }>("POST", "/novedades/leidas", ids ? { ids } : {}),
  alertas: async (): Promise<Alerta[]> => {
    const lista = await request<AlertaApi[]>("GET", "/alertas");
    return lista.map((t) => ({
      tarea_id: t.id,
      materia_id: t.materia_id,
      materia_nombre: t.materia_nombre,
      titulo: t.titulo,
      hasta: t.hasta ?? "",
      cuando: t.dias === 0 ? "hoy" : "manana",
    }));
  },
  respaldos: () => request<Respaldo[]>("GET", "/respaldo"),
  crearRespaldo: () => request<Respaldo>("POST", "/respaldo"),
  restaurarRespaldo: (nombre: string) =>
    request<RestauracionResultado>("POST", "/respaldo/restaurar", { nombre }),
  diagnostico: () => request<Job>("POST", "/diagnostico"),
  calificaciones: (materiaId: string) =>
    request<Calificaciones | null>("GET", `/materias/${materiaId}/calificaciones`),
  precalentarAsistente: () =>
    request<{ cargado: boolean; cargando: boolean; modelo: string }>("POST", "/asistente/precalentar"),
  liberarAsistente: (keepalive = false) =>
    connection
      .transport(`${connection.base}/asistente/liberar`, {
        method: "POST",
        headers: { "X-Token": connection.token },
        keepalive,
      })
      .then(
        () => undefined,
        () => undefined,
      ),
  asistenteEstado: () => request<EstadoAsistente>("GET", "/asistente/estado"),
  confirmarAsistente: (id: string, aceptar: boolean) =>
    request<ConfirmacionResultado>("POST", "/asistente/confirmar", { id, aceptar }),
  indicaciones: (tareaId: string, indicaciones: string) =>
    request<TareaDetalle>("PUT", `/tareas/${tareaId}/indicaciones`, { indicaciones }),
  herramientaPdf: (files: File[], recortar: boolean, portada?: PortadaSuelta) => {
    const form = new FormData();
    files.forEach((f) => form.append("files[]", f, f.name));
    form.append("recortar", recortar ? "true" : "false");
    if (portada) form.append("portada", JSON.stringify(portada));
    return request<{ pdf_url: string }>("POST", "/herramientas/pdf", form);
  },
  herramientaPortada: (datos: PortadaSuelta) =>
    request<PortadaSueltaResultado>("POST", "/herramientas/portada", datos),
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

export async function chatAsistente(
  body: { mensajes: MensajeChat[]; tarea_id?: string },
  alEvento: (e: EventoChat) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await connection.transport(`${connection.base}/asistente/chat`, {
      method: "POST",
      headers: {
        "X-Token": connection.token,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if ((e as Error)?.name === "AbortError") return;
    throw new ApiError(0, "sin_conexion", "No se pudo conectar con el servicio local");
  }
  if (!res.ok) throw await parseError(res);
  if (!res.body) throw new ApiError(0, "sin_flujo", "La respuesta no trae un flujo de datos");
  const lector = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const procesar = (bloque: string) => {
    const datos = bloque
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trimStart())
      .join("\n");
    if (!datos) return;
    try {
      alEvento(JSON.parse(datos) as EventoChat);
    } catch {
      return;
    }
  };
  try {
    for (;;) {
      const { done, value } = await lector.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let i: number;
      while ((i = buffer.search(/\r?\n\r?\n/)) >= 0) {
        procesar(buffer.slice(0, i));
        buffer = buffer.slice(i).replace(/^\r?\n\r?\n/, "");
      }
    }
    if (buffer.trim()) procesar(buffer);
  } catch (e) {
    if ((e as Error)?.name !== "AbortError") throw e;
  }
}
