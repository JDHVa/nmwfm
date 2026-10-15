# Contrato de API (backend ↔ UI)

Base: `http://127.0.0.1:{port}`. El sidecar imprime en stdout una línea `NMWFM_READY {"port":1234,"token":"..."}`; toda petición lleva el header `X-Token`, excepto `GET /health` (sin token). En DEV: puerto 8765 y token `dev`.
Errores: HTTP 4xx/5xx con `{"error": {"code": str, "message": str}}`.

## Tipos
```ts
type Settings = { cuenta: string; tiene_password: boolean; nombre: string; matricula: string; dev: boolean; entregar_sin_revisar: boolean; reducir_animaciones: boolean; sync_inicial_hecha: boolean; ultima_sync: string | null; sync_cada_horas: number };
type Novedad = { id: number; tarea_id: string; materia_id: string; materia_nombre: string; numero: string; titulo: string; tipo: "nueva" | "modificada"; detalle: string; creada_en: string; leida: boolean };
type Materia = { id: string; nombre: string; profesor: string | null; periodo: string | null; sincronizada_en: string | null };
type Etapa = { id: string; materia_id: string; nombre: string; descripcion: string };
type Tarea = { id: string; etapa_id: string; materia_id: string; numero: string; titulo: string; tipo: "dimension" | "evidencia" | "examen" | "pia"; desde: string | null; hasta: string | null; puntos: number | null; modalidad: string | null; estado: "pendiente" | "generada" | "entregada"; entregada_en: string | null; vencida: boolean };
type Rubrica = { niveles: string[]; criterios: { criterio: string; niveles: { puntos: number; descripcion: string }[] }[] };
type TareaDetalle = Tarea & { actividades: string; contenido: string; criterios_desempeno: string; rubrica: Rubrica | null };
type Recurso = { id: string; tarea_id: string; nombre: string; tipo: "imagen" | "texto" | "pdf" | "otro"; descargado: boolean; usado: boolean };
type Insumo = { id: string; tipo: "imagen" | "texto"; ocr_texto?: string | null; original_url?: string; recortada_url?: string; miniatura_url?: string | null; texto?: string; orden: number; rotacion: 0 | 90 | 180 | 270; usar_recorte: boolean };
type Job = { id: string; tipo: "sync" | "generar" | "entregar" | "login_gemini" | "validar_siase" | "revisar_entregas"; estado: "en_cola" | "corriendo" | "esperando_usuario" | "ok" | "error"; paso: string; progreso: number; mensaje: string | null; resultado: unknown };
type Generacion = { id: number; tarea_id: string; markdown: string; docx_url: string; pdf_url: string; creada_en: string; avisos: string[] };
```
Las rutas `*_url` son relativas a la base (`/files/...`). `recortada_url` es la imagen recortada SIN rotar: la UI aplica `rotacion` con CSS (el PDF sí la aplica). `miniatura_url` es una miniatura de la recortada.
`Job.progreso` es un entero de 0 a 100. Con `entregar_sin_revisar` activo, el job `generar` encadena la entrega (pasos `generando` y `entregando`); si la entrega falla el job termina en `error` pero la generación queda disponible.

