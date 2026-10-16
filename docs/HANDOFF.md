# Handoff — estado del proyecto nmwfm (2026-10-15)

Documento para continuar en una conversación nueva. Leer primero `CLAUDE.md` (reglas, stack, comandos) y `docs/api.md` (contrato backend ↔ UI).

## Cómo se trabaja
- Opus revisa e integra; Sonnet escribe código (un agente para backend y otro para UI, cada uno en su worktree, rama `worktree-agent-*`); Haiku hace instalaciones.
- Flujo: Opus actualiza el contrato en `docs/api.md` → le pasa la tarea al agente → revisa → `git merge --no-ff` a `main` → `npm test` (pytest + vitest) en verde → `git push origin main`.
- Si la UI agrega paquetes npm, en main hay que correr `npm install` (vía Haiku) antes de probar.
- Si surge una duda, se le pregunta al usuario antes de asumir. El usuario sigue la sesión desde el celular (remote-control).
- Repo: https://github.com/JDHVa/nmwfm (rama `main`, etiqueta de respaldo `v0.1-respaldo`).

## Estado actual (main, último push ebaaee2)
- 352 tests de backend y 78 de UI en verde, más 4 e2e.
- **Funciona en vivo (probado con la cuenta real):** login SIASE → NEXUS, sync completo de una sola pestaña (~45 min: 10 materias, 116 tareas, detalle, rúbricas, estado de entregas). NEXUS SOLO admite una pestaña/instancia (ver CLAUDE.md).
- **Tipos de tarea:** `dimension`, `evidencia`, `examen` (recordatorio, no se abre), `pia` (ruta ProductoIntegrador, soporte según `htmls/nexus/pia.txt`, sin validar en vivo). Las autoevaluaciones se ocultan.
- **UI:** login, Materias, Próximas entregas, tarea con Stepper (Insumos → Generar → Revisar → Entregar), indicaciones del profesor, búsqueda Ctrl+K, novedades y alertas, calificaciones (lector genérico), respaldo, diagnóstico, bandeja del sistema, instalador `.msi`/`.exe` (npm run build).
- **Asistente local:** Ollama 0.40.4 con `qwen3:4b-instruct-2507-q4_K_M` (por defecto, 3.2 GB de VRAM, keep_alive 90 s configurable, liberar al salir). Chat SSE con herramientas (buscar, ver, próximas, indicaciones, PDF, portada, sync, revisar entregas, generar, entregar con confirmación obligatoria) y salvaguardas de reintento. Probado en vivo: 2.6–7.2 s por respuesta. MCP: `python -m backend.mcp` (mcp 1.30, NO v2).
- **Instalado en la máquina:** Chrome, Rust, Build Tools (registro del VS Installer incompleto pero compila), Graphviz 16.1 (dot), tzdata, rapidocr-onnxruntime, onnxruntime-directml + modelo `data/models/u2netp.onnx` (recorte de página en GPU), Ollama + qwen3:4b y qwen3:4b-instruct.

## Trabajo EN CURSO al cerrar esta conversación (ramas de los agentes, sin integrar)
**Backend: INTEGRADO en main (380 tests).** Los puntos 1-4 de abajo ya están hechos:
1. `/files/herramientas/*` da 404: falta "herramientas" en `PUBLIC_DIRS` (api.py). Probable causa de "No se pudo abrir la portada".
2. Imágenes → PDF: una imagen por página y portada OPCIONAL como primera página (`portada?: {...}`).
3. Gemini se cierra solo: el sync headless relanza el contexto compartido. Solución: Gemini con su propio perfil persistente `data/gemini_profile` (visible) y NEXUS en `data/browser_profile` (headless), con locks independientes.
4. No sincronizar al abrir la app (solo la primera vez o con el scheduler).

**UI (`worktree-agent-a568446ae5ae93689`):**
1. No lanzar sync al entrar (salvo la primera vez).
2. Asistente como vista inicial y primer ítem del Dock.
3. Rediseño estilo Claude.ai: paleta neutra cálida en TODA la app (claro #FAF9F5 / oscuro #262624, acento #C96442), sin neón ni degradados; fondo liso.
4. Chat en una columna del ~70 % del ancho, burbujas del usuario a la derecha y texto limpio del asistente, entrada grande abajo, saludo con sugerencias e historial de conversaciones.
5. Imágenes → PDF con reordenar, recortar sí/no y el check "Agregar portada".

Para retomarlos: revisar `git log main..worktree-agent-<id>` en cada rama. Si los agentes ya no existen, lanzar agentes nuevos con estas mismas tareas.

## Pendientes que necesitan al usuario
- **Gemini en vivo:** iniciar sesión una vez (Configuración → "Iniciar sesión en Gemini") y probar Generar en una tarea normal. Los selectores de Gemini (`backend/core/selectors.py`) son suposiciones.
- **Entrega real:** con una tarea de prueba, con el usuario presente. El selector del botón de cerrar del diálogo es una suposición.
- **HTML de la pestaña "Calificaciones"** para un lector preciso. (Recursos se eliminó por decisión del usuario.)
- **Validar en vivo:** el PIA, el aviso de sesión cerrada de NEXUS (`NX_SESION_CERRADA`) y el instalador en una instalación limpia (bandeja y notificaciones).
- **Velocidad del sync:** correr un sync en DEV y leer `data/debug/api/catalogo-*.json` para decidir si leer los datos del JSON de NEXUS en lugar del DOM (meta: < 10 min).
- **Seguridad:** el usuario pegó su contraseña de SIASE en el chat; recomendarle cambiarla. Está guardada en el keyring de Windows, no en archivos.

## Comandos rápidos (desde la raíz)
`npm run dev` (backend + app) · `npm run dev:ui` (UI con mock) · `npm run backend` · `npm test` · `npm run lint` · `npm run build` · `npm run test:e2e`
