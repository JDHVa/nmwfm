import asyncio
import contextlib
import time
from pathlib import Path
from typing import Protocol

from playwright.async_api import Page

from .. import config
from . import selectors as S
from .browser import BrowserManager, escribir_humano, pausa
from .types import Hooks


class GeminiError(Exception):
    pass


class LLMProvider(Protocol):
    async def sesion_activa(self) -> bool: ...

    async def iniciar_sesion(self, hooks: Hooks) -> None: ...

    async def generar(self, prompt: str, pdf_path: Path | None, hooks: Hooks) -> str: ...


class GeminiWeb:
    def __init__(self, browser: BrowserManager):
        self.browser = browser

    async def _abrir(self) -> Page:
        ctx = await self.browser.context()
        with contextlib.suppress(Exception):
            await ctx.grant_permissions(
                ["clipboard-read", "clipboard-write"], origin="https://gemini.google.com"
            )
        page = await ctx.new_page()
        await page.goto(config.GEMINI_URL, wait_until="domcontentloaded")
        return page

    async def _hay_sesion(self, page: Page) -> bool:
        if "accounts.google.com" in page.url:
            return False
        try:
            await page.wait_for_selector(S.GM_EDITOR, timeout=15000)
        except Exception:
            return False
        if await page.locator(S.GM_SIGN_IN_LINK).count():
            return False
        return await page.locator(S.GM_SIGNED_IN_MARKER).count() > 0

    async def _bloqueado(self, page: Page) -> bool:
        for marker in S.GM_BLOCK_MARKERS:
            with contextlib.suppress(Exception):
                if await page.locator(marker).first.is_visible():
                    return True
        return False

    async def sesion_activa(self) -> bool:
        page = await self._abrir()
        try:
            return await self._hay_sesion(page)
        finally:
            await page.close()

    async def iniciar_sesion(
        self, hooks: Hooks, timeout: float = config.USER_WAIT_TIMEOUT_S
    ) -> None:
        page = await self._abrir()
        await hooks.paso("Abriendo Gemini", 0.1)
        if await self._hay_sesion(page):
            await page.close()
            return
        await hooks.marcar_espera(
            "Inicia sesion en Gemini en la ventana de Chrome; se detecta solo al terminar."
        )
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            await asyncio.sleep(3)
            if page.is_closed():
                raise GeminiError("Se cerro la ventana de Gemini antes de iniciar sesion.")
            if "accounts.google.com" not in page.url and await self._hay_sesion(page):
                await hooks.paso("Sesion de Gemini detectada", 1.0)
                await page.close()
                return
        raise GeminiError("Tiempo agotado esperando el inicio de sesion en Gemini.")

    async def generar(self, prompt: str, pdf_path: Path | None, hooks: Hooks) -> str:
        page = await self._abrir()
        try:
            await self._asegurar_sesion(page, hooks)
            if pdf_path is not None:
                await hooks.paso("Adjuntando PDF en Gemini", 0.55)
                await self._adjuntar(page, pdf_path)
            await hooks.paso("Escribiendo el prompt", 0.6)
            await self._escribir_y_enviar(page, prompt)
            await hooks.paso("Esperando la respuesta de Gemini", 0.7)
            await self._esperar_respuesta(page, hooks)
            await hooks.paso("Leyendo la respuesta", 0.85)
            return await self._leer_markdown(page)
        finally:
            with contextlib.suppress(Exception):
                await page.close()

    async def _asegurar_sesion(self, page: Page, hooks: Hooks) -> None:
        for _ in range(2):
            if await self._hay_sesion(page):
                return
            await hooks.esperar_usuario(
                "Gemini no tiene sesion iniciada. Inicia sesion en la ventana de Chrome "
                "y pulsa continuar."
            )
            await page.goto(config.GEMINI_URL, wait_until="domcontentloaded")
            raise GeminiError("No se pudo detectar la sesion de Gemini.")

    async def _adjuntar(self, page: Page, pdf_path: Path) -> None:
        inputs = page.locator(S.GM_FILE_INPUT)
        if await inputs.count():
            await inputs.first.set_input_files(str(pdf_path))
        else:
            await page.locator(S.GM_UPLOAD_MENU_BUTTON).first.click()
            async with page.expect_file_chooser() as chooser:
                await page.locator(S.GM_UPLOAD_MENU_ITEM).first.click()
            await (await chooser.value).set_files(str(pdf_path))
        await page.wait_for_selector(S.GM_ATTACHMENT_CHIP, timeout=60000)

    async def _pegar_prompt(self, page: Page, editor, prompt: str) -> None:
        await editor.click()
        with contextlib.suppress(Exception):
            await editor.fill(prompt)
            if (await editor.inner_text()).strip():
                return
        with contextlib.suppress(Exception):
            await page.evaluate("t => navigator.clipboard.writeText(t)", prompt)
            await page.keyboard.press("Control+V")
            if (await editor.inner_text()).strip():
                return
        await escribir_humano(page, editor, prompt)

    async def _escribir_y_enviar(self, page: Page, prompt: str) -> None:
        editor = page.locator(S.GM_EDITOR).first
        await pausa(0.5, 1.5)
        await self._pegar_prompt(page, editor, prompt)
        await pausa(0.5, 1.5)
        send = page.locator(S.GM_SEND_BUTTON).first
        try:
            await send.wait_for(state="visible", timeout=15000)
            await send.click()
        except Exception:
            await page.keyboard.press("Enter")

    async def _esperar_respuesta(self, page: Page, hooks: Hooks) -> None:
        with contextlib.suppress(Exception):
            await page.wait_for_selector(S.GM_STOP_BUTTON, timeout=20000)
        fin = time.monotonic() + config.GEMINI_RESPONSE_TIMEOUT_S
        anterior, estable = "", 0
        while time.monotonic() < fin:
            if await self._bloqueado(page):
                await hooks.esperar_usuario(
                    "Gemini pide una verificacion (captcha o aviso). "
                    "Resuelvela en Chrome y pulsa continuar."
                )
            escribiendo = await page.locator(S.GM_STOP_BUTTON).count() > 0
            texto = await self._ultimo_texto(page)
            estable = estable + 1 if (not escribiendo and texto and texto == anterior) else 0
            anterior = texto
            if estable >= 3:
                return
            await asyncio.sleep(2)
        raise GeminiError("Gemini no termino de responder a tiempo.")

    async def _ultimo_texto(self, page: Page) -> str:
        respuestas = page.locator(S.GM_RESPONSE)
        if not await respuestas.count():
            return ""
        return (await respuestas.last.inner_text()).strip()

    async def _leer_markdown(self, page: Page) -> str:
        with contextlib.suppress(Exception):
            ultima = page.locator("model-response").last
            await ultima.hover()
            await ultima.locator(S.GM_COPY_BUTTON).first.click(timeout=8000)
            await pausa(0.3, 0.8)
            copiado = await page.evaluate("navigator.clipboard.readText()")
            if copiado and copiado.strip():
                return copiado.strip()
        texto = await self._ultimo_texto(page)
        if not texto:
            raise GeminiError("No se pudo leer la respuesta de Gemini.")
        return texto
