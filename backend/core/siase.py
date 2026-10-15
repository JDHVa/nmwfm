import asyncio
import contextlib
import time

from playwright.async_api import BrowserContext, Frame, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .. import config
from . import selectors as S
from .browser import clic_humano, pausa, pausa_larga
from .types import Hooks


class SiaseError(Exception):
    pass


class CredencialesInvalidas(SiaseError):
    pass


class SiaseSinRespuesta(SiaseError):
    pass


async def _buscar_scope(page: Page, selector: str, timeout: float) -> Frame | None:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        for frame in page.frames:
            try:
                if await frame.locator(selector).count():
                    return frame
            except Exception:
                continue
        await asyncio.sleep(0.5)
    return None


async def _ya_en_nexus_link(page: Page) -> Frame | None:
    return await _buscar_scope(page, S.SIASE_NEXUS_LOGO, 4)


async def _llenar_formulario(scope: Frame, cuenta: str, password: str) -> None:
    await scope.locator(S.SIASE_TIPO_SELECT).select_option(S.SIASE_TIPO_ALUMNO)
    await pausa()
    campo = scope.locator(S.SIASE_CUENTA)
    await campo.click()
    await campo.fill("")
    await campo.press_sequentially(cuenta, delay=70)
    await pausa()
    campo = scope.locator(S.SIASE_PASSWORD)
    await campo.click()
    await campo.fill("")
    await campo.press_sequentially(password, delay=70)
    await pausa()
    await clic_humano(scope.locator(S.SIASE_ENTRAR))


async def login(
    ctx: BrowserContext, cuenta: str, password: str, hooks: Hooks | None = None
) -> Page:
    hooks = hooks or Hooks()
    page = await ctx.new_page()
    await hooks.paso("Abriendo SIASE", 0.02)
    await page.goto(config.SIASE_URL, wait_until="domcontentloaded")

    logo_scope = await _ya_en_nexus_link(page)
    if logo_scope is None:
        scope = await _buscar_scope(page, S.SIASE_CUENTA, 25)
        if scope is None:
            raise SiaseError("No se encontro el formulario de acceso de SIASE.")
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
    await pausa()
    await logo_scope.locator(S.SIASE_NEXUS_LOGO).first.hover()
    await pausa_larga()
    link = logo_scope.locator(S.SIASE_NEXUS_LINK)
    await link.wait_for(state="visible", timeout=15000)
    async with ctx.expect_page() as nueva:
        await link.click()
    nexus = await nueva.value
    await nexus.wait_for_selector(S.NX_CARD, timeout=60000)
    await pausa()
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
    ctx: BrowserContext, cuenta: str, password: str, hooks: Hooks | None = None, timeout: float = 30
) -> None:
    hooks = hooks or Hooks()
    page = await ctx.new_page()
    try:
        await hooks.paso("Abriendo SIASE", 0.1)
        try:
            await page.goto(config.SIASE_URL, wait_until="domcontentloaded", timeout=45000)
        except PlaywrightTimeoutError as exc:
            raise SiaseSinRespuesta("SIASE no responde") from exc

        if await _buscar_scope(page, S.SIASE_NEXUS_LOGO, 4) is not None:
            return
        scope = await _buscar_scope(page, S.SIASE_CUENTA, 25)
        if scope is None:
            raise SiaseSinRespuesta("SIASE no responde")
        await hooks.paso("Validando credenciales", 0.4)
        await _llenar_formulario(scope, cuenta, password)

        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            if await _presente(page, S.SIASE_NEXUS_LOGO):
                return
            if await _presente(page, S.SIASE_ERROR_LOGIN):
                raise CredencialesInvalidas("Cuenta o contraseña incorrecta")
            await asyncio.sleep(0.5)
        if await _presente(page, S.SIASE_CUENTA):
            raise CredencialesInvalidas("Cuenta o contraseña incorrecta")
        raise SiaseSinRespuesta("SIASE no responde")
    finally:
        with contextlib.suppress(Exception):
            await page.close()
