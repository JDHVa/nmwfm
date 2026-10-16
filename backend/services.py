import asyncio
import contextlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from playwright.async_api import Page

from . import config
from .core import documents, images, metricas, modelos, nexus, ocr, selectors, siase
from .core.apicatalog import Catalogo
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
        self.sesion_muerta_registrada = False
        self._detector: images.DetectorModelo | None = None
        self.catalogo = Catalogo(self.paths.debug / "api" if dev else None)
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
            "modelo_recorte_disponible": modelos.modelo_disponible(self.paths.models),
        }

    def detector_recorte(self) -> images.DetectorModelo | None:
        if self.storage.get_settings()["recorte_modelo"] != "auto":
            return None
        ruta = modelos.ruta_modelo(self.paths.models)
        if not ruta.is_file():
            return None
        if self._detector is None or self._detector.ruta != ruta:
            self._detector = images.DetectorModelo(ruta)
        return None if self._detector.fallo else self._detector

    def insumo_public(self, row: dict) -> dict:
        out: dict = {
            "id": row["id"],
            "tipo": row["tipo"],
            "orden": row["orden"],
            "rotacion": row["rotacion"],
            "usar_recorte": bool(row["usar_recorte"]),
        }
        if row["tipo"] == "imagen":
            out["ocr_texto"] = row.get("ocr_texto")
            out["ocr_editado"] = bool(row.get("ocr_editado"))
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
            "avisos": json.loads(row.get("avisos") or "[]"),
            "portada": json.loads(row["portada"]) if row.get("portada") else None,
            "id": row.get("hist_id") if "hist_id" in row else row.get("id"),
        }

    def tarea_detalle_public(self, tarea: dict, detalle: dict | None) -> dict:
        base = detalle or {
            "actividades": "",
            "contenido": "",
            "criterios_desempeno": "",
            "rubrica": None,
        }
        return {
            **con_vencida(tarea),
            **base,
            "indicaciones": self.storage.get_indicaciones(tarea["id"]),
        }

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


async def _cerrar_nexus_previos(ctx) -> None:
    for pagina in list(getattr(ctx, "pages", [])):
        with contextlib.suppress(Exception):
            if "plataformanexus.uanl.mx" in pagina.url:
                await pagina.close()


async def ensure_nexus(state: AppState, hooks: Hooks, headless: bool | None = None) -> Page:
    ctx = await state.browser.context(headless)
    page = state.nexus_page
    if page is not None and not await _sesion_caida(page):
        return page
    # NEXUS solo admite una instancia abierta: la pestaña vieja se cierra antes de abrir otra.
    await _cerrar_nexus_previos(ctx)
    state.nexus_page = None
    cuenta, password = require_credentials(state)
    state.nexus_page = await siase.login(ctx, cuenta, password, hooks)
    state.sesion_muerta_registrada = False
    state.catalogo.adjuntar(state.nexus_page)
    return state.nexus_page


async def _con_nexus(state: AppState, hooks: Hooks, headless: bool | None, fn):
    page = await ensure_nexus(state, hooks, headless=headless)
    try:
        return await fn(page)
    except Exception:
        actual = state.nexus_page or page
        if not await _sesion_caida(actual):
            raise
        await _avisar_sesion_muerta(state, hooks, actual)
        state.nexus_page = None
        return await fn(await ensure_nexus(state, hooks, headless=headless))


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
    base = state.paths.debug / f"{nombre.replace('.', '_')}-{datetime.now():%Y%m%d-%H%M%S}"
    with contextlib.suppress(Exception):
        base.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
    with contextlib.suppress(Exception):
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)


def _resumen_error(exc: Exception) -> str:
    texto = str(exc).strip()
    return texto.splitlines()[0] if texto else type(exc).__name__


async def _sesion_caida(page: Page | None) -> bool:
    try:
        if page is None or page.is_closed():
            return True
        if "plataformanexus.uanl.mx" not in page.url or "Login" in page.url:
            return True
    except Exception:
        return True
    with contextlib.suppress(Exception):
        return await page.locator(selectors.NX_SESION_CERRADA).count() > 0
    return False


async def _avisar_sesion_muerta(state: AppState, hooks: Hooks, page: Page | None) -> None:
    if page is not None and not state.sesion_muerta_registrada:
        state.sesion_muerta_registrada = True
        await guardar_snapshot(state, page, "sesion-nexus-muerta")
    await hooks.log("NEXUS cerró la sesión (¿está abierto en otra ventana?)", "error")


