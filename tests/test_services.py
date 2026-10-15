import asyncio

import pytest

from backend import services
from backend.core import nexus
from backend.core.types import DetalleTarea

TID = "100-1.1"


class FakeGemini:
    async def sesion_activa(self):
        return True

    async def iniciar_sesion(self, hooks):
        return None

    async def generar(self, prompt, pdf_path, hooks):
        await hooks.paso("gemini", 0.7)
        return "## Respuesta\n\nTexto"


@pytest.fixture
def listo(seeded, monkeypatch):
    seeded.gemini = FakeGemini()
    seeded.storage.set_settings({"nombre": "Ana", "matricula": "1"})
    seeded.storage.set_detalle(
        TID, DetalleTarea("T", "1.1", None, None, 0.0, None, "act", "cont", "crit", None)
    )

    def fake_docs(state, tarea, materia, settings, markdown):
        base = state.paths.generaciones
        return state.storage.set_generacion(
            tarea["id"], markdown, str(base / "x.docx"), str(base / "x.pdf")
        )

    monkeypatch.setattr(services, "_construir_documentos", fake_docs)
    return seeded


def correr(state):
    async def scenario():
        job = state.jobs.start("generar", lambda ctx: services.run_generar(state, ctx, TID, None))
        for _ in range(200):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    return asyncio.run(scenario())


def test_generar_sin_entrega_automatica(listo, monkeypatch):
    llamadas = []

    async def fake_entregar(page, pdf):
        llamadas.append(pdf)

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    job = correr(listo)
    assert job.estado == "ok" and llamadas == []
    assert listo.storage.get_tarea(TID)["estado"] == "generada"


def test_generar_encadena_entrega(listo, monkeypatch):
    llamadas = []

    async def fake_entregar(page, pdf):
        llamadas.append(str(pdf))

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    listo.storage.set_settings({"entregar_sin_revisar": True})
    job = correr(listo)
    assert job.estado == "ok" and len(llamadas) == 1 and llamadas[0].endswith("x.pdf")
    assert job.paso == "entregando"
    assert listo.storage.get_tarea(TID)["estado"] == "entregada"


def test_entrega_fallida_deja_generacion(listo, monkeypatch):
    async def fake_entregar(page, pdf):
        raise NotImplementedError("sin dialogo")

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    listo.storage.set_settings({"entregar_sin_revisar": True})
    job = correr(listo)
    assert job.estado == "error" and "sin dialogo" in job.mensaje
    assert listo.storage.get_generacion(TID) is not None
    assert listo.storage.get_tarea(TID)["estado"] == "generada"
