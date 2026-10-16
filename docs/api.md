# Contrato de API (backend ↔ UI)

Base: `http://127.0.0.1:{port}`. El sidecar imprime en stdout una línea `NMWFM_READY {"port":1234,"token":"..."}`; toda petición lleva el header `X-Token`, excepto `GET /health` (sin token). En DEV: puerto 8765 y token `dev`.
Errores: HTTP 4xx/5xx con `{"error": {"code": str, "message": str}}`.

## Tipos
```ts
type Settings = { cuenta: string; tiene_password: boolean; nombre: string; matricula: string; dev: boolean; entregar_sin_revisar: boolean; reducir_animaciones: boolean; sync_inicial_hecha: boolean; ultima_sync: string | null; sync_cada_horas: number; recorte_modelo: "auto" | "opencv"; modelo_recorte_disponible: boolean; aula: string; grupo: string; turno: string; especialidad: string; instrucciones_fijas: InstruccionFija[]; gemini_espera_envio_s: number; asistente_modelo: string; asistente_keep_alive_s: number };
type DatosPortada = { profesor?: string; aula?: string; grupo?: string; turno?: string; especialidad?: string };
type Respaldo = { nombre: string; url: string; bytes: number; creado_en: string };
type Diagnostico = { ok: boolean; pasos: { nombre: string; ok: boolean; ms: number; detalle: string; selectores_faltantes: string[] }[] };
type Calificaciones = { columnas: string[]; filas: string[][]; actualizada_en: string };
type Novedad = { id: number; tarea_id: string; materia_id: string; materia_nombre: string; numero: string; titulo: string; tipo: "nueva" | "modificada"; detalle: string; creada_en: string; leida: boolean };
type Materia = { id: string; nombre: string; profesor: string | null; periodo: string | null; sincronizada_en: string | null };
type Etapa = { id: string; materia_id: string; nombre: string; descripcion: string };
type Tarea = { id: string; etapa_id: string; materia_id: string; numero: string; titulo: string; tipo: "dimension" | "evidencia" | "examen" | "pia"; desde: string | null; hasta: string | null; puntos: number | null; modalidad: string | null; estado: "pendiente" | "generada" | "entregada"; entregada_en: string | null; vencida: boolean };
type Rubrica = { niveles: string[]; criterios: { criterio: string; niveles: { puntos: number; descripcion: string }[] }[] };
type TareaDetalle = Tarea & { actividades: string; contenido: string; criterios_desempeno: string; rubrica: Rubrica | null };
type Insumo = { id: string; tipo: "imagen" | "texto"; ocr_texto?: string | null; ocr_editado?: boolean; original_url?: string; recortada_url?: string; miniatura_url?: string | null; texto?: string; orden: number; rotacion: 0 | 90 | 180 | 270; usar_recorte: boolean };
type Job = { id: string; tipo: "sync" | "generar" | "entregar" | "login_gemini" | "validar_siase" | "revisar_entregas" | "diagnostico"; estado: "en_cola" | "corriendo" | "esperando_usuario" | "ok" | "error"; paso: string; progreso: number; mensaje: string | null; resultado: unknown };
type Generacion = { id: number; tarea_id: string; markdown: string; docx_url: string; pdf_url: string; creada_en: string; avisos: string[]; portada: DatosPortada | null };
```
Las rutas `*_url` son relativas a la base (`/files/...`). `recortada_url` es la imagen recortada SIN rotar: la UI aplica `rotacion` con CSS (el PDF sí la aplica). `miniatura_url` es una miniatura de la recortada.
`Job.progreso` es un entero de 0 a 100. Con `entregar_sin_revisar` activo, el job `generar` encadena la entrega (pasos `generando` y `entregando`); si la entrega falla el job termina en `error` pero la generación queda disponible.

