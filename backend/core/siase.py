import asyncio
import contextlib
import re
import time

from playwright.async_api import BrowserContext, Frame, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .. import config
from . import selectors as S
from .browser import clic_robusto
from .htmlq import parse, select, text_of
from .types import Hooks


class SiaseError(Exception):
    pass


class CredencialesInvalidas(SiaseError):
    pass


class SiaseSinRespuesta(SiaseError):
    pass


async def _buscar_scope(page: Page, selector: str, timeout: float) -> Frame | None:
    encontrado = await _buscar_alguno(page, [selector], timeout)
    return encontrado[0] if encontrado else None


async def _buscar_alguno(
    page: Page, selectores: list[str], timeout: float
) -> tuple[Frame, str] | None:
    fin = time.monotonic() + timeout
    while True:
        for frame in page.frames:
            for selector in selectores:
                try:
                    if await frame.locator(selector).count():
                        return frame, selector
                except Exception:
                    continue
        if time.monotonic() >= fin:
            return None
        await asyncio.sleep(0.15)


async def _llenar_formulario(scope: Frame, cuenta: str, password: str) -> None:
    await scope.locator(S.SIASE_TIPO_SELECT).first.select_option(S.SIASE_TIPO_ALUMNO)
    await scope.locator(S.SIASE_CUENTA).first.fill(cuenta)
    await scope.locator(S.SIASE_PASSWORD).first.fill(password)
    await clic_robusto(scope.locator(S.SIASE_ENTRAR))


async def _mostrar_panel_nexus(scope: Frame) -> None:
    # Workaround: el hover real lo intercepta un form de SIASE; se ejecuta el mismo handler.
    try:
        await scope.evaluate(S.SIASE_MOSTRAR_NEXUS_JS)
    except Exception:
        await scope.locator(S.SIASE_NEXUS_LOGO).first.dispatch_event("mouseover")


async def _abrir_inicio(page: Page, cuenta: str, password: str, hooks: Hooks) -> Frame:
    await hooks.paso("Abriendo SIASE", 0.02)
    await page.goto(config.SIASE_URL, wait_until="domcontentloaded")

    logo_scope = None
    encontrado = await _buscar_alguno(page, [S.SIASE_NEXUS_LOGO, S.SIASE_CUENTA], 25)
    if encontrado is not None and encontrado[1] == S.SIASE_NEXUS_LOGO:
        logo_scope = encontrado[0]
    if logo_scope is None:
        if encontrado is None:
            raise SiaseError("No se encontro el formulario de acceso de SIASE.")
        scope = encontrado[0]
        await hooks.paso("Iniciando sesion en SIASE", 0.05)
        await _llenar_formulario(scope, cuenta, password)
        await page.wait_for_load_state("domcontentloaded")
        logo_scope = await _buscar_scope(page, S.SIASE_NEXUS_LOGO, 30)
        if logo_scope is None:
            await hooks.esperar_usuario(
                "SIASE no mostro el acceso a NEXUS (captcha o aviso). "
                "Resuelvelo en la ventana de Chrome y pulsa continuar."
            )
            logo_scope = await _buscar_scope(page, S.SIASE_NEXUS_LOGO, 30)
        if logo_scope is None:
            raise SiaseError("No se pudo llegar al acceso a NEXUS desde SIASE.")
    return logo_scope


async def login(
    ctx: BrowserContext, cuenta: str, password: str, hooks: Hooks | None = None
) -> Page:
    hooks = hooks or Hooks()
    page = await ctx.new_page()
    logo_scope = await _abrir_inicio(page, cuenta, password, hooks)

    await hooks.paso("Entrando a NEXUS", 0.1)
    await _mostrar_panel_nexus(logo_scope)
    link = logo_scope.locator(S.SIASE_NEXUS_LINK).first
    await link.wait_for(state="visible", timeout=15000)
    async with ctx.expect_page() as nueva:
        await clic_robusto(link)
    nexus = await nueva.value
    await nexus.wait_for_selector(S.NX_CARD, timeout=60000)
    with contextlib.suppress(Exception):
        await page.close()
    return nexus


async def _presente(page: Page, selector: str) -> bool:
    for frame in page.frames:
        try:
            if await frame.locator(selector).count():
                return True
        except Exception:
            continue
    return False


