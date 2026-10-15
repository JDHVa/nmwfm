import asyncio

from backend import services
from backend.core import siase


def correr(state):
    async def scenario():
        job = state.jobs.start("validar_siase", lambda ctx: services.run_validar_siase(state, ctx))
        for _ in range(200):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    return asyncio.run(scenario())


def preparar(state, monkeypatch, resultado):
    state.storage.set_settings({"cuenta": "123"})
    state.credentials.set("123", "pw")

    async def fake_context():
        return object()

    async def fake_validar(ctx, cuenta, password, hooks=None):
        assert (cuenta, password) == ("123", "pw")
        if resultado is not None:
            raise resultado

    monkeypatch.setattr(state.browser, "context", fake_context)
    monkeypatch.setattr(siase, "validar", fake_validar)


def test_validar_ok(state, monkeypatch):
    preparar(state, monkeypatch, None)
    job = correr(state)
    assert job.estado == "ok" and job.mensaje is None


def test_validar_credenciales_malas(state, monkeypatch):
    preparar(state, monkeypatch, siase.CredencialesInvalidas("Cuenta o contraseña incorrecta"))
    job = correr(state)
    assert job.estado == "error" and job.mensaje == "Cuenta o contraseña incorrecta"


def test_validar_sin_respuesta(state, monkeypatch):
    preparar(state, monkeypatch, siase.SiaseSinRespuesta("SIASE no responde"))
    job = correr(state)
    assert job.estado == "error" and job.mensaje == "SIASE no responde"


def test_validar_sin_credenciales(state):
    job = correr(state)
    assert job.estado == "error" and job.mensaje == "Faltan credenciales"


def test_endpoint_crea_job(client):
    r = client.post("/siase/validar")
    assert r.status_code == 200
    body = r.json()
    assert body["tipo"] == "validar_siase"
    assert body["estado"] in ("en_cola", "corriendo", "error")


def test_endpoint_requiere_token(app):
    from .asgi_client import MiniClient

    assert MiniClient(app).post("/siase/validar").status_code in (401, 403)