## Instrucciones fijas del prompt
```ts
type InstruccionFija = { id: string; texto: string; activa: boolean; sistema: boolean };
```
- `Settings` agrega `instrucciones_fijas: InstruccionFija[]`: la lista de instrucciones que se mandan SIEMPRE a Gemini, editable en Configuración (activar/desactivar, editar texto, agregar, borrar, reordenar; el orden del arreglo es el orden en el prompt). Valores por defecto (`sistema: true`, ids fijos): `rubrica_maxima` ("Cumple cada criterio de la rúbrica en su nivel máximo..."), `cubrir_contenido`, `tono_preparatoria`, `no_mencionar_rubrica`, `referencias_apa7` ("Termina con una sección ## Referencias en formato APA 7 con fuentes reales y verificables...; no inventes referencias."). Las `sistema: true` se pueden desactivar y editar pero no borrar; `PUT /settings` con `instrucciones_fijas` reemplaza la lista completa (las de sistema que falten se re-agregan desactivadas). Las nuevas que agregue el usuario llevan `sistema: false` y un id generado por la UI (`u-<aleatorio>`). Las reglas de formato (solo Markdown, sin portada, uso de adjuntos, diagrama Mermaid) NO están en la lista: son internas y siempre se envían.
- `POST /tareas/{id}/generar` acepta además `instrucciones?: {[id: string]: boolean}`: activa o desactiva instrucciones fijas SOLO para esa generación (p. ej. `{referencias_apa7: false}` para un profe que no pide referencias). Si en la respuesta no hay sección de Referencias, el documento simplemente no la lleva.
- `GET /prompt-preview/{tarea_id}?instrucciones=<json>` → `{prompt: string}` (opcional para la UI: el prompt exacto que se mandaría).
- Gemini: tras pegar el prompt (y adjuntar el PDF) se espera `gemini_espera_envio_s` segundos (Setting nuevo, entero 0–15, por defecto 3) antes de pulsar Enviar.

