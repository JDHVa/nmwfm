# Handoff — estado del proyecto nmwfm (2026-10-16)

Documento para continuar en una conversación nueva. Leer primero `CLAUDE.md` (reglas, stack, comandos) y `docs/api.md` (contrato backend ↔ UI).

## Cómo se trabaja
- Opus revisa e integra; Sonnet escribe código (un agente para backend y otro para UI, cada uno en su worktree, rama `worktree-agent-*`); Haiku hace instalaciones.
- Flujo: Opus actualiza el contrato en `docs/api.md` → le pasa la tarea al agente → revisa → `git merge --no-ff` a `main` → `npm test` (pytest + vitest) en verde → `git push origin main`.
- Si la UI agrega paquetes npm, en main hay que correr `npm install` (vía Haiku) antes de probar.
- Si surge una duda, se le pregunta al usuario antes de asumir. El usuario sigue la sesión desde el celular (remote-control).
- Repo: https://github.com/JDHVa/nmwfm (rama `main`, etiqueta de respaldo `v0.1-respaldo`).

## Estado actual (main, 2026-10-16, último push 509cf61)
- 419 tests de backend y 91 de UI en verde (vitest con maxWorkers 4 y timeouts amplios porque la máquina suele estar cargada).
- **Funciona en vivo:** login SIASE → NEXUS, sync completo (~45 min, 10 materias, 116 tareas). NEXUS SOLO admite una pestaña/instancia.
- **Gemini validado en vivo (2026-10-15):** sesión persistente en `data/gemini_profile`, editor `div.ql-editor[role=textbox]`, botón «Enviar mensaje», carga con `button[aria-label='Subidas y herramientas']` → `button[data-test-id='local-images-files-uploader-button']` → chip `uploader-file-preview`. Se probó mandar «hola» y adjuntar un PDF. El contexto de Gemini se cierra ordenadamente tras cada job y al salir (`POST /apagar` desde Tauri) para que Google no invalide la sesión. La ventana de login siempre es visible.
- **Generar:** a Gemini solo van el prompt y `insumos.pdf`; la portada se genera aparte y se une como primera página. Espera configurable antes de Enviar (`gemini_espera_envio_s`, 3 s). Instrucciones fijas editables en Configuración (incluida «Referencias APA 7», que se puede quitar por generación) y «Ver prompt».
- **Portada:** datos Aula/Grupo/Turno/Especialidad en Configuración (defaults 144, 5V1, MATUTINO, Técnico en IA BPI), fecha siempre de hoy, profesor por combobox (`GET /profesores`) o a mano. Sin materia ni título.
- **Jobs:** botón «Detener» en todos (`POST /jobs/{id}/cancelar`), que también cierra el navegador del job.
- **UI:** estilo Claude (paleta cálida, acento #B85636 / #D97757) con fondo Silk apagado en claro (con hover) y Galaxy apagado y optimizado en oscuro (dpr 0.5, 2 capas, 30 FPS).
- **Asistente:** Ollama `qwen3:4b-instruct-2507-q4_K_M` (sin razonamiento, rápido); sin emojis (prompt + filtro).

## Pendientes que necesitan al usuario
- **Generar completo en vivo:** probarlo en una tarea normal. Hubo un atasco sin diagnosticar (falta saber en qué paso); la espera de respuesta y la lectura (botón Copiar) aún no se validaron en vivo.
- **Entrega real:** con una tarea de prueba, con el usuario presente. El selector del botón de cerrar del diálogo es una suposición.
- **HTML de la pestaña "Calificaciones"** para un lector preciso. (Recursos se eliminó por decisión del usuario.)
- **Validar en vivo:** el PIA, el aviso de sesión cerrada de NEXUS (`NX_SESION_CERRADA`) y el instalador en una instalación limpia (bandeja y notificaciones).
- **Velocidad del sync:** correr un sync en DEV y leer `data/debug/api/catalogo-*.json` para decidir si leer los datos del JSON de NEXUS en lugar del DOM (meta: < 10 min).
- **Seguridad:** el usuario pegó su contraseña de SIASE en el chat; recomendarle cambiarla. Está guardada en el keyring de Windows, no en archivos.

## Comandos rápidos (desde la raíz)
`npm run dev` (backend + app) · `npm run dev:ui` (UI con mock) · `npm run backend` · `npm test` · `npm run lint` · `npm run build` · `npm run test:e2e`
