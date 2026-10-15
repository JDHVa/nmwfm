# nmwfm — Asistente local de tareas NEXUS (UANL)

## Objetivo
App de escritorio 100% local que automatiza: SIASE (login) → NEXUS → materia → Estructura → etapa → dimensión/evidencia → leer descripción, contenido, criterios y rúbrica → el usuario agrega imágenes/texto (las imágenes se recortan a la página y se unen en un PDF) → Gemini web genera la tarea → documento Word + PDF con portada estandarizada (profe de la materia, fecha de hoy) → revisión del usuario → entrega del PDF en NEXUS.

## Stack
- UI: Tauri v2 + React + TypeScript + Vite + Tailwind + shadcn/ui + React Bits (`npx shadcn@latest add https://reactbits.dev/r/<Componente>-TS-TW`), en `app/`.
- Backend: Python 3.12 (`.venv`), FastAPI + uvicorn como sidecar de Tauri, en `backend/`. Contrato de API: `docs/api.md`.
- Navegador: Playwright con Google Chrome instalado (`channel="chrome"`), perfil persistente en `data/browser_profile/`.
- Imágenes: OpenCV + Pillow + img2pdf. Documentos: python-docx + docxcompose + mistune; PDF con docx2pdf (MS Word).
- Datos: SQLite en `data/nmwfm.db`; credenciales en keyring (Windows Credential Manager).
- Plantilla de portada: `portada_word.docx` (marcadores `(NOMBRE DE LA PERSONA)`, `(MATRICULA DE LA PERSONA)`, `(NOMBRE DEL PROFE)`, `(DIA XX)`, `(MES)`, `(AÑO)`).
- Referencia del DOM: `htmls/siase/SIASE.txt`, `htmls/nexus/NEXUS.txt`.

## Correr en DEV
Todo desde la raíz del repo (`npm install` instala también `app/`):
- `npm run dev`: backend + `tauri dev` a la vez (el hook `pretauri` crea un sidecar de relleno si falta)
- `npm run dev:ui`: solo la interfaz en el navegador con backend simulado (`app/.env.mock`)
- `npm run backend`: solo el backend
- `npm test`: pytest + vitest · `npm run lint`: ruff + eslint
- `npm run build`: sidecar real con PyInstaller + instalador de Tauri

## Reglas
- Sin comentarios en el código salvo que sean estrictamente necesarios (un porqué no obvio o un workaround del sitio). Nunca comentarios que repitan lo que el código ya dice.
- Si surge una duda, se interrumpe el flujo y se le pregunta al usuario antes de asumir.
- Roles de desarrollo: **Sonnet 5.5 (`claude-sonnet-5-5`) escribe el código; Opus 5.5 (`claude-opus-5-5`) solo revisa e integra.** Hay un agente para la UI y otro para el backend, cada uno en su worktree. Opus define el contrato de API y los criterios de aceptación, revisa cada entrega y devuelve correcciones al mismo agente. Nada se integra sin la aprobación de Opus ni con lint/tests en rojo. Las plantillas de prompts están en `.claude/prompts/`.
- Instalaciones de herramientas o dependencias del sistema: se delegan a agentes con modelo **Haiku**.
- No automatizar el login de Google; Gemini solo a través del perfil persistente y a ritmo humano (pausas aleatorias, escritura no instantánea). Ante captcha o aviso, pausar y pedir intervención.
- Credenciales solo en keyring; nada sensible en el repo, logs ni SQLite.
- Nunca entregar en NEXUS sin revisión, salvo que el flag "entregar sin revisar" esté activo.
- Selectores de SIASE/NEXUS centralizados en `backend/core/selectors.py`.
- En la rúbrica se ignora el criterio de "responsabilidad" al armar el prompt.
- `DEV=True` → navegador visible (headless=False).
- Textos de la UI en español.
- NEXUS es una SPA de Angular: navegar siempre con clics desde la lista de materias, no por URL.