async def validar(
    ctx: BrowserContext, cuenta: str, password: str, hooks: Hooks | None = None, timeout: float = 12
) -> None:
    hooks = hooks or Hooks()
    page = await ctx.new_page()
    try:
        await hooks.paso("Abriendo SIASE", 0.1)
        try:
            await page.goto(config.SIASE_URL, wait_until="domcontentloaded", timeout=45000)
        except PlaywrightTimeoutError as exc:
            raise SiaseSinRespuesta("SIASE no responde") from exc

        encontrado = await _buscar_alguno(page, [S.SIASE_NEXUS_LOGO, S.SIASE_CUENTA], 25)
        if encontrado is None:
            raise SiaseSinRespuesta("SIASE no responde")
        if encontrado[1] == S.SIASE_NEXUS_LOGO:
            return
        scope = encontrado[0]
        await hooks.paso("Validando credenciales", 0.4)
        await _llenar_formulario(scope, cuenta, password)

        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            if await _presente(page, S.SIASE_NEXUS_LOGO):
                return
            if await _presente(page, S.SIASE_ERROR_LOGIN):
                raise CredencialesInvalidas("Cuenta o contraseña incorrecta")
            await asyncio.sleep(0.2)
        if await _presente(page, S.SIASE_CUENTA):
            raise CredencialesInvalidas("Cuenta o contraseña incorrecta")
        raise SiaseSinRespuesta("SIASE no responde")
    finally:
        with contextlib.suppress(Exception):
            await page.close()


def _numero(texto: str) -> float | None:
    limpio = texto.strip().replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def parse_evaluacion(markup: str) -> list[dict]:
    root = parse(markup)
    filas = select(root, S.SIASE_EVAL_FILAS)
    orden: list[str] = []
    for fila in filas:
        textos = [text_of(c) for c in fila.xpath("./td")]
        encontradas = [S.SIASE_EVAL_COLUMNAS[t] for t in textos if t in S.SIASE_EVAL_COLUMNAS]
        if len(encontradas) == len(S.SIASE_EVAL_COLUMNAS):
            orden = encontradas
            break
    if not orden:
        return []
    materias = []
    for fila in filas:
        celdas = [text_of(c) for c in fila.xpath("./td")]
        if len(celdas) != 3 + 2 * len(orden):
            continue
        coincide = re.match(r"^(\d+)\s+(.+)$", celdas[0])
        if coincide is None:
            continue
        notas = {}
        for i, clave in enumerate(orden):
            cal, pts = _numero(celdas[2 + 2 * i]), _numero(celdas[3 + 2 * i])
            notas[clave] = {"cal": cal, "pts": pts}
        materias.append(
            {
                "clave": coincide.group(1),
                "nombre": coincide.group(2).strip(),
                "grupo": celdas[1],
                "notas": notas,
                "total": _numero(celdas[-1]),
            }
        )
    return materias


async def _leer_tabla(page: Page, timeout: float) -> list[dict]:
    encontrado = await _buscar_alguno(page, [S.SIASE_EVAL_TABLA], timeout)
    if encontrado is None:
        raise SiaseError("SIASE no mostro la tabla de calificaciones.")
    return parse_evaluacion(await encontrado[0].content())


async def leer_calificaciones(
    ctx: BrowserContext, cuenta: str, password: str, hooks: Hooks | None = None
) -> list[dict]:
    hooks = hooks or Hooks()
    page = await ctx.new_page()
    try:
        inicio = await _abrir_inicio(page, cuenta, password, hooks)
        await hooks.paso("Abriendo la carrera", 0.25)
        await clic_robusto(inicio.locator(S.SIASE_CARRERA_LINK))
        menu = await _buscar_alguno(page, [S.SIASE_MENU_EVALUACION], 30)
        if menu is None:
            raise SiaseError("No se encontro la Consulta de Evaluacion en SIASE.")
        await hooks.paso("Consulta de Evaluacion", 0.45)
        await clic_robusto(menu[0].locator(S.SIASE_MENU_EVALUACION))
        formulario = await _buscar_scope(page, S.SIASE_PERIODO_SELECT, 30)
        if formulario is None:
            raise SiaseError("SIASE no mostro el selector de periodo.")
        periodos = await formulario.locator(S.SIASE_PERIODO_SELECT).first.evaluate(
            "el => [...el.options].map(o => o.value)"
        )
        validos = [p for p in periodos if p != S.SIASE_PERIODO_SIN_ELEGIR]
        if not validos:
            raise SiaseError("SIASE no tiene periodos con calificaciones.")
        if len(validos) > 1:
            await hooks.log("SIASE tiene varios periodos; se usa el primero.")
        await hooks.paso("Leyendo calificaciones", 0.65)
        await formulario.locator(S.SIASE_PERIODO_SELECT).first.select_option(validos[0])
        await clic_robusto(formulario.locator(S.SIASE_EVAL_ACEPTAR))
        return await _leer_tabla(page, 30)
    finally:
        with contextlib.suppress(Exception):
            await page.close()
