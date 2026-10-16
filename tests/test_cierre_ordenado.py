import asyncio

import pytest

from backend import services
from backend.api import create_app
from backend.core.types import Hooks

from .asgi_client import MiniClient
from .test_services import correr, listo  # noqa: F401


class Manager:
    def __init__(self, eventos, nombre):
        self.eventos = eventos
        self.nombre = nombre
        self.lock = asyncio.Lock()

    async def close(self):
        self.eventos.append(f"close:{self.nombre}")


class GeminiLogin:
    def __init__(self, eventos):
        self.eventos = eventos

    async def iniciar_sesion(self, hooks):
        self.eventos.append("sesion")
        return False


class Ctx:
    def hooks(self):
        return Hooks()


def test_login_espera_y_cierra_gemini(state, monkeypatch):
    eventos = []
    state.browser_gemini = Manager(eventos, "gemini")
    state.gemini = GeminiLogin(eventos)

    async def sleep(segundos):
        eventos.append(f"espera:{segundos}")

    monkeypatch.setattr(services.asyncio, "sleep", sleep)
    res = asyncio.run(services.run_login_gemini(state, Ctx()))
    assert res["sesion"] is True
    assert eventos == ["sesion", "espera:3.0", "close:gemini"]


def test_login_cierra_gemini_si_falla(state):
    eventos = []

    class Falla:
        async def iniciar_sesion(self, hooks):
            raise RuntimeError("x")

    state.browser_gemini = Manager(eventos, "gemini")
    state.gemini = Falla()
    with pytest.raises(RuntimeError):
        asyncio.run(services.run_login_gemini(state, Ctx()))
    assert eventos == ["close:gemini"]


def test_generar_cierra_gemini(listo):  # noqa: F811
    eventos = []
    listo.browser_gemini = Manager(eventos, "gemini")
    job = correr(listo)
    assert job.estado == "ok"
    assert eventos == ["close:gemini"]


def test_apagar_cierra_ambos_y_programa_salida(state):
    eventos = []
    state.browser = Manager(eventos, "nexus")
    state.browser_gemini = Manager(eventos, "gemini")
    app = create_app(state=state)
    salidas = []
    app.state.salir = lambda: salidas.append(1)
    cliente = MiniClient(app, headers={"X-Token": "dev"})

    async def escenario():
        r = await cliente.arequest("POST", "/apagar")
        await asyncio.sleep(0.5)
        return r

    r = asyncio.run(escenario())
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert eventos == ["close:nexus", "close:gemini"]
    assert salidas == [1]


def test_apagar_exige_token(state):
    app = create_app(state=state)
    cliente = MiniClient(app)
    r = asyncio.run(cliente.arequest("POST", "/apagar"))
    assert r.status_code == 401