## Endpoints
- `GET /health` → `{ok: true, version}`
- `GET /settings` → `Settings` · `PUT /settings` body `Partial<Settings> & {password?: string}` (`recorte_modelo`: `auto` usa el modelo ONNX de segmentación (GPU con DirectML, CPU como respaldo) para recortar la hoja si el archivo está en `data/models/` y cae al detector OpenCV si falta o falla; `opencv` fuerza solo OpenCV; `modelo_recorte_disponible` es solo lectura e indica si el modelo está descargado. `sync_cada_horas`: entero >= 0; 0 apaga el sync incremental automático del backend, que corre en segundo plano mientras la app esté abierta)
- `POST /siase/validar` → `Job` (solo hace el login en SIASE con las credenciales guardadas y cierra; `estado: "ok"` si entró, `"error"` con `mensaje` legible si la cuenta/contraseña es incorrecta o el sitio no responde)
- `POST /diagnostico` → `Job` (smoke test de SOLO LECTURA contra NEXUS: login, lista de materias, portada, estructura, una tarea con rúbrica y entregas, calificaciones; `resultado: Diagnostico` indica qué paso y qué selectores fallaron; el job termina `ok` aunque haya pasos con falla; también disponible por consola con `python -m backend.check [--json]`)
- `GET /respaldo` → `Respaldo[]` (zips guardados en `data/respaldos/`, el más reciente primero)
- `POST /respaldo` → `Respaldo` (zip de `data/` sin `browser_profile`, `gemini_profile`, `respaldos` ni `debug`: base de datos consistente, insumos y generaciones; NO incluye la contraseña, que vive en el Administrador de credenciales de Windows)
- `POST /respaldo/restaurar` body JSON `{nombre}` (un zip de `GET /respaldo`) o multipart con `file` (un zip subido) → `{restaurados: number, respaldo_previo: string}` (antes de restaurar crea un respaldo `pre-restauracion-*`; 409 `jobs_en_curso` si hay jobs corriendo; 400 `respaldo_invalido` si el zip no trae `nmwfm.db` o tiene rutas peligrosas)
- `POST /gemini/login` → `Job` (abre Chrome en gemini.google.com para que el usuario inicie sesión; termina cuando detecta la sesión; la ventana de Chrome se abre SIEMPRE visible, también en la app instalada; resultado `{sesion, ya_iniciada}`, con `ya_iniciada: true` si el perfil ya tenía sesión y el paso final es «Ya tienes la sesión de Gemini iniciada»). Gemini usa su PROPIO perfil persistente (`data/gemini_profile`) y su propia instancia de Chrome (visible en DEV), independiente de NEXUS, que corre oculto con `data/browser_profile`: los dos tienen candados distintos y pueden trabajar a la vez, y cambiar el modo de uno nunca cierra la ventana del otro.
- `POST /sync` body `{modo?: "auto" | "completo" | "incremental"}` → `Job`. `auto` (por defecto): `completo` si `sync_inicial_hecha` es false; si no, `incremental`. `completo`: materias, profesor, etapas, tareas y el DETALLE de todas las tareas (actividades, contenido, criterios, rúbrica). `incremental`: lista de materias/etapas/tareas + detalle solo de las tareas nuevas o sin detalle. Corre con el navegador OCULTO (headless) aunque DEV esté activo. `Job.resultado`: `{materias, tareas, detalles_leidos, nuevas, errores: string[], tiempos: Record<fase, {n, total_s, media_s}>}` (fases: login, materia, tarea, rubrica, entregas; también van al log del job). En DEV el backend guarda en `data/debug/api/` un catálogo de los endpoints XHR/fetch que NEXUS pide durante el sync (solo URL sin tokens, método y forma del JSON). Si ya hay un sync corriendo, devuelve ese mismo Job. El backend NO sincroniza solo al arrancar y la UI tampoco lo hace al abrir la app: el sync lo dispara el usuario, el primer arranque de la UI (solo si `sync_inicial_hecha` es false) o el programador interno (`sync_cada_horas`; 0 = apagado, que es el valor por defecto). El sync COMPLETO revisa además la pestaña Entregas de cada tarea (estado `entregada` + `entregada_en`); el incremental NO revisa entregas (para eso está `POST /entregas/revisar`). Las tareas ya `entregada` no se vuelven a abrir en syncs posteriores. `vencida` = no entregada y `hasta` < ahora. Tareas `examen` (título con "Examen", "Diagnostic", "Cuestionario en línea"): se contestan dentro de NEXUS; el sync NO abre su detalle (solo lista, fechas y puntos de la estructura), y la UI las muestra como recordatorio sin Generar/Entregar.
- `POST /entregas/revisar` → `Job` (opción manual "Revisar tareas entregadas": abre la pestaña Entregas de TODAS las tareas no entregadas y actualiza `estado`/`entregada_en`; headless y en secuencia, en la única pestaña de NEXUS (NEXUS solo admite una instancia abierta), como el sync. `resultado: {revisadas, entregadas, pendientes, errores}`)
- `GET /tareas/proximas` → `Tarea[]` (pendientes de todas las materias, sin entregar, ordenadas por `hasta` ascendente; incluye las vencidas al final con `vencida: true`; agrega `materia_nombre: string`)
- `GET /novedades` (query `no_leidas=1` opcional) → `Novedad[]` (tareas NUEVAS o MODIFICADAS detectadas por un sync posterior al inicial: título, fecha de entrega, puntos, actividades, contenido, criterios o rúbrica; `detalle` resume el cambio; más recientes primero)
- `POST /novedades/leidas` body `{ids?: number[]}` (sin `ids` = todas) → `{marcadas: number}`
- `GET /alertas` → `(Tarea & {materia_nombre: string; dias: 0 | 1})[]` (no entregadas que vencen hoy (`dias: 0`) o mañana (`dias: 1`), todavía no vencidas; para notificaciones)
- `GET /materias` → `Materia[]`
- `GET /materias/{id}/calificaciones` → `Calificaciones | null` (tabla de la pestaña "Calificaciones" de la materia, leída en el sync COMPLETO tal como aparece en NEXUS; `null` si todavía no se leyó o si NEXUS no mostró una tabla reconocible: en ese caso se guarda un snapshot en `data/debug/` para ajustar el lector)
- `GET /materias/{id}/etapas` → `(Etapa & {tareas: Tarea[]})[]`
- `GET /tareas/{id}` → `TareaDetalle` (si no hay detalle en caché lo trae de NEXUS)
- `GET /tareas/{id}/insumos` → `Insumo[]`
- `POST /tareas/{id}/insumos` multipart `files[]` (imágenes) → `Insumo[]` (ya recortadas)
- `POST /tareas/{id}/insumos/texto` body `{texto}` → `Insumo`
- `PATCH /insumos/{id}` body `{orden?, rotacion?, usar_recorte?, texto?, ocr_texto?}` (`ocr_texto` editado por el usuario reemplaza al OCR automático y no se recalcula salvo al rotar) → `Insumo`
- `DELETE /insumos/{id}` → 204
- `POST /tareas/{id}/generar` body `{instrucciones_extra?: string, portada?: DatosPortada, instrucciones?: {[id: string]: boolean}}` → `Job` (`instrucciones`: ver «Instrucciones fijas del prompt») (OCR local de las imágenes si `rapidocr-onnxruntime` está instalado: el texto extraído se agrega al prompt y se expone en `Insumo.ocr_texto`; insumos.pdf → Gemini → docx/pdf con portada; el documento lleva en su primera línea "Materia - Título", un índice automático si hay más de 4 secciones `##`, numeración de páginas desde el cuerpo (sin número en la portada) y las referencias APA con sangría francesa)
- `GET /tareas/{id}/generaciones` → `(Generacion & {actual: boolean})[]` (historial de generaciones de la tarea, la más reciente primero; cada una conserva su propio .docx/.pdf)
- `POST /generaciones/{id}/restaurar` → `Generacion` (la generación del historial pasa a ser la actual; el estado de la tarea no cambia salvo que estuviera `pendiente`, que pasa a `generada`)
- `GET /tareas/{id}/portada-preview?profesor=&aula=&grupo=&turno=&especialidad=` → `{pdf_url: string}` (overrides opcionales; PDF de la portada con los datos reales: nombre y matrícula de Settings, profesor de la materia y la fecha de hoy; requiere Word instalado, 502 `sin_word` si falla la conversión)
- `GET /tareas/{id}/generacion` → `Generacion | null` (`avisos`: advertencias de la generación, p. ej. un diagrama Mermaid que no se pudo renderizar como imagen y se insertó como lista/tabla porque no hay Graphviz local; la UI debe mostrarlas)
- `POST /tareas/{id}/abrir-docx` → 204 (abre el .docx en Word)
- `POST /tareas/{id}/reconstruir-pdf` → `Generacion` (tras editar el .docx a mano)
- `POST /tareas/{id}/entregar` body `{confirmar: true}` → `Job`
- `GET /jobs/{id}` → `Job`
- `POST /jobs/{id}/cancelar` → `Job` (detiene un job `en_cola`, `corriendo` o `esperando_usuario`: cancela su tarea, cierra ordenadamente el navegador que usaba (Gemini o NEXUS) para no dejarlo trabado y lo deja en `estado: "error"` con `mensaje: "Cancelado por el usuario"` y `resultado: {cancelado: true}`; si ya terminó, lo devuelve tal cual. Funciona para todos los tipos de job)
- `POST /jobs/{id}/continuar` → `Job` (cuando estaba `esperando_usuario`, p. ej. captcha)
- `WS /ws?token=...` → mensajes `{"type":"job","job":Job}` y `{"type":"log","level":str,"message":str}`
- `GET /files/{path}` → archivos dentro de `data/` (miniaturas, PDFs, docx); acepta el token también como `?token=...` para usarlo en `<img src>`