## Endpoints
- `GET /health` → `{ok: true, version}`
- `GET /settings` → `Settings` · `PUT /settings` body `Partial<Settings> & {password?: string}` (`sync_cada_horas`: entero >= 0; 0 apaga el sync incremental automático del backend, que corre en segundo plano mientras la app esté abierta)
- `POST /siase/validar` → `Job` (solo hace el login en SIASE con las credenciales guardadas y cierra; `estado: "ok"` si entró, `"error"` con `mensaje` legible si la cuenta/contraseña es incorrecta o el sitio no responde)
- `POST /gemini/login` → `Job` (abre Chrome en gemini.google.com para que el usuario inicie sesión; termina cuando detecta la sesión)
- `POST /sync` body `{modo?: "auto" | "completo" | "incremental"}` → `Job`. `auto` (por defecto): `completo` si `sync_inicial_hecha` es false; si no, `incremental`. `completo`: materias, profesor, etapas, tareas y el DETALLE de todas las tareas (actividades, contenido, criterios, rúbrica). `incremental`: lista de materias/etapas/tareas + detalle solo de las tareas nuevas o sin detalle. Corre con el navegador OCULTO (headless) aunque DEV esté activo. `Job.resultado`: `{materias, tareas, detalles_leidos, nuevas, errores: string[], tiempos: Record<fase, {n, total_s, media_s}>}` (fases: login, materia, tarea, rubrica, entregas; también van al log del job). En DEV el backend guarda en `data/debug/api/` un catálogo de los endpoints XHR/fetch que NEXUS pide durante el sync (solo URL sin tokens, método y forma del JSON). Si ya hay un sync corriendo, devuelve ese mismo Job. La UI lanza `auto` al abrir la app. El sync COMPLETO revisa además la pestaña Entregas de cada tarea (estado `entregada` + `entregada_en`); el incremental NO revisa entregas (para eso está `POST /entregas/revisar`). Las tareas ya `entregada` no se vuelven a abrir en syncs posteriores. `vencida` = no entregada y `hasta` < ahora. Tareas `examen` (título con "Examen", "Diagnostic", "Cuestionario en línea"): se contestan dentro de NEXUS; el sync NO abre su detalle (solo lista, fechas y puntos de la estructura), y la UI las muestra como recordatorio sin Generar/Entregar.
- `POST /entregas/revisar` → `Job` (opción manual "Revisar tareas entregadas": abre la pestaña Entregas de TODAS las tareas no entregadas y actualiza `estado`/`entregada_en`; headless y en secuencia, en la única pestaña de NEXUS (NEXUS solo admite una instancia abierta), como el sync. `resultado: {revisadas, entregadas, pendientes, errores}`)
- `GET /tareas/proximas` → `Tarea[]` (pendientes de todas las materias, sin entregar, ordenadas por `hasta` ascendente; incluye las vencidas al final con `vencida: true`; agrega `materia_nombre: string`)
- `GET /novedades` (query `no_leidas=1` opcional) → `Novedad[]` (tareas NUEVAS o MODIFICADAS detectadas por un sync posterior al inicial: título, fecha de entrega, puntos, actividades, contenido, criterios o rúbrica; `detalle` resume el cambio; más recientes primero)
- `POST /novedades/leidas` body `{ids?: number[]}` (sin `ids` = todas) → `{marcadas: number}`
- `GET /alertas` → `(Tarea & {materia_nombre: string; dias: 0 | 1})[]` (no entregadas que vencen hoy (`dias: 0`) o mañana (`dias: 1`), todavía no vencidas; para notificaciones)
- `GET /materias` → `Materia[]`
- `GET /materias/{id}/etapas` → `(Etapa & {tareas: Tarea[]})[]`
- `GET /tareas/{id}` → `TareaDetalle` (si no hay detalle en caché lo trae de NEXUS)
- `GET /tareas/{id}/insumos` → `Insumo[]`
- `POST /tareas/{id}/insumos` multipart `files[]` (imágenes) → `Insumo[]` (ya recortadas)
- `POST /tareas/{id}/insumos/texto` body `{texto}` → `Insumo`
- `GET /tareas/{id}/recursos` → `Recurso[]` (archivos de la pestaña "Recursos" de la tarea que ya se descargaron como insumos opcionales; la lista queda vacía mientras no se implemente la lectura de esa pestaña en NEXUS)
- `POST /tareas/{id}/recursos/{rid}/usar` → `Insumo` (convierte el recurso en insumo: imagen → imagen recortada, texto → insumo de texto; 409 `sin_descargar` si el archivo no está, 415 `tipo_no_soportado` para otros tipos)
- `PATCH /insumos/{id}` body `{orden?, rotacion?, usar_recorte?, texto?}` → `Insumo`
- `DELETE /insumos/{id}` → 204
- `POST /tareas/{id}/generar` body `{instrucciones_extra?: string}` → `Job` (OCR local de las imágenes si `rapidocr-onnxruntime` está instalado: el texto extraído se agrega al prompt y se expone en `Insumo.ocr_texto`; insumos.pdf → Gemini → docx/pdf con portada; el documento lleva en su primera línea "Materia - Título", un índice automático si hay más de 4 secciones `##`, numeración de páginas desde el cuerpo (sin número en la portada) y las referencias APA con sangría francesa)
- `GET /tareas/{id}/generaciones` → `(Generacion & {actual: boolean})[]` (historial de generaciones de la tarea, la más reciente primero; cada una conserva su propio .docx/.pdf)
- `POST /generaciones/{id}/restaurar` → `Generacion` (la generación del historial pasa a ser la actual; el estado de la tarea no cambia salvo que estuviera `pendiente`, que pasa a `generada`)
- `GET /tareas/{id}/portada-preview` → `{pdf_url: string}` (PDF de la portada con los datos reales: nombre y matrícula de Settings, profesor de la materia y la fecha de hoy; requiere Word instalado, 502 `sin_word` si falla la conversión)
- `GET /tareas/{id}/generacion` → `Generacion | null` (`avisos`: advertencias de la generación, p. ej. un diagrama Mermaid que no se pudo renderizar como imagen y se insertó como lista/tabla porque no hay Graphviz local; la UI debe mostrarlas)
- `POST /tareas/{id}/abrir-docx` → 204 (abre el .docx en Word)
- `POST /tareas/{id}/reconstruir-pdf` → `Generacion` (tras editar el .docx a mano)
- `POST /tareas/{id}/entregar` body `{confirmar: true}` → `Job`
- `GET /jobs/{id}` → `Job`
- `POST /jobs/{id}/continuar` → `Job` (cuando estaba `esperando_usuario`, p. ej. captcha)
- `WS /ws?token=...` → mensajes `{"type":"job","job":Job}` y `{"type":"log","level":str,"message":str}`
- `GET /files/{path}` → archivos dentro de `data/` (miniaturas, PDFs, docx); acepta el token también como `?token=...` para usarlo en `<img src>`
