import asyncio

import pytest

from backend import services
from backend.core import nexus
from backend.core.types import DetalleTarea, EtapaItem, MateriaCard, Portada, TareaItem

from . import fixtures


@pytest.mark.parametrize(
    "titulo",
    [
        "Examen Diagnóstico Etapa 1",
        "Examen Diagnóstico etapa 4",
        "Diagnostic Evaluation Stage 2",
        "E1-Dimensión 1. Recuperación: Cuestionario en línea.",
        "EXAMEN FINAL",
        "cuestionario en linea",
    ],
)
def test_clasifica_examenes(titulo):
    assert nexus.es_examen(titulo)
    assert nexus.clasificar(titulo) == "examen"


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        ("Dimensión 2 - Comprensión - Ficha Técnica", "dimension"),
        ("Evidencia de Aprendizaje - Informe", "evidencia"),
    ],
)
def test_otros_tipos(titulo, esperado):
    assert nexus.clasificar(titulo) == esperado


def test_pia_por_etapa_aunque_el_titulo_no_lo_diga():
    assert nexus.clasificar("ILP: Video", en_pia=True) == "pia"


def test_estructura_real_marca_pia_y_examen():
    html = fixtures.estructura_html().replace(
        "Evidencia de Aprendizaje - Informe", "Examen Diagnóstico Etapa 1"
    )
    etapas = nexus.parse_estructura(html)
    assert etapas[0].tareas[2].tipo == "examen"
    assert etapas[0].tareas[0].tipo == "dimension"
    assert etapas[4].tareas[0].tipo == "pia"


class _Contador:
    def __init__(self, sel=""):
        self.sel = sel

    async def count(self):
        return 0 if "sesi" in self.sel else 1


class _Pagina:
    url = "https://plataformanexus.uanl.mx/#/App"

    def is_closed(self):
        return False

    def locator(self, sel):
        return _Contador(sel)

    async def close(self):
        return None

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


def test_sync_no_abre_examenes_ni_pia_y_no_son_errores(state, monkeypatch):
    abiertas = []

    async def ensure(st, hooks, **kw):
        return _Pagina()

    async def leer(page):
        return [MateriaCard("100", "Lógica", 0)]

    async def abrir_materia(page, i, nombre=None):
        return Portada("PROFE", "p", None)

    async def abrir_estructura(page):
        return [
            EtapaItem(
                "Etapa 1",
                "d",
                0,
                [
                    TareaItem("1.1", "Dimensión 1 - Algo", "dimension", 2.0, None, 0),
                    TareaItem("1.2", "Examen Diagnóstico Etapa 1", "examen", 5.0, None, 1),
                ],
            ),
            EtapaItem(
                "Producto Integrador de Aprendizaje",
                "d",
                1,
                [TareaItem("PIA", "PIA: Video", "pia", None, None, 0)],
            ),
        ]

    async def abrir_tarea(page, e, t, numero=None, **kw):
        abiertas.append(numero)
        return DetalleTarea("T", numero, None, None, 1.0, None, "a", "c", "k", None)

    async def nada(page):
        return None

    monkeypatch.setattr(services, "ensure_nexus", ensure)
    monkeypatch.setattr(nexus, "leer_materias", leer)
    monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
    monkeypatch.setattr(nexus, "abrir_estructura", abrir_estructura)
    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    monkeypatch.setattr(nexus, "volver_a_estructura", nada)
    monkeypatch.setattr(nexus, "volver_a_lista", nada)
    cola = state.jobs.subscribe()

    async def escenario():
        job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, "completo"))
        for _ in range(300):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    job = asyncio.run(escenario())
    assert job.estado == "ok", job.mensaje
    assert abiertas == ["1.1"]
    assert job.resultado["errores"] == [] and job.resultado["detalles_leidos"] == 1
    assert job.resultado["tareas"] == 3
    tareas = {t["numero"]: t for e in state.storage.list_etapas("100") for t in e["tareas"]}
    assert tareas["1.2"]["tipo"] == "examen" and tareas["1.2"]["estado"] == "pendiente"
    assert tareas["PIA"]["tipo"] == "pia"
    mensajes = []
    while not cola.empty():
        mensajes.append(cola.get_nowait())
    assert any(
        m.get("type") == "log" and "PIA pendiente de soporte" in m["message"] for m in mensajes
    )