## Estado de la sesión de Gemini
- `Settings` agrega (solo lectura) `gemini_sesion: boolean | null` y `gemini_sesion_verificada_en: string | null`. `null` = nunca verificada. Se actualizan solos: el job `login_gemini` deja `true` al detectar sesión (también con `ya_iniciada`); `generar` deja `true` cuando Gemini abre con sesión y `false` si encuentra la pantalla de login de Google o los marcadores de bloqueo; `verificar_gemini` deja lo que detecte. Se guardan en SQLite (no son credenciales: solo un booleano y una fecha).
- `POST /gemini/verificar` → `Job` (tipo nuevo `"verificar_gemini"`): abre el perfil de Gemini, comprueba la sesión con `sesion_activa()` sin pedir nada al usuario, cierra el contexto ordenadamente y termina `ok` con `resultado: {sesion: boolean}`. Al arrancar el backend NO se verifica sola.
- UI (Configuración → Gemini): si `gemini_sesion` es `true` muestra «Sesión de Gemini guardada» con la fecha de verificación y los botones «Verificar sesión» y «Volver a iniciar sesión»; si es `false` muestra «La sesión de Gemini se cerró» y «Iniciar sesión en Gemini»; si es `null` muestra «Sesión sin verificar» con «Verificar sesión» (principal) e «Iniciar sesión en Gemini».