class SesionCaida(Exception):
    pass


async def _a_estructura(page: Page, indice: int, nombre: str) -> None:
    with contextlib.suppress(Exception):
        if await page.locator(selectors.NX_PANEL_ITEM_LINK).count() > 0:
            return
    try:
        await nexus.volver_a_estructura(page)
    except Exception:
        await nexus.volver_a_lista(page)
        await nexus.abrir_materia(page, indice, nombre)
        await nexus.abrir_estructura(page)


async def _abrir_materia_y_estructura(
    state: AppState, page: Page, i: int, materia, acum: dict
) -> tuple[list[dict], set[str]]:
    portada = await nexus.abrir_materia(page, i, materia.nombre)
    state.storage.set_portada(materia.id, portada.profesor, portada.periodo)
    etapas = await nexus.abrir_estructura(page)
    antes = state.storage.ids_tareas(materia.id)
    titulos_antes = state.storage.titulos_tareas(materia.id)
    state.storage.replace_estructura(materia.id, etapas)
    filas = state.storage.tareas_con_posicion(materia.id)
    if acum.get("novedades"):
        _novedades_estructura(state, filas, antes, titulos_antes)
    if i not in acum["contadas"]:
        acum["contadas"].add(i)
        acum["tareas"] += len(filas)
        acum["nuevas"] += sum(1 for f in filas if f["id"] not in antes)
    return filas, antes


def _novedades_estructura(state: AppState, filas: list[dict], antes: set, titulos: dict) -> None:
    for fila in filas:
        if fila["id"] not in antes:
            state.storage.add_novedad(fila["id"], "nueva", f"Tarea nueva: {fila['titulo']}")
        elif titulos.get(fila["id"]) not in (None, fila["titulo"]):
            state.storage.add_novedad(
                fila["id"], "modificada", f"Título: {titulos[fila['id']]} → {fila['titulo']}"
            )


CAMPOS_DETALLE = (
    ("actividades", "Actividades actualizadas"),
    ("contenido", "Contenido actualizado"),
    ("criterios_desempeno", "Criterios de desempeño actualizados"),
)


def cambios_detalle(previo: dict | None, tarea_previa: dict, nuevo, tarea_nueva: dict) -> list[str]:
    if previo is None:
        return []
    cambios = []
    for campo, nombre in (("desde", "Fecha de inicio"), ("hasta", "Fecha de entrega")):
        if tarea_previa.get(campo) != tarea_nueva.get(campo):
            cambios.append(f"{nombre}: {tarea_previa.get(campo)} → {tarea_nueva.get(campo)}")
    if tarea_previa.get("puntos") != tarea_nueva.get("puntos"):
        cambios.append(f"Puntos: {tarea_previa.get('puntos')} → {tarea_nueva.get('puntos')}")
    for campo, nombre in CAMPOS_DETALLE:
        if (previo.get(campo) or "") != (getattr(nuevo, campo, "") or ""):
            cambios.append(nombre)
    rubrica_nueva = nuevo.rubrica.to_dict() if nuevo.rubrica else None
    if previo.get("rubrica") != rubrica_nueva:
        cambios.append("Rúbrica actualizada")
    return cambios


def _guardar_detalle_con_novedades(state: AppState, tarea_id: str, detalle, acum: dict) -> None:
    previo = state.storage.get_detalle(tarea_id) if acum.get("novedades") else None
    tarea_previa = state.storage.get_tarea(tarea_id)
    state.storage.set_detalle(tarea_id, detalle)
    if previo is not None:
        cambios = cambios_detalle(previo, tarea_previa, detalle, state.storage.get_tarea(tarea_id))
        if cambios:
            state.storage.add_novedad(tarea_id, "modificada", "; ".join(cambios))


def _registrar_entregas(state: AppState, tarea_id: str, entregas, acum: dict) -> None:
    if entregas is None:
        return
    if entregas:
        state.storage.marcar_entregada(tarea_id, nexus.ultima_entrega(entregas))
        acum["entregadas"] += 1
    else:
        state.storage.desmarcar_entregada(tarea_id)
        acum["pendientes"] += 1


def _sin_examenes(filas: list[dict]) -> list[dict]:
    return [f for f in filas if f["tipo"] != "examen"]


