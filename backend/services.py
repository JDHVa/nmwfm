import asyncio
import contextlib
from datetime import date
from pathlib import Path

from playwright.async_api import Page

from . import config
from .core import documents, images, nexus, selectors, siase
from .core.browser import BrowserManager
from .core.gemini import GeminiWeb, LLMProvider
from .core.prompt_builder import PromptData, build_prompt
from .core.storage import Credentials, Storage
from .core.types import Hooks, Rubrica
from .jobs import JobContext, JobManager


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class AppState:
    def __init__(
        self,
        data_dir: Path,
        token: str,
        *,
        dev: bool = config.DEV,
        credentials: Credentials | None = None,
        gemini: LLMProvider | None = None,
    ):
        self.paths = config.Paths(data_dir)
        self.paths.ensure()
        self.token = token
        self.dev = dev
        self.storage = Storage(self.paths.db)
        self.credentials = credentials or Credentials()
        self.jobs = JobManager()
        self.browser = BrowserManager(self.paths.browser_profile, dev)
        self.gemini: LLMProvider = gemini or GeminiWeb(self.browser)
        self.nexus_page: Page | None = None

    def file_url(self, path: str | Path | None) -> str | None:
        if not path:
            return None
        rel = Path(path).resolve().relative_to(self.paths.data.resolve())
        return "/files/" + rel.as_posix()

    def settings_public(self) -> dict:
        s = self.storage.get_settings()
        return {
            **s,
            "tiene_password": self.credentials.has(s["cuenta"]),
            "dev": self.dev,
        }

    def insumo_public(self, row: dict) -> dict:
        out: dict = {
            "id": row["id"],
            "tipo": row["tipo"],
            "orden": row["orden"],
            "rotacion": row["rotacion"],
            "usar_recorte": bool(row["usar_recorte"]),
        }
        if row["tipo"] == "imagen":
            out["original_url"] = self.file_url(row["original_path"])
            out["recortada_url"] = self.file_url(row["recortada_path"])
            thumb = Path(row["recortada_path"]).with_name(f"{row['id']}_thumb.jpg")
            out["miniatura_url"] = self.file_url(thumb) if thumb.exists() else None
        else:
            out["texto"] = row["texto"]
        return out

    def generacion_public(self, row: dict) -> dict:
        return {
            "tarea_id": row["tarea_id"],
            "markdown": row["markdown"],
            "docx_url": self.file_url(row["docx_path"]),
            "pdf_url": self.file_url(row["pdf_path"]),
            "creada_en": row["creada_en"],
        }

    def tarea_detalle_public(self, tarea: dict, detalle: dict) -> dict:
        return {**tarea, **detalle}

    async def close(self) -> None:
        await self.jobs.shutdown()
        await self.browser.close()
        self.storage.close()


def require_credentials(state: AppState) -> tuple[str, str]:
    cuenta = state.storage.get_settings()["cuenta"]
    password = state.credentials.get(cuenta)
    if not cuenta or not password:
        raise ApiError(400, "sin_credenciales", "Configura tu cuenta y contraseña de SIASE.")
    return cuenta, password


async def ensure_nexus(state: AppState, hooks: Hooks) -> Page:
    page = state.nexus_page
    if page is not None and not page.is_closed() and "plataformanexus.uanl.mx" in page.url:
        return page
    cuenta, password = require_credentials(state)
    ctx = await state.browser.context()
    state.nexus_page = await siase.login(ctx, cuenta, password, hooks)
    return state.nexus_page


async def run_validar_siase(state: AppState, ctx: JobContext) -> dict:
    cuenta = state.storage.get_settings()["cuenta"]
    password = state.credentials.get(cuenta)
    if not cuenta or not password:
        raise ApiError(400, "sin_credenciales", "Faltan credenciales")
    async with state.browser.lock:
        browser_ctx = await state.browser.context()
        await siase.validar(browser_ctx, cuenta, password, ctx.hooks())
    return {"valido": True}


