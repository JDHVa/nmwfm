import asyncio

from backend import check, services
from backend.core import nexus
from backend.core import selectors as S
from backend.core.types import DetalleTarea, EtapaItem, MateriaCard, Portada, TareaItem

from .asgi_client import MiniClient


class _Loc:
    def __init__(self, ausentes, sel):
        self.ausentes, self.sel = ausentes, sel

    async def count(self):
        return 0 if self.sel in self.ausentes else 1


class _Pagina:
    url = "https://plataformanexus.uanl.mx/#/App"

    def __init__(self, ausentes=()):
        self.ausentes = set(ausentes)

    def is_closed(self):
        return False

    def locator(self, sel):
        return _Loc(self.ausentes, sel)


def montar(monkeypatch, ausentes=(), tareas=None, rubrica=True, entregas=True):
    pagina = _Pagina(ausentes)

    async def ensure(st, hooks, **kw):
        return pagina

    async def en_lista(page):
        return None

    async def leer(page):
        return [MateriaCard("1", "Lógica", 0)]

    async def abrir_materia(page, i, nombre=None):
        return Portada("PROFE", "p", None)

    async def abrir_estructura(page):
        items = (
            tareas
            if tareas is not None
            else [
                TareaItem("1.1", "Examen Diagnóstico", "examen", None, None, 0),
                TareaItem("1.2", "Dimensión 2 - Ficha", "dimension", 2.0, None, 1),
            ]
        )
        return [EtapaItem("E", "d", 0, items)]

    async def abrir_tarea(page, e, t, numero=None, **kw):
        assert (t, numero) == (1, "1.2") and kw["entregas"] is True
        return DetalleTarea(
            "Ficha",
            numero,
            None,
            None,
            2.0,
            None,
            "a",
            "c",
            "k",
            object() if rubrica else None,
            [] if entregas else None,
        )

    async def calificaciones(page):
        return "<table><tr><th>E</th></tr><tr><td>1</td></tr></table>"

    async def nada(page):
        return None

    monkeypatch.setattr(services, "ensure_nexus", ensure)
    monkeypatch.setattr(services, "_en_lista", en_lista)
    monkeypatch.setattr(nexus, "leer_materias", leer)
    monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
    monkeypatch.setattr(nexus, "abrir_estructura", abrir_estructura)
    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    monkeypatch.setattr(nexus, "abrir_calificaciones", calificaciones)
    monkeypatch.setattr(nexus, "volver_a_lista", nada)


def correr(state):
    return asyncio.run(check.ejecutar(state))


def test_todo_bien(state, monkeypatch):
    montar(monkeypatch)
    reporte = correr(state)
    assert reporte["ok"] is True
    assert [p["nombre"] for p in reporte["pasos"]] == [
        "login",
        "lista de materias",
        "portada de la materia",
        "estructura",
        "detalle de la tarea",
        "rúbrica",
        "entregas",
        "calificaciones",
    ]
    assert all(p["ms"] >= 0 and p["selectores_faltantes"] == [] for p in reporte["pasos"])
    assert "1.2" in reporte["pasos"][4]["detalle"]


def test_reporta_los_selectores_que_fallan(state, monkeypatch):
    montar(monkeypatch, ausentes={S.NX_PANEL_TITLE})
    reporte = correr(state)
    assert reporte["ok"] is False
    paso = reporte["pasos"][-1]
    assert paso["nombre"] == "estructura" and paso["ok"] is False
    assert paso["selectores_faltantes"] == [S.NX_PANEL_TITLE]
    texto = check.formatear(reporte)
    assert "[FALLA] estructura" in texto and S.NX_PANEL_TITLE in texto
    assert texto.endswith("hay pasos con falla")


def test_falla_de_login_corta_el_diagnostico(state, monkeypatch):
    async def ensure(st, hooks, **kw):
        raise RuntimeError("Cuenta o contraseña incorrecta")

    monkeypatch.setattr(services, "ensure_nexus", ensure)
    reporte = correr(state)
    assert [p["nombre"] for p in reporte["pasos"]] == ["login"]
    assert reporte["pasos"][0]["ok"] is False
    assert "incorrecta" in reporte["pasos"][0]["detalle"]


def test_sin_tarea_de_prueba(state, monkeypatch):
    montar(monkeypatch, tareas=[TareaItem("1.1", "Examen", "examen", None, None, 0)])
    reporte = correr(state)
    assert reporte["pasos"][-1]["nombre"] == "tarea de prueba" and not reporte["ok"]


def test_rubrica_o_entregas_ausentes_marcan_el_paso(state, monkeypatch):
    montar(monkeypatch, rubrica=False, entregas=False)
    reporte = correr(state)
    fallidos = [p["nombre"] for p in reporte["pasos"] if not p["ok"]]
    assert fallidos == ["rúbrica", "entregas"]


def test_endpoint_diagnostico_es_un_job(app, state, monkeypatch):
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.post("/diagnostico").status_code == 400
    state.storage.set_settings({"cuenta": "1"})
    state.credentials.set("1", "pw")
    montar(monkeypatch)

    async def escenario():
        a = await client.arequest("POST", "/diagnostico")
        b = await client.arequest("POST", "/diagnostico")
        return a.json(), b.json()

    a, b = asyncio.run(escenario())
    assert a["tipo"] == "diagnostico" and a["id"] == b["id"]
