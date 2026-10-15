import asyncio
import contextlib
import time

from playwright.async_api import BrowserContext, Frame, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .. import config
from . import selectors as S
from .browser import clic_robusto
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


async def login(
    ctx: BrowserContext, cuenta: str, password: str, hooks: Hooks | None = None
) -> Page:
    hooks = hooks or Hooks()
    page = await ctx.new_page()
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

    await hooks.paso("Entrando a NEXUS", 0.1)
    await _mostrar_panel_nexus(logo_scope)
    link = logo_scope.locator(S.SIASE_NEXUS_LINK).first
    await link.wait_for(state="visible", timeout=15000)
    async with ctx.expect_page() as nueva:
        await clic_robusto(link)
    nexus = await nueva.value
    await nexus.wait_for_selector(S.NX_CARD, timeout=60000)
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