async def run_sync(state: AppState, ctx: JobContext) -> dict:
    hooks = ctx.hooks()
    async with state.browser.lock:
        await ctx.update("Iniciando sesión", 0.0)
        page = await ensure_nexus(state, hooks)
        await ctx.update("Leyendo materias", 0.12)
        materias = await nexus.leer_materias(page)
        for m in materias:
            state.storage.upsert_materia(m.id, m.nombre, m.orden)
        total = max(len(materias), 1)
        for i, m in enumerate(materias):
            await ctx.update(f"Materia {i + 1}/{len(materias)}: {m.nombre}", 0.15 + 0.8 * i / total)
            portada = await nexus.abrir_materia(page, i)
            state.storage.set_portada(m.id, portada.profesor, portada.periodo)
            etapas = await nexus.abrir_estructura(page)
            state.storage.replace_estructura(m.id, etapas)
            await nexus.volver_a_lista(page)
    return {"materias": len(materias)}


async def _abrir_tarea_nexus(state: AppState, page: Page, tarea_id: str):
    pos = state.storage.tarea_posicion(tarea_id)
    if pos is None:
        raise ApiError(404, "tarea_no_encontrada", "La tarea no existe.")
    _, etapa_idx, tarea_idx = pos
    tarea = state.storage.get_tarea(tarea_id)
    if not await page.locator(selectors.NX_CARD).count():
        await nexus.volver_a_lista(page)
    materias = await nexus.leer_materias(page)
    indice = next((m.orden for m in materias if m.id == tarea["materia_id"]), None)
    if indice is None:
        raise ApiError(404, "materia_no_encontrada", "La materia ya no aparece en NEXUS.")
    await nexus.abrir_materia(page, indice)
    await nexus.abrir_estructura(page)
    return await nexus.abrir_tarea(page, etapa_idx, tarea_idx)


async def traer_detalle(state: AppState, tarea_id: str) -> dict:
    if state.storage.tarea_posicion(tarea_id) is None:
        raise ApiError(404, "tarea_no_encontrada", "La tarea no existe.")
    async with state.browser.lock:
        page = await ensure_nexus(state, Hooks())
        detalle = await _abrir_tarea_nexus(state, page, tarea_id)
        state.storage.set_detalle(tarea_id, detalle)
        await nexus.volver_a_lista(page)
    return state.storage.get_detalle(tarea_id)


async def run_login_gemini(state: AppState, ctx: JobContext) -> dict:
    async with state.browser.lock:
        await state.gemini.iniciar_sesion(ctx.hooks())
    return {"sesion": True}


def _insumo_refs(state: AppState, tarea_id: str) -> list[images.InsumoRef]:
    refs = []
    for row in state.storage.list_insumos(tarea_id):
        refs.append(
            images.InsumoRef(
                tipo=row["tipo"],
                original=Path(row["original_path"]) if row["original_path"] else None,
                recortada=Path(row["recortada_path"]) if row["recortada_path"] else None,
                texto=row["texto"],
                rotacion=row["rotacion"],
                usar_recorte=bool(row["usar_recorte"]),
            )
        )
    return refs


def _generacion_dir(state: AppState, tarea_id: str) -> Path:
    return state.paths.generaciones / tarea_id


