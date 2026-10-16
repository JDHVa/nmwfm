import asyncio
from pathlib import Path

import pytest

from backend.core import selectors as S
from backend.core.gemini import GeminiError, GeminiWeb


class _Chooser:
    def __init__(self, eventos):
        self.eventos = eventos

    async def set_files(self, ruta):
        self.eventos.append(("set_files", ruta))


class _Ctx:
    def __init__(self, eventos):
        self.eventos = eventos
        self.value = self._valor()

    async def _valor(self):
        return _Chooser(self.eventos)

    async def __aenter__(self):
        self.eventos.append("esperando_chooser")
        return self

    async def __aexit__(self, *a):
        return False


class _Loc:
    def __init__(self, eventos, selector, visible):
        self.eventos, self.selector, self.visible = eventos, selector, visible

    @property
    def first(self):
        return self

    async def is_visible(self):
        return self.visible

    async def click(self, timeout=None):
        self.eventos.append(("click", self.selector, timeout))


class _Page:
    def __init__(self, menu_visible=True):
        self.eventos = []
        self.menu_visible = menu_visible

    def locator(self, selector):
        return _Loc(self.eventos, selector, self.menu_visible)

    def expect_file_chooser(self):
        return _Ctx(self.eventos)

    async def wait_for_selector(self, selector, timeout=None):
        self.eventos.append(("chip", selector, timeout))


def test_selectores_validados_primero():
    assert S.GM_UPLOAD_MENU_BUTTON.startswith("button[aria-label='Subidas y herramientas']")
    assert S.GM_UPLOAD_MENU_ITEM.startswith(
        "button[data-test-id='local-images-files-uploader-button']"
    )


def test_adjuntar_abre_menu_luego_chooser_y_espera_chip():
    page = _Page()
    asyncio.run(GeminiWeb(browser=None)._adjuntar(page, Path("a.pdf")))
    assert page.eventos == [
        ("click", S.GM_UPLOAD_MENU_BUTTON, 10000),
        "esperando_chooser",
        ("click", S.GM_UPLOAD_MENU_ITEM, 10000),
        ("set_files", "a.pdf"),
        ("chip", S.GM_ATTACHMENT_CHIP, 60000),
    ]


def test_adjuntar_sin_menu_visible_da_error_claro():
    with pytest.raises(GeminiError, match="botón de carga"):
        asyncio.run(GeminiWeb(browser=None)._adjuntar(_Page(menu_visible=False), Path("a.pdf")))
