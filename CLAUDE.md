# nmwfm — Asistente local de tareas NEXUS (UANL)

## Objetivo
App de escritorio 100% local que automatiza: SIASE (login) → NEXUS → materia → Estructura → etapa → dimensión/evidencia → leer descripción, contenido, criterios y rúbrica → el usuario agrega imágenes/texto (las imágenes se recortan a la página y se unen en un PDF) → Gemini web genera la tarea → documento Word + PDF con portada estandarizada (profe de la materia, fecha de hoy) → revisión del usuario → entrega del PDF en NEXUS.

## Stack
- UI: Tauri v2 + React + TypeScript + Vite + Tailwind + shadcn/ui + React Bits (`npx shadcn@latest add https://reactbits.dev/r/<Componente>-TS-TW`), en `app/`.
- Backend: Python 3.12 (`.venv`), FastAPI + uvicorn como sidecar de Tauri, en `backend/`. Contrato de API: `docs/api.md`.
- Navegador: Playwright con Google Chrome instalado (`channel="chrome"`), perfil persistente en `data/browser_profile/`.
- Imágenes: OpenCV + Pillow + img2pdf. Documentos: python-docx + docxcompose + mistune; PDF con docx2pdf (MS Word).
- Datos: SQLite en `data/nmwfm.db`; credenciales en keyring (Windows Credential Manager).
- Plantilla de portada: `portada_word.docx` (marcadores `(NOMBRE DE LA PERSONA)`, `(MATRICULA DE LA PERSONA)`, `(NOMBRE DEL PROFE)`, `(AULA)`, `(GRUPO)`, `(TURNO)`, `(ESPECIALIDAD)`, `(DIA XX)`, `(MES)`, `(AÑO)`).
- Referencia del DOM: `htmls/siase/SIASE.txt`, `htmls/nexus/NEXUS.txt`.

## Correr en DEV
Todo desde la raíz del repo (`npm install` instala también `app/`):
- `npm run dev`: backend + `tauri dev` a la vez (el hook `pretauri` crea un sidecar de relleno si falta)
- `npm run dev:ui`: solo la interfaz en el navegador con backend simulado (`app/.env.mock`)
- `npm run backend`: solo el backend
- `npm test`: pytest + vitest · `npm run lint`: ruff + eslint
- `npm run build`: sidecar real con PyInstaller + instalador de Tauri. Genera `app/src-tauri/target/release/bundle/msi/nmwfm_0.1.0_x64_en-US.msi` y `.../nsis/nmwfm_0.1.0_x64-setup.exe` (unos 138 MB; tarda varios minutos)
- `npm run test:e2e`: pruebas de punta a punta con Playwright (Chrome instalado) contra la UI con backend simulado

## Instalar la app
1. Genera el instalador con `npm run build` (necesita `.venv` con PyInstaller, Rust y Chrome instalado).
2. Ejecuta el `.exe` (NSIS) o el `.msi` de `app/src-tauri/target/release/bundle/`.
3. La app instalada lanza sola el sidecar del backend (puerto aleatorio y token por sesión) con `NMWFM_DEV=0` y guarda sus datos (base de datos, perfil del navegador, insumos y generaciones) en `%LOCALAPPDATA%\mx.nmwfm.app`. Cerrar la ventana la deja en la bandeja del sistema; «Salir» está en el menú de su ícono.

## Servidor MCP (herramientas para Claude)
`python -m backend.mcp` expone por stdio las mismas herramientas del asistente (`buscar_tareas`, `ver_tarea`, `proximas_entregas`, `agregar_indicaciones`, `reemplazar_indicaciones`, `crear_pdf_imagenes`, `generar_portada`, `sincronizar`, `revisar_entregas`, `generar_tarea`, `entregar_tarea`). `entregar_tarea` exige `confirmar: true` y solo debe usarse tras la aprobación explícita del usuario. Las herramientas lentas (sincronizar, generar, entregar, revisar) esperan a que termine su trabajo y devuelven el resultado.
- Claude Code: `claude mcp add nmwfm -- C:\ruta\al\repo\.venv\Scripts\python.exe -m backend.mcp` (ejecútalo desde la raíz del repo para que `backend` se resuelva).
- Claude Desktop: en `claude_desktop_config.json` agrega `"mcpServers": {"nmwfm": {"command": "C:\\ruta\\al\\repo\\.venv\\Scripts\\python.exe", "args": ["-m", "backend.mcp"], "cwd": "C:\\ruta\\al\\repo"}}` y reinicia la app.
- El servidor MCP usa la misma carpeta `data/` que la app: ciérrala antes de usar `sincronizar`, `generar_tarea` o `entregar_tarea` desde MCP, porque el perfil del navegador no puede abrirse dos veces.

## Reglas
- Sin comentarios en el código salvo que sean estrictamente necesarios (un porqué no obvio o un workaround del sitio). Nunca comentarios que repitan lo que el código ya dice.
- Si surge una duda, se interrumpe el flujo y se le pregunta al usuario antes de asumir.
- Roles de desarrollo: **Sonnet 5.5 (`claude-sonnet-5-5`) escribe el código; Opus 5.5 (`claude-opus-5-5`) solo revisa e integra.** Hay un agente para la UI y otro para el backend, cada uno en su worktree. Opus define el contrato de API y los criterios de aceptación, revisa cada entrega y devuelve correcciones al mismo agente. Nada se integra sin la aprobación de Opus ni con lint/tests en rojo. Las plantillas de prompts están en `.claude/prompts/`.
- Instalaciones de herramientas o dependencias del sistema: se delegan a agentes con modelo **Haiku**.
- Velocidad: SIASE/NEXUS al máximo (`fill` directo, sin pausas humanas, esperas por selector y no por tiempo, bloquear imágenes/fuentes/media). Gemini semi-rápido: el prompt se pega de golpe (como Ctrl+V), con solo un par de pausas cortas.
- No automatizar el login de Google; Gemini solo a través del perfil persistente. Ante captcha o aviso, pausar y pedir intervención.
- Credenciales solo en keyring; nada sensible en el repo, logs ni SQLite.
- Nunca entregar en NEXUS sin revisión, salvo que el flag "entregar sin revisar" esté activo.
- Selectores de SIASE/NEXUS centralizados en `backend/core/selectors.py`.
- En la rúbrica se ignora el criterio de "responsabilidad" al armar el prompt.
- `DEV=True` → navegador visible (headless=False).
- Textos de la UI en español.
- NEXUS es una SPA de Angular: navegar siempre con clics desde la lista de materias, no por URL.
- NEXUS solo admite UNA instancia abierta: abrir NEXUS en otra pestaña/contexto mata la anterior. Una sola pestaña de NEXUS en todo el backend, reutilizada entre jobs y protegida por el lock global; nada de paralelismo ni contextos aislados. El usuario no usa NEXUS a mano mientras la app trabaja.
