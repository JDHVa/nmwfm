import asyncio

from backend.api import create_app

from .asgi_client import MiniClient


class Manager:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.cierres = 0

    async def close(self):
        self.cierres += 1


def _client(state):
    return MiniClient(create_app(state=state), headers={"X-Token": "dev"})


async def _ok(ctx):
    return 1


def test_cancelar_corriendo_libera_lock_y_cierra_navegador(state):
    client = _client(state)
    state.browser = Manager()
    state.browser_gemini = Manager()

    async def scenario():
        dentro = asyncio.Event()

        async def largo(ctx):
            async with state.browser.lock:
                dentro.set()
                await asyncio.sleep(60)

        job = state.jobs.start("sync", largo)
        await dentro.wait()
        assert state.browser.lock.locked()
        data = (await client.arequest("POST", f"/jobs/{job.id}/cancelar")).json()
        assert data["estado"] == "error"
        assert data["mensaje"] == "Cancelado por el usuario"
        assert data["resultado"] == {"cancelado": True}
        assert not state.browser.lock.locked()
        assert state.browser.cierres == 1 and state.browser_gemini.cierres == 0
        siguiente = state.jobs.start("sync", _ok)
        await asyncio.sleep(0.05)
        assert siguiente.estado == "ok"

    asyncio.run(scenario())


def test_cancelar_generar_cierra_gemini(state):
    client = _client(state)
    state.browser = Manager()
    state.browser_gemini = Manager()

    async def scenario():
        async def largo(ctx):
            await asyncio.sleep(60)

        job = state.jobs.start("generar", largo)
        await asyncio.sleep(0.02)
        await client.arequest("POST", f"/jobs/{job.id}/cancelar")
        assert state.browser_gemini.cierres == 1 and state.browser.cierres == 0

    asyncio.run(scenario())


def test_cancelar_esperando_usuario(state):
    client = _client(state)

    async def scenario():
        async def espera(ctx):
            await ctx.wait_user("captcha")

        job = state.jobs.start("revisar_entregas", espera)
        for _ in range(50):
            if job.estado == "esperando_usuario":
                break
            await asyncio.sleep(0.02)
        assert job.estado == "esperando_usuario"
        data = (await client.arequest("POST", f"/jobs/{job.id}/cancelar")).json()
        assert data["estado"] == "error" and data["resultado"] == {"cancelado": True}

    asyncio.run(scenario())


def test_cancelar_terminado_lo_devuelve_igual(state):
    client = _client(state)
    state.browser = Manager()

    async def scenario():
        async def rapido(ctx):
            return {"x": 1}

        job = state.jobs.start("sync", rapido)
        await asyncio.sleep(0.05)
        data = (await client.arequest("POST", f"/jobs/{job.id}/cancelar")).json()
        assert data["estado"] == "ok" and data["resultado"] == {"x": 1}
        assert state.browser.cierres == 0

    asyncio.run(scenario())


def test_cancelar_inexistente_404(client):
    assert client.post("/jobs/zzz/cancelar").status_code == 404
