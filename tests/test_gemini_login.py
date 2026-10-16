import asyncio

import pytest

from backend import services
from backend.core.gemini import GeminiError, GeminiWeb
from backend.core.types import Hooks


class _Page:
    def __init__(self):
        self.cerrada = False
        self.url = "https://gemini.google.com/app"

    def is_closed(self):
        return self.cerrada

    async def close(self):
        self.cerrada = True

    async def goto(self, url, wait_until=None):
        pass


class _Contexto:
    async def grant_permissions(self, *a, **k):
        pass

    async def new_page(self):
        return _Page()


class _Browser:
    def __init__(self, headless=True):
        self._headless = headless
        self.pedidos = []

    async def context(self, headless=None):
        self.pedidos.append(headless)
        if headless is not None:
            self._headless = headless
        return _Contexto()


def _hooks(pasos, esperas=None):
    async def paso(texto, avance):
        pasos.append((texto, avance))

    async def esperar(texto):
        if esperas is not None:
            esperas.append(texto)

    return Hooks(paso=paso, esperar_usuario=esperar)


def _con_sesion(web, monkeypatch, valores):
    it = iter(valores)

    async def hay(page):
        return next(it)

    monkeypatch.setattr(web, "_hay_sesion", hay)


def test_sesion_ya_iniciada_avisa_y_abre_visible(monkeypatch):
    browser = _Browser(headless=True)
    web = GeminiWeb(browser)
    _con_sesion(web, monkeypatch, [True])
    pasos = []
    assert asyncio.run(web.iniciar_sesion(_hooks(pasos))) is True
    assert pasos[-1] == ("Ya tienes la sesión de Gemini iniciada", 1.0)
    assert browser.pedidos == [False]


def test_run_login_gemini_devuelve_ya_iniciada(monkeypatch):
    class Lock:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class Gem:
        async def iniciar_sesion(self, hooks):
            return True

    class Ctx:
        def hooks(self):
            return Hooks()

    class Estado:
        gemini = Gem()

        class browser_gemini:
            lock = Lock()

            @staticmethod
            async def close():
                pass

    monkeypatch.setattr(services, "ESPERA_COOKIES_GEMINI_S", 0)
    res = asyncio.run(services.run_login_gemini(Estado(), Ctx()))
    assert res == {"sesion": True, "ya_iniciada": True}


def test_generar_relanza_visible_si_hace_falta_login(monkeypatch):
    browser = _Browser(headless=True)
    web = GeminiWeb(browser)
    _con_sesion(web, monkeypatch, [False, False, True])
    esperas = []

    async def run():
        page = await web._abrir()
        return page, await web._asegurar_sesion(page, _hooks([], esperas))

    page, res = asyncio.run(run())
    assert browser.pedidos == [None, False]
    assert len(esperas) == 1
    assert res is not page


def test_asegurar_sesion_falla_solo_tras_dos_intentos(monkeypatch):
    web = GeminiWeb(_Browser(headless=False))
    _con_sesion(web, monkeypatch, [False, False, False])
    esperas = []

    async def run():
        page = await web._abrir()
        await web._asegurar_sesion(page, _hooks([], esperas))

    with pytest.raises(GeminiError):
        asyncio.run(run())
    assert len(esperas) == 2


def test_asegurar_sesion_se_recupera_en_el_segundo_intento(monkeypatch):
    web = GeminiWeb(_Browser(headless=False))
    _con_sesion(web, monkeypatch, [False, True])
    esperas = []

    async def run():
        page = await web._abrir()
        return page, await web._asegurar_sesion(page, _hooks([], esperas))

    page, res = asyncio.run(run())
    assert res is page and len(esperas) == 1
