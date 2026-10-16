import asyncio

from backend import services
from backend.api import create_app
from backend.core.gemini import GeminiWeb
from backend.core.types import Hooks

from .asgi_client import MiniClient
from .test_cancelar_jobs import Manager
from .test_gemini_login import _Browser


def _client(state):
    return MiniClient(create_app(state=state), headers={"X-Token": "dev"})


class _Gem:
    def __init__(self, sesion=True, demora=0):
        self.sesion = sesion
        self.demora = demora

    async def sesion_activa(self):
        await asyncio.sleep(self.demora)
        return self.sesion

    async def iniciar_sesion(self, hooks):
        return False


def test_settings_nacen_en_null_y_put_los_ignora(state):
    client = _client(state)
    s = client.request("GET", "/settings").json()
    assert s["gemini_sesion"] is None and s["gemini_sesion_verificada_en"] is None
    s = client.request(
        "PUT",
        "/settings",
        json={"gemini_sesion": True, "gemini_sesion_verificada_en": "x"},
    ).json()
    assert s["gemini_sesion"] is None and s["gemini_sesion_verificada_en"] is None


def test_verificar_guarda_resultado(state):
    client = _client(state)
    state.browser_gemini = Manager()
    for sesion in (True, False):
        state.gemini = _Gem(sesion)

        async def scenario():
            job = (await client.arequest("POST", "/gemini/verificar")).json()
            for _ in range(100):
                await asyncio.sleep(0.01)
                job = (await client.arequest("GET", f"/jobs/{job['id']}")).json()
                if job["estado"] not in ("pendiente", "corriendo"):
                    return job

        job = asyncio.run(scenario())
        assert job["tipo"] == "verificar_gemini"
        assert job["estado"] == "ok" and job["resultado"] == {"sesion": sesion}
        s = state.storage.get_settings()
        assert s["gemini_sesion"] is sesion and s["gemini_sesion_verificada_en"]
    assert state.browser_gemini.cierres == 2


def test_cancelar_verificar_cierra_gemini(state):
    client = _client(state)
    state.browser_gemini = Manager()
    state.gemini = _Gem(demora=60)

    async def scenario():
        job = (await client.arequest("POST", "/gemini/verificar")).json()
        await asyncio.sleep(0.05)
        data = (await client.arequest("POST", f"/jobs/{job['id']}/cancelar")).json()
        assert data["estado"] == "error"
        assert not state.browser_gemini.lock.locked()

    asyncio.run(scenario())
    assert state.browser_gemini.cierres >= 1
    assert state.storage.get_settings()["gemini_sesion"] is None


def test_login_deja_sesion_true(state, monkeypatch):
    state.browser_gemini = Manager()
    state.gemini = _Gem()
    monkeypatch.setattr(services, "ESPERA_COOKIES_GEMINI_S", 0)

    class Ctx:
        def hooks(self):
            return Hooks()

    asyncio.run(services.run_login_gemini(state, Ctx()))
    assert state.storage.get_settings()["gemini_sesion"] is True


def test_generar_avisa_sesion(monkeypatch):
    avisos = []
    web = GeminiWeb(_Browser(headless=False), al_cambiar_sesion=avisos.append)
    valores = iter([False, True])

    async def hay(page):
        return next(valores)

    async def esperar(texto):
        pass

    monkeypatch.setattr(web, "_hay_sesion", hay)

    async def run():
        page = await web._abrir()
        await web._asegurar_sesion(page, Hooks(esperar_usuario=esperar))

    asyncio.run(run())
    assert avisos == [False, True]