async def _recorrer_tareas(
    state: AppState,
    ctx: JobContext,
    page: Page,
    i: int,
    n: int,
    materia,
    pendientes: list[dict],
    acum: dict,
    leer,
) -> None:
    for j, fila in enumerate(pendientes):
        acum["fracciones"][i] = j / len(pendientes)
        await ctx.update(
            f"Materia {i + 1}/{n} · Tarea {j + 1}/{len(pendientes)}: {fila['titulo']}",
            0.08 + 0.9 * sum(acum["fracciones"].values()) / n,
        )
        try:
            async with metricas.medir("tarea"):
                await leer(page, fila)
        except Exception as exc:
            if await _sesion_caida(page):
                raise SesionCaida() from exc
            if fila["tipo"] == "pia":
                await ctx.log(f"PIA pendiente de soporte: {fila['titulo']}")
            else:
                mensaje = f"{materia.nombre} · {fila['numero']}: {_resumen_error(exc)}"
                acum["errores"].append(mensaje)
                await ctx.log(f"Error en la tarea {mensaje}", "error")
            await guardar_snapshot(state, page, f"sync-tarea-{materia.id}-{fila['numero']}")
        await _a_estructura(page, i, materia.nombre)
    acum["fracciones"][i] = 1.0


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
    filas, antes = await _abrir_materia_y_estructura(state, page, i, materia, acum)
    leidas = acum["leidas"]
    forzada = modo == "completo" and not reanudar
    filas = _sin_examenes(filas)
    pendientes = [
        f
        for f in filas
        if f["id"] not in leidas
        and f["estado"] != "entregada"
        and (forzada or f["id"] not in antes or not f["tiene_detalle"])
    ]

    async def leer(pagina: Page, fila: dict) -> None:
        detalle = await nexus.abrir_tarea(
            pagina,
            fila["etapa_idx"],
            fila["tarea_idx"],
            fila["numero"],
            entregas=modo == "completo",
            pia=fila["tipo"] == "pia",
        )
        _guardar_detalle_con_novedades(state, fila["id"], detalle, acum)
        leidas.add(fila["id"])
        acum["detalles_leidos"] += 1
        _registrar_entregas(state, fila["id"], detalle.entregas, acum)

    await _recorrer_tareas(state, ctx, page, i, n, materia, pendientes, acum, leer)
    if modo == "completo":
        await _leer_calificaciones(state, ctx, page, materia)
    await nexus.volver_a_lista(page)


async def _leer_calificaciones(state: AppState, ctx: JobContext, page: Page, materia) -> None:
    try:
        async with metricas.medir("calificaciones"):
            html = await nexus.abrir_calificaciones(page)
        datos = nexus.parse_calificaciones(html)
        if datos is None:
            await ctx.log(f"Calificaciones de {materia.nombre}: formato no reconocido", "error")
            await guardar_snapshot(state, page, f"calificaciones-{materia.id}")
        else:
            state.storage.set_calificaciones(materia.id, datos)
    except Exception as exc:
        if await _sesion_caida(page):
            raise SesionCaida() from exc
        await ctx.log(f"Calificaciones de {materia.nombre}: {_resumen_error(exc)}", "error")


