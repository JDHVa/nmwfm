# Contrato de API (backend ↔ UI)

Base: `http://127.0.0.1:{port}`. El sidecar imprime en stdout una línea `NMWFM_READY {"port":1234,"token":"..."}`; toda petición lleva el header `X-Token`. En DEV: puerto 8765 y token `dev`.
Errores: HTTP 4xx/5xx con `{"error": {"code": str, "message": str}}`.

## Tipos
```ts
type Settings = { cuenta: string; tiene_password: boolean; nombre: string; matricula: string; dev: boolean; entregar_sin_revisar: boolean; reducir_animaciones: boolean };
type Materia = { id: string; nombre: string; profesor: string | null; periodo: string | null; sincronizada_en: string | null };
type Etapa = { id: string; materia_id: string; nombre: string; descripcion: string };
type Tarea = { id: string; etapa_id: string; materia_id: string; numero: string; titulo: string; tipo: "dimension" | "evidencia"; desde: string | null; hasta: string | null; puntos: number | null; modalidad: string | null; estado: "pendiente" | "generada" | "entregada" };
type Rubrica = { niveles: string[]; criterios: { criterio: string; niveles: { puntos: number; descripcion: string }[] }[] };
type TareaDetalle = Tarea & { actividades: string; contenido: string; criterios_desempeno: string; rubrica: Rubrica | null };
type Insumo = { id: string; tipo: "imagen" | "texto"; original_url?: string; recortada_url?: string; texto?: string; orden: number; rotacion: 0 | 90 | 180 | 270; usar_recorte: boolean };
type Job = { id: string; tipo: "sync" | "generar" | "entregar" | "login_gemini"; estado: "en_cola" | "corriendo" | "esperando_usuario" | "ok" | "error"; paso: string; progreso: number; mensaje: string | null; resultado: unknown };
type Generacion = { tarea_id: string; markdown: string; docx_url: string; pdf_url: string; creada_en: string };
```
Las rutas `*_url` son relativas a la base (`/files/...`).

## Endpoints
- `GET /health` → `{ok: true, version}`
- `GET /settings` → `Settings` · `PUT /settings` body `Partial<Settings> & {password?: string}`
- `POST /gemini/login` → `Job` (abre Chrome en gemini.google.com para que el usuario inicie sesión; termina cuando detecta la sesión)
- `POST /sync` → `Job` (login SIASE → NEXUS → materias, profesor, etapas, tareas)
- `GET /materias` → `Materia[]`
- `GET /materias/{id}/etapas` → `(Etapa & {tareas: Tarea[]})[]`
- `GET /tareas/{id}` → `TareaDetalle` (si no hay detalle en caché lo trae de NEXUS)
- `GET /tareas/{id}/insumos` → `Insumo[]`
- `POST /tareas/{id}/insumos` multipart `files[]` (imágenes) → `Insumo[]` (ya recortadas)
- `POST /tareas/{id}/insumos/texto` body `{texto}` → `Insumo`
- `PATCH /insumos/{id}` body `{orden?, rotacion?, usar_recorte?, texto?}` → `Insumo`
- `DELETE /insumos/{id}` → 204
- `POST /tareas/{id}/generar` body `{instrucciones_extra?: string}` → `Job` (insumos.pdf → Gemini → docx/pdf con portada)
- `GET /tareas/{id}/generacion` → `Generacion | null`
- `POST /tareas/{id}/abrir-docx` → 204 (abre el .docx en Word)
- `POST /tareas/{id}/reconstruir-pdf` → `Generacion` (tras editar el .docx a mano)
- `POST /tareas/{id}/entregar` body `{confirmar: true}` → `Job`
- `GET /jobs/{id}` → `Job`
- `POST /jobs/{id}/continuar` → `Job` (cuando estaba `esperando_usuario`, p. ej. captcha)
- `WS /ws?token=...` → mensajes `{"type":"job","job":Job}` y `{"type":"log","level":str,"message":str}`
- `GET /files/{path}` → archivos dentro de `data/` (miniaturas, PDFs, docx)
