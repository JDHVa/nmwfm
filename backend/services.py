import asyncio
import contextlib
from datetime import date, datetime
from pathlib import Path

from playwright.async_api import Page

from . import config
from .core import documents, images, nexus, selectors, siase
from .core.browser import BrowserManager
from .core.gemini import GeminiWeb, LLMProvider
from .core.prompt_builder import PromptData, build_prompt
from .core.storage import Credentials, Storage, now_iso
from .core.types import Hooks, Rubrica
from .jobs import JobContext, JobManager


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def limpiar_autoevaluaciones(storage: Storage) -> int:
    ids = [i for i, titulo in storage.listar_titulos_tareas() if nexus.es_autoevaluacion(titulo)]
    storage.borrar_tareas(ids)
    return len(ids)


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
        limpiar_autoevaluaciones(self.storage)

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


async def ensure_nexus(state: AppState, hooks: Hooks, headless: bool | None = None) -> Page:
    ctx = await state.browser.context(headless)
    page = state.nexus_page
    if page is not None and not page.is_closed() and "plataformanexus.uanl.mx" in page.url:
        return page
    cuenta, password = require_credentials(state)
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


async def guardar_snapshot(state: AppState, page: Page, nombre: str) -> None:
    state.paths.debug.mkdir(parents=True, exist_ok=True)
    base = state.paths.debug / f"{nombre}-{datetime.now():%Y%m%d-%H%M%S}"
    with contextlib.suppress(Exception):
        base.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
    with contextlib.suppress(Exception):
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)


def _resumen_error(exc: Exception) -> str:
    texto = str(exc).strip()
    return texto.splitlines()[0] if texto else type(exc).__name__


async def _sesion_caida(page: Page | None) -> bool:
    try:
        return (
            page is None
            or page.is_closed()
            or ("plataformanexus.uanl.mx" not in page.url or "Login" in page.url)
        )
    except Exception:
        return True


async def _abrir_pestana(state: AppState, hooks: Hooks, login_lock: asyncio.Lock) -> Page:
    ctx = await state.browser.context(True)
    page = await ctx.new_page()
    try:
        await page.goto(config.NEXUS_LISTA_URL, wait_until="domcontentloaded")
        await page.wait_for_selector(selectors.NX_CARD, timeout=20000)
        return page
    except Exception:
        with contextlib.suppress(Exception):
            await page.close()
    # Workaround: si la pestaña nueva no hereda la sesión, se entra por SIASE.
    async with login_lock:
        cuenta, password = require_credentials(state)
        return await siase.login(ctx, cuenta, password, hooks)


class SesionCaida(Exception):
    pass


async def _a_estructura(page: Page, indice: int) -> None:
    try:
        await nexus.volver_a_estructura(page)
    except Exception:
        await nexus.volver_a_lista(page)
        await nexus.abrir_materia(page, indice)
        await nexus.abrir_estructura(page)


async def _sync_materia(
    state: AppState,
    ctx: JobContext,
    page: Page,
    modo: str,
    reanudar: bool,
    i: int,
    n: int,
    materia,
    acum: dict,
) -> None:
    portada = await nexus.abrir_materia(page, i)
    state.storage.set_portada(materia.id, portada.profesor, portada.periodo)
    etapas = await nexus.abrir_estructura(page)
    antes = state.storage.ids_tareas(materia.id)
    state.storage.replace_estructura(materia.id, etapas)
    filas = state.storage.tareas_con_posicion(materia.id)
    if i not in acum["contadas"]:
        acum["contadas"].add(i)
        acum["tareas"] += len(filas)
        acum["nuevas"] += sum(1 for f in filas if f["id"] not in antes)
    leidas = acum["leidas"]
    pendientes = []
    for f in filas:
        if f["id"] in leidas:
            continue
        forzada = modo == "completo" and not reanudar
        if forzada or f["id"] not in antes or not f["tiene_detalle"]:
            pendientes.append(f)

    for j, fila in enumerate(pendientes):
        acum["fracciones"][i] = j / len(pendientes)
        await ctx.update(
            f"Materia {i + 1}/{n} · Tarea {j + 1}/{len(pendientes)}: {fila['titulo']}",
            0.08 + 0.9 * sum(acum["fracciones"].values()) / n,
        )
        try:
            detalle = await nexus.abrir_tarea(page, fila["etapa_idx"], fila["tarea_idx"])
        except Exception as exc:
            if await _sesion_caida(page):
                raise SesionCaida() from exc
            mensaje = f"{materia.nombre} · {fila['numero']}: {_resumen_error(exc)}"
            acum["errores"].append(mensaje)
            await ctx.log(f"Error en la tarea {mensaje}", "error")
        else:
            state.storage.set_detalle(fila["id"], detalle)
            leidas.add(fila["id"])
            acum["detalles_leidos"] += 1
        await _a_estructura(page, i)
    acum["fracciones"][i] = 1.0


