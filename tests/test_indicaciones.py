from backend.core.prompt_builder import PromptData, build_prompt
from backend.core.types import DetalleTarea, EtapaItem, TareaItem

from .asgi_client import MiniClient
from .test_automatizacion import Nexus, sync

TID = "100-1.1"
TITULO = "## Indicaciones adicionales del profesor (prioridad sobre la descripción)"


def test_put_guarda_y_devuelve_el_detalle_con_indicaciones(app, seeded):
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.put(f"/tareas/{TID}/indicaciones", json={"indicaciones": "  Entregar a mano  "})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["indicaciones"] == "Entregar a mano" and cuerpo["id"] == TID
    assert cuerpo["rubrica"] is None and cuerpo["actividades"] == ""
    assert seeded.storage.get_indicaciones(TID) == "Entregar a mano"


def test_get_tarea_incluye_las_indicaciones(app, seeded):
    seeded.storage.set_detalle(
        TID, DetalleTarea("T", "1.1", None, None, 1.0, None, "act", "cont", "crit", None)
    )
    seeded.storage.set_indicaciones(TID, "Usar Arial 12")
    client = MiniClient(app, headers={"X-Token": "dev"})
    cuerpo = client.get(f"/tareas/{TID}").json()
    assert cuerpo["indicaciones"] == "Usar Arial 12" and cuerpo["actividades"] == "act"


def test_sin_indicaciones_devuelve_cadena_vacia(app, seeded):
    seeded.storage.set_detalle(
        TID, DetalleTarea("T", "1.1", None, None, 1.0, None, "a", "c", "k", None)
    )
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.get(f"/tareas/{TID}").json()["indicaciones"] == ""


def test_put_en_tarea_inexistente_da_404(app, seeded):
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.put("/tareas/nada/indicaciones", json={"indicaciones": "x"}).status_code == 404
    assert client.put(f"/tareas/{TID}/indicaciones", json={}).status_code == 422


def test_el_sync_nunca_toca_las_indicaciones(state, monkeypatch):
    fake = Nexus(monkeypatch)
    sync(state, "auto")
    state.storage.set_indicaciones("100-1.1", "Nota del pizarrón")
    fake.titulo = "Dimensión 1 - Título nuevo"
    fake.contenido = "contenido v2"
    sync(state, "completo")
    sync(state, "incremental")
    assert state.storage.get_indicaciones("100-1.1") == "Nota del pizarrón"
    assert state.storage.get_detalle("100-1.1")["contenido"] == "contenido v2"


def test_las_indicaciones_se_van_con_la_tarea(seeded):
    seeded.storage.set_indicaciones(TID, "x")
    seeded.storage.replace_estructura(
        "100", [EtapaItem("E", "d", 0, [TareaItem("9.9", "Otra", "evidencia", 1.0, None, 0)])]
    )
    assert seeded.storage.get_indicaciones(TID) == ""


def test_el_prompt_las_incluye_con_prioridad_y_antes_del_contenido():
    prompt = build_prompt(
        PromptData(
            materia="M",
            titulo="T",
            actividades="Haz algo",
            contenido="Tema X",
            indicaciones="El profe pidió máximo 2 hojas",
        )
    )
    assert TITULO in prompt and "máximo 2 hojas" in prompt
    assert prompt.index("Haz algo") < prompt.index(TITULO) < prompt.index("Tema X")


def test_prompt_sin_indicaciones_no_agrega_la_seccion():
    assert TITULO not in build_prompt(PromptData(materia="M", titulo="T", indicaciones="  "))