async def _revisar_materia(
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
    filas, _ = await _abrir_materia_y_estructura(state, page, i, materia, acum)
    filas = _sin_examenes(filas)
    pendientes = [f for f in filas if f["estado"] != "entregada"]

    async def leer(pagina: Page, fila: dict) -> None:
        detalle = await nexus.abrir_tarea(
            pagina,
            fila["etapa_idx"],
            fila["tarea_idx"],
            fila["numero"],
            solo_entregas=True,
            pia=fila["tipo"] == "pia",
        )
        if detalle.entregas is not None:
            acum["revisadas"] += 1
        _registrar_entregas(state, fila["id"], detalle.entregas, acum)

    await _recorrer_tareas(state, ctx, page, i, n, materia, pendientes, acum, leer)
    await nexus.volver_a_lista(page)


async def _en_lista(page: Page) -> None:
    if not await page.locator(selectors.NX_CARD).count():
        await nexus.volver_a_lista(page)


async def _secuencial(state: AppState, ctx: JobContext, procesar, modo, reanudar, acum):
    medidor = metricas.Metricas()
    token = metricas.actual.set(medidor)
    try:
        n, fallidas = await _recorrer_materias(state, ctx, procesar, modo, reanudar, acum)
    finally:
        metricas.actual.reset(token)
        await ctx.log(medidor.texto())
        state.catalogo.guardar()
    acum["tiempos"] = medidor.resumen()
    return n, fallidas


async def _recorrer_materias(state: AppState, ctx: JobContext, procesar, modo, reanudar, acum):
    hooks = ctx.hooks()
    await ctx.update("Iniciando sesión", 0.0)
    async with metricas.medir("login"):
        page = await ensure_nexus(state, hooks, headless=True)
    await ctx.update("Leyendo materias", 0.05)
    try:
        await _en_lista(page)
        materias = await nexus.leer_materias(page)
    except Exception:
        if not await _sesion_caida(state.nexus_page or page):
            raise
        await _avisar_sesion_muerta(state, hooks, state.nexus_page or page)
        state.nexus_page = None
        page = await ensure_nexus(state, hooks, headless=True)
        materias = await nexus.leer_materias(page)
    if not materias:
        await guardar_snapshot(state, page, "sync-sin-materias")
        raise ApiError(502, "sin_materias", "No se encontraron materias en NEXUS")
    for m in materias:
        state.storage.upsert_materia(m.id, m.nombre, m.orden)
    n = len(materias)
    fallidas = 0
    for i, m in enumerate(materias):
        for intento in range(2):
            try:
                async with metricas.medir("materia"):
                    await procesar(state, ctx, page, modo, reanudar, i, n, m, acum)
                break
            except Exception as exc:
                page = state.nexus_page or page
                causa: Exception = exc
                if intento == 0 and (isinstance(exc, SesionCaida) or await _sesion_caida(page)):
                    await _avisar_sesion_muerta(state, hooks, page)
                    try:
                        state.nexus_page = None
                        page = await ensure_nexus(state, hooks, headless=True)
                        continue
                    except Exception as exc2:
                        causa = exc2
                fallidas += 1
                acum["errores"].append(f"{m.nombre}: {_resumen_error(causa)}")
                await ctx.log(f"Error en la materia {m.nombre}: {causa}", "error")
                await guardar_snapshot(state, page, f"sync-materia-{m.id}")
                with contextlib.suppress(Exception):
                    await nexus.volver_a_lista(page)
                break
    if fallidas == n:
        raise ApiError(
            502, "sync_fallido", "No se pudo leer ninguna materia: " + acum["errores"][0]
        )
    return n, fallidas


def _acumulador() -> dict:
    return {
        "tareas": 0,
        "detalles_leidos": 0,
        "nuevas": 0,
        "errores": [],
        "contadas": set(),
        "leidas": set(),
        "fracciones": {},
        "revisadas": 0,
        "entregadas": 0,
        "pendientes": 0,
        "tiempos": {},
    }


async def run_sync(state: AppState, ctx: JobContext, modo: str = "auto") -> dict:
    reanudar = False
    hecha = state.storage.get_settings()["sync_inicial_hecha"]
    if modo == "auto":
        modo = "incremental" if hecha else "completo"
        reanudar = not hecha
    limpiar_autoevaluaciones(state.storage)
    acum = _acumulador()
    acum["novedades"] = hecha
    async with state.browser.lock:
        n, fallidas = await _secuencial(state, ctx, _sync_materia, modo, reanudar, acum)
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
        "tiempos": acum["tiempos"],
    }


async def run_revisar_entregas(state: AppState, ctx: JobContext) -> dict:
    limpiar_autoevaluaciones(state.storage)
    acum = _acumulador()
    async with state.browser.lock:
        await _secuencial(state, ctx, _revisar_materia, "revisar", False, acum)
    return {
        "revisadas": acum["revisadas"],
        "entregadas": acum["entregadas"],
        "pendientes": acum["pendientes"],
        "errores": acum["errores"],
    }


def ahora_monterrey() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/Monterrey")).replace(tzinfo=None)
    except ZoneInfoNotFoundError:
        return datetime.now(timezone(timedelta(hours=-6))).replace(tzinfo=None)


def con_vencida(tarea: dict, ahora: datetime | None = None) -> dict:
    ahora = ahora or ahora_monterrey()
    vencida = False
    if tarea.get("estado") != "entregada" and tarea.get("hasta"):
        with contextlib.suppress(ValueError):
            vencida = datetime.fromisoformat(tarea["hasta"]) < ahora
    return {**tarea, "vencida": vencida}


