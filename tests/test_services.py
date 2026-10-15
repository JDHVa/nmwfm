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

    async def fake_ensure(state, hooks, **kw):
        return None

    async def fake_abrir(state, page, tarea_id):
        return None

    async def fake_volver(page):
        return None

    monkeypatch.setattr(services, "ensure_nexus", fake_ensure)
    monkeypatch.setattr(services, "_abrir_tarea_nexus", fake_abrir)
    monkeypatch.setattr(nexus, "volver_a_lista", fake_volver)
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

    async def fake_entregar(page, pdf, hooks=None):
        llamadas.append(pdf)

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    job = correr(listo)
    assert job.estado == "ok" and llamadas == []
    assert listo.storage.get_tarea(TID)["estado"] == "generada"


def test_generar_encadena_entrega(listo, monkeypatch):
    llamadas = []

    async def fake_entregar(page, pdf, hooks=None):
        llamadas.append(str(pdf))

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    listo.storage.set_settings({"entregar_sin_revisar": True})
    job = correr(listo)
    assert job.estado == "ok", job.mensaje
    assert len(llamadas) == 1 and llamadas[0].endswith("x.pdf")
    assert job.paso == "entregando"
    assert listo.storage.get_tarea(TID)["estado"] == "entregada"
    assert listo.storage.get_tarea(TID)["entregada_en"]


def test_entrega_fallida_deja_generacion(listo, monkeypatch):
    async def fake_entregar(page, pdf, hooks=None):
        raise NotImplementedError("sin dialogo")

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    listo.storage.set_settings({"entregar_sin_revisar": True})
    job = correr(listo)
    assert job.estado == "error" and "sin dialogo" in job.mensaje
    assert listo.storage.get_generacion(TID) is not None
    assert listo.storage.get_tarea(TID)["estado"] == "generada"


def test_entrega_registra_historial_y_reemplaza(listo, monkeypatch):
    async def fake_entregar(page, pdf, hooks=None):
        return None

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    listo.storage.set_settings({"entregar_sin_revisar": True})
    assert correr(listo).estado == "ok"
    historial = listo.storage.list_entregas(TID)
    assert len(historial) == 1 and historial[0]["pdf_path"].endswith("x.pdf")
    assert historial[0]["entregada_en"]

    job = correr(listo)
    assert job.estado == "ok"
    assert len(listo.storage.list_entregas(TID)) == 2
    assert listo.storage.get_tarea(TID)["estado"] == "entregada"


def test_entrega_fallida_no_registra_historial(listo, monkeypatch):
    async def fake_entregar(page, pdf, hooks=None):
        raise nexus.EntregaError("rechazada")

    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    listo.storage.set_settings({"entregar_sin_revisar": True})
    assert correr(listo).estado == "error"
    assert listo.storage.list_entregas(TID) == []


def test_entrega_corre_oculta(listo, monkeypatch):
    modos = []

    async def fake_ensure(state, hooks, **kw):
        modos.append(kw.get("headless"))

    async def fake_entregar(page, pdf, hooks=None):
        return None

    monkeypatch.setattr(services, "ensure_nexus", fake_ensure)
    monkeypatch.setattr(nexus, "entregar", fake_entregar)
    listo.storage.set_settings({"entregar_sin_revisar": True})
    job = correr(listo)
    assert job.estado == "ok", job.mensaje
    assert modos == [True]
