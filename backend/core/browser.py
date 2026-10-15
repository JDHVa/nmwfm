import asyncio
import contextlib
import random
from pathlib import Path

from playwright.async_api import BrowserContext, Locator, Page, Playwright, async_playwright


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


class BrowserManager:
    def __init__(self, profile_dir: Path, dev: bool):
        self.profile_dir = profile_dir
        self.dev = dev
        self.lock = asyncio.Lock()
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None

    @property
    def abierto(self) -> bool:
        return self._ctx is not None

    async def context(self) -> BrowserContext:
        if self._ctx is not None:
            return self._ctx
        if self._pw is None:
            self._pw = await async_playwright().start()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            channel="chrome",
            headless=not self.dev,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._ctx.on("close", lambda _: setattr(self, "_ctx", None))
        return self._ctx

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