def tareas_proximas(state: AppState, ahora: datetime | None = None) -> list[dict]:
    ahora = ahora or ahora_monterrey()
    tareas = [con_vencida(t, ahora) for t in state.storage.tareas_no_entregadas()]
    tareas.sort(key=lambda t: (t["vencida"], t["hasta"] is None, t["hasta"] or ""))
    return tareas


def tareas_alertas(state: AppState, ahora: datetime | None = None) -> list[dict]:
    ahora = ahora or ahora_monterrey()
    alertas = []
    for tarea in state.storage.tareas_no_entregadas():
        if not tarea.get("hasta"):
            continue
        with contextlib.suppress(ValueError):
            limite = datetime.fromisoformat(tarea["hasta"])
            dias = (limite.date() - ahora.date()).days
            if limite >= ahora and dias in (0, 1):
                alertas.append({**con_vencida(tarea, ahora), "dias": dias})
    alertas.sort(key=lambda t: t["hasta"])
    return alertas


def tarea_materia_nombre(state: AppState, tarea: dict) -> str | None:
    materia = state.storage.get_materia(tarea["materia_id"])
    return materia["nombre"] if materia else None


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
    await nexus.abrir_materia(page, indice, tarea_materia_nombre(state, tarea))
    await nexus.abrir_estructura(page)
    return await nexus.abrir_tarea(
        page, etapa_idx, tarea_idx, tarea["numero"], pia=tarea["tipo"] == "pia"
    )


async def traer_detalle(state: AppState, tarea_id: str) -> dict:
    if state.storage.tarea_posicion(tarea_id) is None:
        raise ApiError(404, "tarea_no_encontrada", "La tarea no existe.")

    async def leer(page: Page):
        detalle = await _abrir_tarea_nexus(state, page, tarea_id)
        state.storage.set_detalle(tarea_id, detalle)
        await nexus.volver_a_lista(page)

    async with state.browser.lock:
        await _con_nexus(state, Hooks(), True, leer)
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


def _ocr_pendiente(state: AppState, tarea_id: str) -> list[str]:
    textos = []
    for fila in state.storage.list_insumos(tarea_id):
        if fila["tipo"] != "imagen" or not fila["recortada_path"]:
            continue
        texto = fila.get("ocr_texto")
        if texto is None:
            if not ocr.disponible():
                continue
            origen = fila["recortada_path"] if fila["usar_recorte"] else fila["original_path"]
            try:
                texto = ocr.extraer_texto(Path(origen), fila["rotacion"])
            except Exception:
                continue
            state.storage.set_ocr(fila["id"], texto)
        if texto.strip():
            textos.append(texto.strip())
    return textos


async def _texto_ocr(state: AppState, ctx: JobContext, tarea_id: str) -> str:
    imagenes = [f for f in state.storage.list_insumos(tarea_id) if f["tipo"] == "imagen"]
    if not imagenes:
        return ""
    sin_texto = any(f.get("ocr_texto") is None for f in imagenes)
    if sin_texto and not ocr.disponible():
        await ctx.log("OCR local no disponible: instala rapidocr-onnxruntime")
    elif sin_texto:
        await ctx.update("Leyendo el texto de las imágenes", 0.35)
    return "\n\n".join(await asyncio.to_thread(_ocr_pendiente, state, tarea_id))


def _generacion_dir(state: AppState, tarea_id: str) -> Path:
    return state.paths.generaciones / tarea_id


async def run_generar(
    state: AppState,
    ctx: JobContext,
    tarea_id: str,
    instrucciones_extra: str | None,
    portada: dict | None = None,
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

    texto_ocr = await _texto_ocr(state, ctx, tarea_id)
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
            texto_ocr=texto_ocr,
            indicaciones=state.storage.get_indicaciones(tarea_id),
        )
    )
    await ctx.update("generando", 0.45)
    async with state.browser.lock:
        markdown = await state.gemini.generar(prompt, pdf_insumos, ctx.hooks())

    await ctx.update("Creando el documento Word", 0.88)
    gen = await asyncio.to_thread(
        _construir_documentos, state, tarea, materia, settings, markdown, _portada_limpia(portada)
    )
    state.storage.set_estado(tarea_id, "generada")
    resultado = state.generacion_public(gen)
    if settings["entregar_sin_revisar"]:
        await ctx.update("entregando", 0.95)
        await run_entregar(state, ctx, tarea_id)
        resultado["entregada"] = True
    return resultado