async def run_generar(
    state: AppState, ctx: JobContext, tarea_id: str, instrucciones_extra: str | None
) -> dict:
    tarea = state.storage.get_tarea(tarea_id)
    materia = state.storage.get_materia(tarea["materia_id"])
    settings = state.storage.get_settings()
    if not materia["profesor"]:
        raise ApiError(400, "sin_profesor", "Falta el profesor de la materia; sincroniza primero.")
    if not settings["nombre"] or not settings["matricula"]:
        raise ApiError(400, "sin_datos_portada", "Configura tu nombre y matrícula en ajustes.")

    detalle = state.storage.get_detalle(tarea_id)
    if detalle is None:
        await ctx.update("Leyendo la tarea en NEXUS", 0.05)
        detalle = await traer_detalle(state, tarea_id)

    out_dir = _generacion_dir(state, tarea_id)
    refs = _insumo_refs(state, tarea_id)
    pdf_insumos = None
    if refs:
        await ctx.update("Armando el PDF de insumos", 0.3)
        pdf_insumos = await asyncio.to_thread(images.build_pdf, refs, out_dir / "insumos.pdf")

    prompt = build_prompt(
        PromptData(
            materia=materia["nombre"],
            titulo=tarea["titulo"],
            numero=tarea["numero"],
            tipo=tarea["tipo"],
            puntos=tarea["puntos"],
            actividades=detalle["actividades"],
            contenido=detalle["contenido"],
            criterios_desempeno=detalle["criterios_desempeno"],
            rubrica=Rubrica.from_dict(detalle["rubrica"]) if detalle["rubrica"] else None,
            instrucciones_extra=instrucciones_extra,
            tiene_insumos=pdf_insumos is not None,
        )
    )
    await ctx.update("generando", 0.45)
    async with state.browser.lock:
        markdown = await state.gemini.generar(prompt, pdf_insumos, ctx.hooks())

    await ctx.update("Creando el documento Word", 0.88)
    gen = await asyncio.to_thread(_construir_documentos, state, tarea, materia, settings, markdown)
    state.storage.set_estado(tarea_id, "generada")
    resultado = state.generacion_public(gen)
    if settings["entregar_sin_revisar"]:
        await ctx.update("entregando", 0.95)
        await run_entregar(state, ctx, tarea_id)
        resultado["entregada"] = True
    return resultado


def _construir_documentos(
    state: AppState, tarea: dict, materia: dict, settings: dict, markdown: str
) -> dict:
    out_dir = _generacion_dir(state, tarea["id"])
    mapping = documents.marcadores(
        settings["nombre"], settings["matricula"], materia["profesor"], date.today()
    )
    docx_path = documents.build_final_docx(
        config.PORTADA_TEMPLATE, markdown, out_dir / "tarea.docx", mapping, out_dir / "tmp"
    )
    pdf_path = documents.export_pdf(docx_path, out_dir / "tarea.pdf")
    return state.storage.set_generacion(tarea["id"], markdown, str(docx_path), str(pdf_path))


async def reconstruir_pdf(state: AppState, tarea_id: str) -> dict:
    gen = state.storage.get_generacion(tarea_id)
    if gen is None:
        raise ApiError(404, "sin_generacion", "Esta tarea todavía no tiene documento generado.")
    docx_path = Path(gen["docx_path"])
    pdf_path = await asyncio.to_thread(documents.export_pdf, docx_path, Path(gen["pdf_path"]))
    return state.generacion_public(
        state.storage.set_generacion(tarea_id, gen["markdown"], str(docx_path), str(pdf_path))
    )


async def run_entregar(state: AppState, ctx: JobContext, tarea_id: str) -> dict:
    tarea = state.storage.get_tarea(tarea_id)
    if tarea is None:
        raise ApiError(404, "tarea_no_encontrada", "La tarea no existe.")
    gen = state.storage.get_generacion(tarea_id)
    if gen is None:
        raise ApiError(400, "sin_generacion", "Genera el documento antes de entregar.")
    await ctx.update("entregando", 0.95)
    if tarea["estado"] == "entregada":
        await ctx.log("Reemplazando entrega previa")
    pdf_path = Path(gen["pdf_path"])
    hooks = ctx.hooks()
    async with state.browser.lock:
        page = await ensure_nexus(state, hooks)
        await _abrir_tarea_nexus(state, page, tarea_id)
        try:
            await nexus.entregar(page, pdf_path, hooks)
        finally:
            with contextlib.suppress(Exception):
                await nexus.volver_a_lista(page)
    state.storage.add_entrega(tarea_id, str(pdf_path))
    state.storage.set_estado(tarea_id, "entregada")
    return {"entregada": True}