## Asistente (chat local) y herramientas sueltas
Motor: Ollama local (`http://127.0.0.1:11434`), modelo por defecto `qwen3:4b-instruct-2507-q4_K_M` (sin razonamiento, responde rápido y cabe en 6 GB de VRAM), configurable. Todo es local.
```ts
type MensajeChat = { rol: "user" | "assistant" | "tool"; contenido: string; herramienta?: string };
type EstadoAsistente = { ollama: boolean; modelo: string; modelo_instalado: boolean; error: string | null };
```
- `Settings` agrega `asistente_modelo: string` (por defecto `qwen3:4b-instruct-2507-q4_K_M`) y `asistente_keep_alive_s: number` (segundos que Ollama mantiene el modelo en la GPU tras cada uso; entero >= 1; por defecto 90).
- `TareaDetalle` agrega `indicaciones: string` (notas del profe/pizarrón; las escribe el usuario o el asistente; el sync NUNCA las toca; el prompt de Gemini las incluye con prioridad sobre la descripción de NEXUS).
- `PUT /tareas/{id}/indicaciones` body `{indicaciones: string}` → `TareaDetalle`.
- `GET /asistente/estado` → `EstadoAsistente`.
- `POST /asistente/chat` body `{mensajes: MensajeChat[], tarea_id?: string}` → `text/event-stream` con eventos `{"type":"token","text"}`, `{"type":"tool_call","nombre","args"}`, `{"type":"tool_result","nombre","resultado"}`, `{"type":"confirmar","accion","args","id"}` (acciones peligrosas: entregar), `{"type":"fin"}` y `{"type":"error","message"}`. Las herramientas del asistente: `buscar_tareas`, `ver_tarea`, `proximas_entregas`, `agregar_indicaciones` / `reemplazar_indicaciones`, `crear_pdf_imagenes`, `generar_portada`, `sincronizar`, `revisar_entregas`, `generar_tarea`, `entregar_tarea` (esta última SIEMPRE requiere confirmación del usuario).
- `POST /asistente/precalentar` → `{cargado: boolean, cargando: boolean, modelo: string}` (la UI lo llama al abrir la vista del asistente: carga el modelo en la GPU en segundo plano, tarda ~30 s en frío; 503 `ollama_no_disponible` si Ollama no corre). El chat agrega eventos `{"type":"estado","estado":"cargando"|"pensando","mensaje":string}` (`cargando`: el modelo aún no estaba en la GPU; `pensando`: el modelo está razonando, y sus bloques `<think>` y su campo `thinking` nunca se envían como texto). El historial se recorta para caber en el contexto de 4096 tokens.
- `POST /apagar` → `{ok: true}` (cierra de forma ordenada los contextos de NEXUS y de Gemini para que Chrome escriba a disco las cookies del perfil y no se pierda la sesión de Google, y unos 0.3 s después termina el proceso. Tauri lo llama antes de matar el sidecar. El backend también cierra los navegadores al recibir SIGTERM/SIGINT/CTRL_BREAK y al apagar el lifespan). Además, tras cada job que usa Gemini (`login_gemini`, `generar`) el contexto de Gemini se cierra al terminar; en el login se esperan ~3 s tras detectar la sesión.
- `POST /asistente/liberar` → `{liberado: boolean, modelo: string}` (descarga el modelo de la GPU al instante con `keep_alive: 0`; la UI lo llama al salir de la vista del asistente y al cerrar la app; `liberado: false` si Ollama no corre). Mientras tanto el modelo se mantiene cargado `asistente_keep_alive_s` segundos (por defecto 90) tras cada uso.
- `POST /asistente/confirmar` body `{id, aceptar: boolean}` → resultado de la acción confirmada.
- `POST /herramientas/pdf` multipart `files[]` + `recortar?: boolean` + `portada?: string` (JSON `DatosPortada` con `profesor` obligatorio) → `{pdf_url}` (cada imagen es una página del PDF, en el orden recibido y recortada si `recortar`; si viene `portada`, la portada va como PRIMERA página, generada con Word y unida con pikepdf; sin `portada` el PDF solo trae las imágenes; 422 `validacion` si `portada` no es JSON válido o no trae `profesor`; 502 `sin_word` si Word no puede convertir la portada). Los archivos se sirven desde `GET /files/herramientas/...`.
- `POST /herramientas/portada` body `DatosPortada & {profesor: string}` → `{docx_url, pdf_url}` (portada suelta).
- `GET /profesores` → `{nombre: string, materias: string[]}[]` (profesores distintos guardados en las materias, para autocompletar; la UI permite también escribir uno a mano).
- Portada: la fecha SIEMPRE es la de hoy (no se acepta `fecha`); ya no hay campos `materia` ni `titulo` en la portada. Los campos de `DatosPortada` omitidos o vacíos se llenan con `Settings` (`aula`, `grupo`, `turno`, `especialidad`, por defecto "144", "5V1", "MATUTINO", "Técnico en Inteligencia Artificial BPI") y el profesor con el de la materia de la tarea. La plantilla `portada_word.docx` usa los marcadores `(AULA)`, `(GRUPO)`, `(TURNO)` y `(ESPECIALIDAD)`.
- MCP: `python -m backend.mcp` expone por stdio las mismas herramientas del asistente (salvo que `entregar_tarea` exige un argumento `confirmar: true`), para usarlas desde cualquier cliente MCP.