def _portada_limpia(portada: dict | None) -> dict | None:
    limpia = {k: v.strip() for k, v in (portada or {}).items() if isinstance(v, str) and v.strip()}
    return {k: v for k, v in limpia.items() if k in ("profesor", "titulo")} or None


def _construir_documentos(
    state: AppState,
    tarea: dict,
    materia: dict,
    settings: dict,
    markdown: str,
    portada: dict | None = None,
) -> dict:
    portada = portada or {}
    out_dir = _generacion_dir(state, tarea["id"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
    mapping = documents.marcadores(
        settings["nombre"],
        settings["matricula"],
        portada.get("profesor") or materia["profesor"],
        date.today(),
    )
    avisos: list[str] = []
    docx_path = documents.build_final_docx(
        config.PORTADA_TEMPLATE,
        markdown,
        out_dir / "tarea.docx",
        mapping,
        out_dir / "tmp",
        avisos,
        portada.get("titulo") or f"{materia['nombre']} - {tarea['titulo']}",
    )
    pdf_path = documents.export_pdf(docx_path, out_dir / "tarea.pdf")
    return state.storage.set_generacion(
        tarea["id"], markdown, str(docx_path), str(pdf_path), avisos, portada=portada or None
    )


def listar_generaciones(state: AppState, tarea_id: str) -> list[dict]:
    return [
        {**state.generacion_public({**fila, "hist_id": fila["id"]}), "actual": fila["actual"]}
        for fila in state.storage.listar_generaciones(tarea_id)
    ]


def restaurar_generacion(state: AppState, hist_id: int) -> dict:
    fila = state.storage.restaurar_generacion(hist_id)
    if fila is None:
        raise ApiError(404, "generacion_no_encontrada", "La generación no existe.")
    return state.generacion_public(fila)


def _portada_preview(state: AppState, tarea: dict, portada: dict | None = None) -> Path:
    portada = portada or {}
    materia = state.storage.get_materia(tarea["materia_id"])
    settings = state.storage.get_settings()
    mapping = documents.marcadores(
        settings["nombre"] or "NOMBRE DEL ALUMNO",
        settings["matricula"] or "MATRÍCULA",
        portada.get("profesor") or (materia or {}).get("profesor") or "PROFESOR",
        date.today(),
    )
    carpeta = _generacion_dir(state, tarea["id"]) / "preview"
    docx_path = documents.fill_cover(config.PORTADA_TEMPLATE, carpeta / "portada.docx", mapping)
    return documents.export_pdf(docx_path, carpeta / "portada.pdf")


async def portada_preview(state: AppState, tarea_id: str, portada: dict | None = None) -> dict:
    tarea = state.storage.get_tarea(tarea_id)
    try:
        pdf = await asyncio.to_thread(_portada_preview, state, tarea, _portada_limpia(portada))
    except Exception as exc:
        raise ApiError(502, "sin_word", f"No se pudo generar la vista previa: {exc}") from exc
    return {"pdf_url": state.file_url(pdf)}


async def reconstruir_pdf(state: AppState, tarea_id: str) -> dict:
    gen = state.storage.get_generacion(tarea_id)
    if gen is None:
        raise ApiError(404, "sin_generacion", "Esta tarea todavía no tiene documento generado.")
    docx_path = Path(gen["docx_path"])
    pdf_path = await asyncio.to_thread(documents.export_pdf, docx_path, Path(gen["pdf_path"]))
    return state.generacion_public(
        state.storage.set_generacion(
            tarea_id,
            gen["markdown"],
            str(docx_path),
            str(pdf_path),
            json.loads(gen.get("avisos") or "[]"),
            historial=False,
        )
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

    async def subir(page: Page):
        await _abrir_tarea_nexus(state, page, tarea_id)
        try:
            await nexus.entregar(page, pdf_path, hooks)
        finally:
            with contextlib.suppress(Exception):
                await nexus.volver_a_lista(page)

    async with state.browser.lock:
        await _con_nexus(state, hooks, True, subir)
    state.storage.add_entrega(tarea_id, str(pdf_path))
    state.storage.marcar_entregada(tarea_id, now_iso())
    return {"entregada": True}
