# Contrato de API (backend ↔ UI)

Base: `http://127.0.0.1:{port}`. El sidecar imprime en stdout una línea `NMWFM_READY {"port":1234,"token":"..."}`; toda petición lleva el header `X-Token`, excepto `GET /health` (sin token). En DEV: puerto 8765 y token `dev`.
Errores: HTTP 4xx/5xx con `{"error": {"code": str, "message": str}}`.

## Tipos
```ts
type Settings = { cuenta: string; tiene_password: boolean; nombre: string; matricula: string; dev: boolean; entregar_sin_revisar: boolean; reducir_animaciones: boolean; sync_inicial_hecha: boolean; ultima_sync: string | null };
type Materia = { id: string; nombre: string; profesor: string | null; periodo: string | null; sincronizada_en: string | null };
type Etapa = { id: string; materia_id: string; nombre: string; descripcion: string };
type Tarea = { id: string; etapa_id: string; materia_id: string; numero: string; titulo: string; tipo: "dimension" | "evidencia"; desde: string | null; hasta: string | null; puntos: number | null; modalidad: string | null; estado: "pendiente" | "generada" | "entregada" };
type Rubrica = { niveles: string[]; criterios: { criterio: string; niveles: { puntos: number; descripcion: string }[] }[] };
type TareaDetalle = Tarea & { actividades: string; contenido: string; criterios_desempeno: string; rubrica: Rubrica | null };
type Insumo = { id: string; tipo: "imagen" | "texto"; original_url?: string; recortada_url?: string; miniatura_url?: string | null; texto?: string; orden: number; rotacion: 0 | 90 | 180 | 270; usar_recorte: boolean };
type Job = { id: string; tipo: "sync" | "generar" | "entregar" | "login_gemini" | "validar_siase"; estado: "en_cola" | "corriendo" | "esperando_usuario" | "ok" | "error"; paso: string; progreso: number; mensaje: string | null; resultado: unknown };
type Generacion = { tarea_id: string; markdown: string; docx_url: string; pdf_url: string; creada_en: string };
```
Las rutas `*_url` son relativas a la base (`/files/...`). `recortada_url` es la imagen recortada SIN rotar: la UI aplica `rotacion` con CSS (el PDF sí la aplica). `miniatura_url` es una miniatura de la recortada.
`Job.progreso` es un entero de 0 a 100. Con `entregar_sin_revisar` activo, el job `generar` encadena la entrega (pasos `generando` y `entregando`); si la entrega falla el job termina en `error` pero la generación queda disponible.

## Endpoints
- `GET /health` → `{ok: true, version}`
- `GET /settings` → `Settings` · `PUT /settings` body `Partial<Settings> & {password?: string}`
- `POST /siase/validar` → `Job` (solo hace el login en SIASE con las credenciales guardadas y cierra; `estado: "ok"` si entró, `"error"` con `mensaje` legible si la cuenta/contraseña es incorrecta o el sitio no responde)
- `POST /gemini/login` → `Job` (abre Chrome en gemini.google.com para que el usuario inicie sesión; termina cuando detecta la sesión)
- `POST /sync` body `{modo?: "auto" | "completo" | "incremental"}` → `Job`. `auto` (por defecto): `completo` si `sync_inicial_hecha` es false; si no, `incremental`. `completo`: materias, profesor, etapas, tareas y el DETALLE de todas las tareas (actividades, contenido, criterios, rúbrica). `incremental`: lista de materias/etapas/tareas + detalle solo de las tareas nuevas o sin detalle. Corre con el navegador OCULTO (headless) aunque DEV esté activo. `Job.resultado`: `{materias, tareas, detalles_leidos, nuevas, errores: string[]}`. Si ya hay un sync corriendo, devuelve ese mismo Job. La UI lanza `auto` al abrir la app.
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
- `GET /files/{path}` → archivos dentro de `data/` (miniaturas, PDFs, docx); acepta el token también como `?token=...` para usarlo en `<img src>`