## Calificaciones y predicción
Fuentes: SIASE «Consulta de Evaluación» (oficial: PAR 1, EMT, PAR 2, EG y PORT por materia; flujo en `htmls/siase/SIASE_calificaciones.txt`) y la pestaña «Calificaciones» de NEXUS (detalle del portafolio por tarea; `htmls/nexus/nexus_calificaciones.txt`, ya se lee en el sync completo).
```ts
type TipoMateria = "bachillerato" | "carrera" | "portafolio";
type ClaveComponente = "par1" | "emt" | "par2" | "eg" | "portafolio";
type Componente = { clave: ClaveComponente; nombre: string; peso: number; calificacion: number | null; puntos: number | null };
type ElementoPortafolio = { titulo: string; valor: number; puntos: number | null; perdida: boolean };
type Pendiente = { clave: ClaveComponente; titulo: string; peso: number };
type MateriaCalificacion = {
  clave: string; nombre: string; materia_id: string | null; tipo: TipoMateria | null; tipo_manual: boolean;
  componentes: Componente[]; portafolio: ElementoPortafolio[]; pendientes: Pendiente[];
  asegurados: number; maximo_posible: number; proyectada: number; rango: [number, number];
  objetivo: number | null; necesario: number | null; alcanzable: boolean;
  prob_objetivo: number | null; prob_aprobar: number; estado: "bien" | "atento" | "riesgo" | "sin_datos";
};
type ResumenCalificaciones = {
  materias: MateriaCalificacion[];
  semestre: { actual: number; proyectada: number; rango: [number, number]; objetivo: number | null; prob_objetivo: number | null; necesario_promedio: number | null };
  siase_leida_en: string | null;
};
```
- Pesos (puntos sobre 100). `bachillerato`: portafolio 40, PAR 1 10, EMT 15, PAR 2 10, EG 25. `carrera`: portafolio 50, PAR 1 10, EMT 15, PAR 2 10, EG 15. `portafolio` (p. ej. Elección Vocacional): portafolio 100, sin exámenes.
- Tipo: por la suma de `valor` de las tareas del portafolio en NEXUS sin los diagnósticos (≈40 → bachillerato, ≈50 → carrera, ≈100 → portafolio); si no hay NEXUS, por la razón `%`/`Cal` del PORT de SIASE (0.4 / 0.5); si no se puede, `null` y el usuario lo elige (`tipo_manual: true`).
- NEXUS: «-» = sin calificar (NO es 0); los «Diagnostic Evaluation…»/«Diagnóstico» se ignoran siempre. `perdida: true` si la tarea está vencida y no entregada (cuenta como 0 en la proyección, no en `asegurados`).
- `asegurados`: puntos ya ganados (exámenes de SIASE + puntos del portafolio; el portafolio sale del detalle de NEXUS si existe y si no del PORT de SIASE). `maximo_posible` = asegurados + peso de todo lo pendiente no perdido. Las materias de SIASE se emparejan con las de NEXUS por nombre normalizado (sin clave, acentos ni mayúsculas).
- `necesario`: calificación uniforme (0–100) que hace falta en TODO lo pendiente para llegar a `objetivo`; `alcanzable: false` si pasa de 100. `null` sin objetivo o sin pendientes.
- Predicción probabilística: el rendimiento esperado en cada pendiente se estima con un modelo bayesiano simple (media de tus exámenes y de tus tareas, encogida hacia tu promedio general en todas las materias cuando hay pocos datos, con su desviación); Monte Carlo (~5000 muestras, recortadas a 0–100, semilla fija para que sea reproducible) da `proyectada` (media), `rango` (percentiles 10–90), `prob_objetivo` y `prob_aprobar` (≥ 70). El semestre usa las mismas muestras: promedio simple de TODAS las materias.
- `estado`: `riesgo` si `prob_aprobar` < 0.6 o `necesario` para 70 > 90; `atento` si no llega al objetivo (`prob_objetivo` < 0.5); `bien` en otro caso; `sin_datos` si no hay ninguna calificación.
- Calificación aprobatoria: 70.
- `GET /calificaciones` → `ResumenCalificaciones` (calculado al vuelo con lo guardado).
- `POST /siase/calificaciones` → `Job` (tipo nuevo `"calificaciones_siase"`; login SIASE → carrera → «Consulta de Evaluación» → periodo (la única opción distinta de «Selecciona..») → Aceptar → tabla; oculto y sin pausas; selectores en `selectors.py`; `resultado: {materias: number}`). SIASE es independiente de NEXUS: no usa el lock ni la pestaña de NEXUS.
- `PUT /calificaciones/objetivos` body `{semestre?: number | null, materias?: {[clave: string]: number | null}}` → `ResumenCalificaciones` (objetivos 0–100; `null` borra).
- `PUT /calificaciones/tipo` body `{clave: string, tipo: TipoMateria | null}` → `ResumenCalificaciones` (`null` vuelve a la detección automática).
- Herramienta del asistente/MCP nueva: `ver_calificaciones` (devuelve el resumen).

