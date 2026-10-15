from backend import services
from backend.core import nexus

from .asgi_client import MiniClient
from .test_automatizacion import Nexus, sync

TABLA = """
<div><table class="mat-table">
<thead><tr><th>Etapa</th><th>Puntos</th><th>Calificación</th></tr></thead>
<tbody>
<tr><td>Etapa 1</td><td>30</td><td>28.5</td></tr>
<tr><td>Etapa 2</td><td>30</td><td>-/-</td></tr>
<tr><td></td><td></td><td></td></tr>
</tbody></table></div>
"""

TABLA_SIN_ENCABEZADO = (
    "<table><tr><th>Etapa</th><th>Nota</th></tr><tr><td>1</td><td>9</td></tr></table>"
)


def test_parse_con_encabezado():
    datos = nexus.parse_calificaciones(TABLA)
    assert datos["columnas"] == ["Etapa", "Puntos", "Calificación"]
    assert datos["filas"] == [["Etapa 1", "30", "28.5"], ["Etapa 2", "30", "-/-"]]


def test_parse_con_encabezado_en_la_primera_fila():
    datos = nexus.parse_calificaciones(TABLA_SIN_ENCABEZADO)
    assert datos["columnas"] == ["Etapa", "Nota"] and datos["filas"] == [["1", "9"]]


def test_parse_sin_tabla():
    assert nexus.parse_calificaciones("<div>Sin calificaciones</div>") is None


def test_sync_completo_guarda_calificaciones(app, state, monkeypatch):
    Nexus(monkeypatch)

    async def abrir(page):
        return TABLA

    monkeypatch.setattr(nexus, "abrir_calificaciones", abrir)
    sync(state, "completo")
    client = MiniClient(app, headers={"X-Token": "dev"})
    datos = client.get("/materias/100/calificaciones").json()
    assert datos["columnas"][2] == "Calificación" and len(datos["filas"]) == 2
    assert datos["actualizada_en"]


def test_sync_incremental_no_lee_calificaciones(state, monkeypatch):
    Nexus(monkeypatch)
    llamadas = []

    async def abrir(page):
        llamadas.append(1)
        return TABLA

    monkeypatch.setattr(nexus, "abrir_calificaciones", abrir)
    sync(state, "incremental")
    assert llamadas == []


def test_formato_desconocido_deja_snapshot_y_no_es_error(app, state, monkeypatch):
    Nexus(monkeypatch)

    async def abrir(page):
        return "<div>Aún no hay calificaciones</div>"

    monkeypatch.setattr(nexus, "abrir_calificaciones", abrir)
    job = sync(state, "completo")
    assert job.resultado["errores"] == []
    assert any(f.name.startswith("calificaciones-100") for f in state.paths.debug.iterdir())
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.get("/materias/100/calificaciones").json() is None
    assert client.get("/materias/999/calificaciones").status_code == 404


def test_fallo_al_abrir_calificaciones_no_rompe_el_sync(state, monkeypatch):
    Nexus(monkeypatch)

    async def abrir(page):
        raise TimeoutError("sin menú")

    monkeypatch.setattr(nexus, "abrir_calificaciones", abrir)
    job = sync(state, "completo")
    assert job.resultado["errores"] == [] and job.resultado["detalles_leidos"] == 1
    assert services.metricas is not None
