import asyncio
import contextlib
import random
from pathlib import Path

from playwright.async_api import BrowserContext, Locator, Page, Playwright, async_playwright

VIEWPORT = {"width": 1366, "height": 900}
RECURSOS_BLOQUEADOS = {"image", "font", "media"}
TIMEOUT_POR_DEFECTO_MS = 10_000
TIMEOUT_NAVEGACION_MS = 30_000


def bloquear_recurso(resource_type: str, page_url: str) -> bool:
    if resource_type not in RECURSOS_BLOQUEADOS:
        return False
    if not page_url or page_url.startswith("about:"):
        return False
    return "gemini.google.com" not in page_url


async def _filtrar_recursos(route) -> None:
    request = route.request
    try:
        url_pagina = request.frame.url
    except Exception:
        url_pagina = ""
    if bloquear_recurso(request.resource_type, url_pagina):
        await route.abort()
    else:
        await route.continue_()


async def pausa(minimo: float = 0.4, maximo: float = 1.4) -> None:
    await asyncio.sleep(random.uniform(minimo, maximo))


async def pausa_larga() -> None:
    await pausa(1.5, 3.5)


async def escribir_humano(
    page: Page, target: Locator, texto: str, *, delay_min: int = 18, delay_max: int = 55
) -> None:
    await target.click()
    await pausa(0.3, 0.8)
    lineas = texto.split("\n")
    for i, linea in enumerate(lineas):
        pos = 0
        while pos < len(linea):
            trozo = linea[pos : pos + random.randint(12, 45)]
            await target.press_sequentially(trozo, delay=random.randint(delay_min, delay_max))
            pos += len(trozo)
            if random.random() < 0.15:
                await pausa(0.2, 0.9)
        if i < len(lineas) - 1:
            await page.keyboard.press("Shift+Enter")
            await asyncio.sleep(random.uniform(0.05, 0.25))


async def clic_humano(target: Locator) -> None:
    await target.scroll_into_view_if_needed()
    await target.hover()
    await pausa(0.2, 0.7)
    await target.click()


class ElementoNoEncontrado(Exception):
    pass


def _url_de(locator: Locator) -> str:
    try:
        return locator.page.url
    except Exception:
        return "desconocida"


async def clic_robusto(locator: Locator, respaldo: Locator | None = None) -> None:
    objetivo = locator.first
    with contextlib.suppress(Exception):
        await objetivo.evaluate("e => e.scrollIntoView({block: 'center'})")
    try:
        await objetivo.click(timeout=5000)
    except Exception as exc:
        try:
            existe = await locator.count() > 0
        except Exception:
            existe = True
        if not existe:
            raise ElementoNoEncontrado(
                f"No se encontró {locator} en la página {_url_de(locator)}"
            ) from exc
        # Workaround: overlays/forms de SIASE y NEXUS interceptan el clic real.
        with contextlib.suppress(Exception):
            await objetivo.wait_for(state="visible", timeout=3000)
        await (respaldo if respaldo is not None else objetivo).dispatch_event("click")


async def _configurar_contexto(ctx: BrowserContext) -> None:
    ctx.set_default_timeout(TIMEOUT_POR_DEFECTO_MS)
    ctx.set_default_navigation_timeout(TIMEOUT_NAVEGACION_MS)
    await ctx.route("**/*", _filtrar_recursos)


class BrowserManager:
    def __init__(self, profile_dir: Path, dev: bool):
        self.profile_dir = profile_dir
        self.dev = dev
        self.lock = asyncio.Lock()
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None
        self._headless: bool | None = None

    @property
    def abierto(self) -> bool:
        return self._ctx is not None

    async def context(self, headless: bool | None = None) -> BrowserContext:
        objetivo = (not self.dev) if headless is None else headless
        if self._ctx is not None and self._headless != objetivo:
            await self._cerrar_contexto()
        if self._ctx is not None:
            return self._ctx
        if self._pw is None:
            self._pw = await async_playwright().start()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="chrome",
            headless=objetivo,
            viewport=VIEWPORT,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        await _configurar_contexto(ctx)
        self._ctx = ctx
        self._headless = objetivo
        ctx.on("close", lambda _: self._olvidar(ctx))
        return ctx

    def _olvidar(self, ctx: BrowserContext) -> None:
        if self._ctx is ctx:
            self._ctx = None

    async def _cerrar_contexto(self) -> None:
        ctx, self._ctx = self._ctx, None
        if ctx is not None:
            with contextlib.suppress(Exception):
                await ctx.close()

    async def nueva_pagina(self) -> Page:
        ctx = await self.context()
        return await ctx.new_page()

    async def close(self) -> None:
        await self._cerrar_contexto()
        if self._pw is not None:
            with contextlib.suppress(Exception):
                await self._pw.stop()
            self._pw = None