### Calificaciones v2: portafolio de NEXUS, historial, tabla y escenarios
- **Portafolio de NEXUS (fuente preferida del portafolio).** `POST /nexus/portafolio` → `Job` (tipo nuevo `"portafolio_nexus"`): con el lock global y la única pestaña de NEXUS, entra a cada materia desde la lista y abre SOLO la pestaña «Calificaciones» (sin abrir tareas), guarda la tabla como hoy (`storage.set_calificaciones`); `resultado: {materias: number, errores: string[]}`. Cuando una materia tiene detalle de NEXUS, el portafolio (puntos, pendientes, tipo) sale de NEXUS aunque SIASE traiga PORT. `ResumenCalificaciones` agrega `nexus_leido_en: string | null`.
- **Historial.** Tabla `historial_calificaciones` con materias de semestres anteriores: `{periodo, nombre: string | null, tipo: TipoMateria | null, par1?, par2?, emt?, eg?, port?, total}` (calificaciones 0–100; `null`/ausente = no se conoce). Al arrancar, si la tabla está vacía y existe `data/historial_semestres.json` (formato `{semestres: [{periodo, materias: [...]}]}`), se importa una vez. `GET /calificaciones/historial` → `{semestres: {periodo: string; materias: ...[]}[]; resumen: {[clave in "par1"|"par2"|"emt"|"eg"|"portafolio"|"total"]: {media: number, desv: number, n: number, prob_100: number}}}`; `PUT /calificaciones/historial` body `{semestres}` reemplaza todo. (Kárdex: pendiente hasta tener su HTML.)
- **Modelo «Mío» (el probabilístico por defecto).** Cada pendiente se predice con una distribución por componente construida desde el historial: remuestreo suavizado de las calificaciones históricas de ese componente (PAR 1, PAR 2, EMT, EG, portafolio en % del valor), que respeta la frecuencia real de 100 (`prob_100`) sin asumir 100 siempre, desplazada por cómo vas este semestre en esa materia: desplazamiento = (media actual de la materia en ese grupo − media histórica del grupo) · n/(n+3), con n = observaciones actuales; recortado a 0–100; sesgo compartido por materia. Sin historial, se usa el modelo actual. Probabilidad: si es > 0 pero < 0.005 se reporta tal cual (la UI muestra «<1 %»); si `alcanzable` es false, 0.
- **Cuidado.** `MateriaCalificacion` agrega `alertas: {tipo: "bajo_historico" | "examen_bajo" | "puntos_perdidos" | "tipo_dudoso"; detalle: string}[]` y `en_cuidado: boolean`:
  - `bajo_historico`: un componente (o la media de exámenes / del portafolio calificado) está > 5 puntos debajo de tu media histórica de ese componente.
  - `examen_bajo`: cualquier examen ya presentado (incluido PAR 1) con calificación ≤ 80 (perdiste ≥ 20 puntos).
  - `tipo_dudoso`: el tipo elegido a mano no coincide con el que sugiere NEXUS por la suma de valores del portafolio («NEXUS suma X puntos de portafolio; el tipo elegido espera Y»).
  - `puntos_perdidos`: puntos perdidos acumulados (peso evaluado − puntos ganados, sin contar tareas `perdida`) > 100 − mínimo histórico de `total` (≈ 6 con el historial actual; 6 si no hay historial).
  - `estado`: `riesgo` con la regla anterior (`prob_aprobar` < 0.6 o `necesario` para 70 > 90); si hay alertas, como mínimo `atento`. El desplazamiento del modelo no toca los 100 del remuestreo (se conserva `prob_100`).
