import pytest

from backend import services
from backend.core import nexus
from backend.core.types import EtapaItem, TareaItem

from . import fixtures


@pytest.mark.parametrize(
    "titulo",
    [
        "Dimensión 1 - Recuperación - Autoevaluación E1",
        "AUTOEVALUACION",
        "autoevaluación final",
        "Autoevaluacion 2",
    ],
)
def test_detecta_autoevaluacion(titulo):
    assert nexus.es_autoevaluacion(titulo)


@pytest.mark.parametrize("titulo", ["Dimensión 2 - Comprensión - Ficha Técnica", "Evidencia", ""])
def test_no_detecta_otras(titulo):
    assert not nexus.es_autoevaluacion(titulo)


def test_estructura_oculta_autoevaluaciones_y_conserva_indice_original():
    etapas = nexus.parse_estructura(fixtures.estructura_html())
    for etapa in etapas:
        assert all(not nexus.es_autoevaluacion(t.titulo) for t in etapa.tareas)
    primera = etapas[0].tareas[0]
    assert primera.numero == "1.2"
    assert primera.orden == 1


def test_indice_de_clic_sigue_siendo_el_original(seeded):
    etapas = nexus.parse_estructura(fixtures.estructura_html())
    seeded.storage.replace_estructura("100", etapas)
    filas = seeded.storage.tareas_con_posicion("100")
    primera = next(f for f in filas if f["numero"] == "1.2")
    assert primera["tarea_idx"] == 1


def test_limpia_autoevaluaciones_guardadas(seeded):
    storage = seeded.storage
    storage.replace_estructura(
        "100",
        [
            EtapaItem(
                "E1",
                "d",
                0,
                [
                    TareaItem("1.1", "Dimensión 1 - Autoevaluación E1", "dimension", 1.0, None, 0),
                    TareaItem("1.2", "Dimensión 2 - Ficha", "dimension", 1.0, None, 1),
                ],
            )
        ],
    )
    storage.add_insumo("100-1.1", "texto", texto="hola")
    assert services.limpiar_autoevaluaciones(storage) == 1
    assert [t["id"] for t in storage.list_etapas("100")[0]["tareas"]] == ["100-1.2"]
    assert storage.list_insumos("100-1.1") == []