async def run_sync(state: AppState, ctx: JobContext, modo: str = "auto") -> dict:
    hooks = ctx.hooks()
    reanudar = False
    if modo == "auto":
        hecha = state.storage.get_settings()["sync_inicial_hecha"]
        modo = "incremental" if hecha else "completo"
        reanudar = not hecha
    limpiar_autoevaluaciones(state.storage)
    acum: dict = {
        "tareas": 0,
        "detalles_leidos": 0,
        "nuevas": 0,
        "errores": [],
        "contadas": set(),
        "leidas": set(),
        "fracciones": {},
    }
    fallidas = 0
    async with state.browser.lock:
        await ctx.update("Iniciando sesión", 0.0)
        page = await ensure_nexus(state, hooks, headless=True)
        await ctx.update("Leyendo materias", 0.05)
        materias = await nexus.leer_materias(page)
        if not materias:
            await guardar_snapshot(state, page, "sync-sin-materias")
            raise ApiError(502, "sin_materias", "No se encontraron materias en NEXUS")
        for m in materias:
            state.storage.upsert_materia(m.id, m.nombre, m.orden)
        n = len(materias)
        semaforo = asyncio.Semaphore(config.SYNC_PESTANAS)
        login_lock = asyncio.Lock()

        async def trabajar(i: int, m) -> bool:
            async with semaforo:
                for intento in range(2):
                    tab = None
                    try:
                        tab = await _abrir_pestana(state, hooks, login_lock)
                        await _sync_materia(state, ctx, tab, modo, reanudar, i, n, m, acum)
                        return True
                    except Exception as exc:
                        caida = isinstance(exc, SesionCaida) or tab is None
                        if intento == 0 and caida:
                            await ctx.log(f"Sesión de NEXUS perdida en {m.nombre}; reintentando")
                            continue
                        acum["errores"].append(f"{m.nombre}: {_resumen_error(exc)}")
                        await ctx.log(f"Error en la materia {m.nombre}: {exc}", "error")
                        if tab is not None:
                            await guardar_snapshot(state, tab, f"sync-materia-{m.id}")
                        return False
                    finally:
                        if tab is not None:
                            with contextlib.suppress(Exception):
                                await tab.close()
                return False

        resultados = await asyncio.gather(*(trabajar(i, m) for i, m in enumerate(materias)))
        fallidas = resultados.count(False)
        if fallidas == n:
            raise ApiError(
                502, "sync_fallido", "No se pudo leer ninguna materia: " + acum["errores"][0]
            )
    valores: dict = {"ultima_sync": now_iso()}
    if modo == "completo":
        valores["sync_inicial_hecha"] = True
    state.storage.set_settings(valores)
    return {
        "materias": n - fallidas,
        "tareas": acum["tareas"],
        "detalles_leidos": acum["detalles_leidos"],
        "nuevas": acum["nuevas"],
        "errores": acum["errores"],
    }


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
        page = await ensure_nexus(state, Hooks(), headless=True)
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