- **Tabla de resumen** (`MateriaCalificacion` agrega): `portafolio_pts`, `portafolio_max` (peso del portafolio), `examenes_pts`, `examenes_max` (suma de pesos de exámenes), `total_pts` (= asegurados), `evaluado_pts` (peso de lo ya calificado, incluidas tareas perdidas) y `pct_evaluado` (= total_pts / evaluado_pts · 100, `null` si nada evaluado).
- **Escenarios.** `POST /calificaciones/escenario` body `Escenario` → `ResultadoEscenario`:
  ```ts
  type Escenario = { preset: "pesimista" | "realista" | "optimista" | "mio" | "personalizado"; examenes?: number; tareas?: number; materias?: {[clave: string]: {examenes?: number; tareas?: number; pendientes?: {[indice: number]: number}; esfuerzo?: boolean}} };
  type ResultadoEscenario = { materias: {clave: string; final: number; pendientes: {clave: ClaveComponente; titulo: string; peso: number; nota: number}[]}[]; semestre: number };
  ```
  Presets (valores supuestos por pendiente, sobreescribibles con `examenes`/`tareas` globales, luego por materia y luego por pendiente):
  - `pesimista`: igual o peor que lo que llevas: por grupo (exámenes/tareas) de cada materia, min(media actual del grupo, media histórica) − 1 desviación histórica; sin datos actuales, media histórica − 1 desv.
  - `realista`: la media del modelo «Mío» para cada pendiente.
  - `optimista`: 100 en todo, salvo en los grupos de materias con alerta, donde se usa la media actual del grupo; con `esfuerzo: true` en una materia, esa materia va a 100 aunque tenga alerta.
  - `mio`: igual que `realista` pero `final` es la media de Monte Carlo (el mismo número que `proyectada`).
  - `personalizado`: solo los valores dados; lo no dado usa `realista`.
  `final` = asegurados + Σ nota·peso/100 (tareas `perdida` = 0); `semestre` = promedio simple de todas las materias.
- **Regla del portafolio (corrección 2026-10-16).** Del portafolio de NEXUS solo cuenta como evaluado lo que tiene calificación: una tarea sin calificar («-») significa que aún no se ha revisado, NO que se perdió. `perdida` deja de restar en todo cálculo (asegurados, evaluado_pts, pct_evaluado, alertas, proyección y escenarios); queda solo como aviso visual «posible no entregada» y su emparejamiento con las tareas guardadas debe ser 1 a 1 (títulos repetidos se emparejan en orden de fecha, nunca una tarea vencida marca a todas las homónimas). `pct_evaluado` = (puntos de exámenes presentados + puntos de tareas calificadas) / (pesos de esos exámenes + valores de esas tareas) · 100.
- **Kárdex.** `POST /siase/calificaciones` además lee el Kárdex en la misma sesión de SIASE (enlace «Kardex» del menú, se carga en el frame `center`; HTML en `htmls/siase/kardex.txt`): tabla Sem. | Mod. | Clave | Materia | 1 Opo. … 6 Opo | Labs. La calificación final es la de la última oportunidad con valor. Las filas sin calificación (semestre actual y futuros) se ignoran. Se guarda en `historial_calificaciones` como `{periodo: "Semestre N", nombre, clave, tipo: null, total}` y reemplaza las filas previas de Kárdex (las importadas del JSON se conservan; si una materia aparece en ambos, el `total` del Kárdex manda y se conservan los componentes del JSON). `resultado` agrega `kardex: number`. El `total` del Kárdex alimenta el resumen histórico de `total` y el umbral de `puntos_perdidos`.

- **Portafolio con y sin NEXUS (2026-10-16).** Con detalle de NEXUS, la `calificacion` del componente portafolio es puntos/valor de las tareas calificadas · 100 y `puntos` la suma de NEXUS; sin NEXUS, `calificacion` es null (el «Cal» de SIASE es acumulado, no desempeño) y `puntos` son los de SIASE. Si la suma de `valor` de NEXUS es menor que el peso del portafolio del tipo, se agrega el pendiente «Portafolio aún no publicado» por la diferencia.
