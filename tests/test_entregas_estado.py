import asyncio
import sqlite3
from datetime import datetime

from backend import services
from backend.core import nexus
from backend.core import selectors as S
from backend.core.storage import Storage
from backend.core.types import DetalleTarea, Entrega, EtapaItem, MateriaCard, Portada, TareaItem

from . import fixtures
from .asgi_client import MiniClient


def test_parse_entregas_con_fila_real():
    entregas = nexus.parse_entregas(fixtures.entregas_tabla_html())
    assert len(entregas) == 1
    assert entregas[0].nombre == "D2E1_ABI.pdf"
    assert entregas[0].fecha == "2026-09-20T22:24"
    assert nexus.tarea_entregada(fixtures.entregas_tabla_html())


def test_sin_entregas():
    assert nexus.parse_entregas(fixtures.entregas_vacio_html()) == []
    assert not nexus.tarea_entregada(fixtures.entregas_vacio_html())


def test_pestana_entregas_detectada():
    assert "entregas" in nexus.parse_pestanas(fixtures.pestanas_entregas_html())


def test_fechas_am_pm_y_ultima_entrega():
    assert nexus.parse_fecha_entrega("02-11-2026 12:00 am") == "2026-11-02T00:00"
    assert nexus.parse_fecha_entrega("02-11-2026 12:30 pm") == "2026-11-02T12:30"
    assert nexus.parse_fecha_entrega("sin fecha") is None
    entregas = [
        Entrega("a", "2026-09-20T10:00"),
        Entrega("b", "2026-09-21T09:00"),
        Entrega("c", None),
    ]
    assert nexus.ultima_entrega(entregas) == "2026-09-21T09:00"
    assert nexus.ultima_entrega([]) is None


class _Loc:
    def __init__(self, page, sel):
        self.page, self.sel = page, sel

    @property
    def first(self):
        return self

    def locator(self, sel, **kw):
        return _Loc(self.page, sel)

    def filter(self, **kw):
        return self

    async def count(self):
        p = self.page
        if self.sel == S.NX_ENTREGAS_FILA:
            p.sondeos += 1
            return 1 if (p.con_filas and p.sondeos > 2) else 0
        if self.sel == S.NX_ENTREGAS_VACIO:
            return 1 if (not p.con_filas and p.sondeos > 2) else 0
        if self.sel == S.NX_TAB_ENTREGAS_CSS:
            return 1
        return 1

    async def click(self, **kw):
        self.page.clics.append(self.sel)

    async def evaluate(self, script):
        if "outerHTML" in script:
            return fixtures.entregas_tabla_html()

    async def all_inner_texts(self):
        if self.sel == S.NX_TAB_ACTIVA:
            return ["Contenidos"]
        return ["x"]

    async def wait_for(self, **kw):
        return None


class _Page:
    def __init__(self, con_filas):
        self.con_filas = con_filas
        self.sondeos = 0
        self.clics = []

    def locator(self, sel):
        if sel == S.NX_ENTREGAS_FILA or sel == S.NX_ENTREGAS_VACIO:
            return _Loc(self, sel)
        return _Loc(self, sel)


def test_leer_entregas_espera_la_tabla_y_vuelve_a_contenidos():
    page = _Page(True)
    entregas = asyncio.run(nexus.leer_entregas(page))
    assert len(entregas) == 1 and page.sondeos > 2
    assert page.clics[0] == S.NX_TAB_ENTREGAS_CSS
    assert page.clics[-1] == S.NX_TAB_CONTENIDOS_CSS


def test_leer_entregas_vacio():
    assert asyncio.run(nexus.leer_entregas(_Page(False))) == []


def test_marcar_y_desmarcar_entregada(seeded):
    st = seeded.storage
    st.marcar_entregada("100-1.1", "2026-09-20T22:24")
    t = st.get_tarea("100-1.1")
    assert t["estado"] == "entregada" and t["entregada_en"] == "2026-09-20T22:24"
    st.desmarcar_entregada("100-1.1")
    t = st.get_tarea("100-1.1")
    assert t["estado"] == "pendiente" and t["entregada_en"] is None
    st.set_generacion("100-1.1", "md", "a.docx", "a.pdf")
    st.marcar_entregada("100-1.1", None)
    st.desmarcar_entregada("100-1.1")
    assert st.get_tarea("100-1.1")["estado"] == "generada"


def test_migra_base_vieja_sin_entregada_en(tmp_path):
    ruta = tmp_path / "viejo.db"
    con = sqlite3.connect(ruta)
    con.executescript(
        "CREATE TABLE materias (id TEXT PRIMARY KEY, nombre TEXT NOT NULL, profesor TEXT, "
        "periodo TEXT, orden INTEGER NOT NULL DEFAULT 0, sincronizada_en TEXT);"
        "CREATE TABLE etapas (id TEXT PRIMARY KEY, materia_id TEXT NOT NULL, nombre TEXT NOT NULL, "
        "descripcion TEXT NOT NULL DEFAULT '', orden INTEGER NOT NULL DEFAULT 0);"
        "CREATE TABLE tareas (id TEXT PRIMARY KEY, etapa_id TEXT NOT NULL, "
        "materia_id TEXT NOT NULL, "
        "numero TEXT NOT NULL, titulo TEXT NOT NULL, tipo TEXT NOT NULL, desde TEXT, hasta TEXT, "
        "puntos REAL, modalidad TEXT, estado TEXT NOT NULL DEFAULT 'pendiente', "
        "orden INTEGER NOT NULL DEFAULT 0);"
    )
    con.commit()
    con.close()
    st = Storage(ruta)
    cols = {r[1] for r in st._db.execute("PRAGMA table_info(tareas)")}
    st.close()
    assert "entregada_en" in cols


AHORA = datetime(2026, 10, 15, 12, 0)


def test_vencida_solo_si_no_entregada_y_pasada():
    base = {"estado": "pendiente", "hasta": "2026-10-14T23:59"}
    assert services.con_vencida(base, AHORA)["vencida"] is True
    assert services.con_vencida({**base, "hasta": "2026-10-16T00:00"}, AHORA)["vencida"] is False
    assert services.con_vencida({**base, "estado": "entregada"}, AHORA)["vencida"] is False
    assert services.con_vencida({**base, "hasta": None}, AHORA)["vencida"] is False


def _tarea(st, numero, hasta, estado="pendiente"):
    tid = f"100-{numero}"
    st._run("UPDATE tareas SET hasta = ?, estado = ? WHERE id = ?", (hasta, estado, tid))


def test_proximas_ordenadas_con_vencidas_al_final(state, seeded):
    st = state.storage
    st.replace_estructura(
        "100",
        [
            EtapaItem(
                "E",
                "d",
                0,
                [TareaItem(f"1.{k}", f"T{k}", "evidencia", 1.0, None, k) for k in range(1, 6)],
            )
        ],
    )
    _tarea(st, "1.1", "2026-10-20T00:00")
    _tarea(st, "1.2", "2026-10-10T00:00")
    _tarea(st, "1.3", "2026-10-17T00:00")
    _tarea(st, "1.4", "2026-10-01T00:00", "entregada")
    _tarea(st, "1.5", None)
    todas = services.tareas_proximas(state, AHORA)
    assert [t["id"] for t in todas] == ["100-1.3", "100-1.1", "100-1.5", "100-1.2"]
    assert all(t["materia_nombre"] == "Lógica" for t in todas)
    assert "100-1.4" not in [t["id"] for t in todas]
    assert todas[-1]["id"] == "100-1.2" and todas[-1]["vencida"] is True


def test_api_proximas_revisar_y_etapas(app, state, seeded):
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.get("/tareas/proximas")
    assert r.status_code == 200 and r.json()[0]["materia_nombre"] == "Lógica"
    etapas = client.get("/materias/100/etapas").json()
    assert "vencida" in etapas[0]["tareas"][0] and "entregada_en" in etapas[0]["tareas"][0]
    assert client.post("/entregas/revisar").status_code == 400

    state.storage.set_settings({"cuenta": "1"})
    state.credentials.set("1", "pw")

    async def escenario():
        a = await client.arequest("POST", "/entregas/revisar")
        b = await client.arequest("POST", "/entregas/revisar")
        return a.json(), b.json()

    a, b = asyncio.run(escenario())
    assert a["id"] == b["id"] and a["tipo"] == "revisar_entregas"


class _Pagina:
    url = "https://plataformanexus.uanl.mx/#/App"
    page = property(lambda self: self)

    def is_closed(self):
        return False

    async def close(self):
        return None

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


def _montar(monkeypatch, state, tareas=3):
    llamadas = []

    async def ensure(st, hooks, **kw):
        return _Pagina()

    async def pestana(st, hooks, lock, estado=None):
        return _Pagina()

    async def sin_estado(st):
        return None

    async def leer(page):
        return [MateriaCard("100", "Lógica", 0)]

    async def abrir_materia(page, i, nombre=None):
        return Portada("PROFE", "p", None)

    async def abrir_estructura(page):
        return [
            EtapaItem(
                "E",
                "d",
                0,
                [TareaItem(f"1.{k}", f"T{k}", "evidencia", 1.0, None, k) for k in range(tareas)],
            )
        ]

    async def nada(page):
        return None

    monkeypatch.setattr(services, "ensure_nexus", ensure)
    monkeypatch.setattr(services, "_abrir_pestana", pestana)
    monkeypatch.setattr(services, "_exportar_sesion", sin_estado)
    monkeypatch.setattr(nexus, "leer_materias", leer)
    monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
    monkeypatch.setattr(nexus, "abrir_estructura", abrir_estructura)
    monkeypatch.setattr(nexus, "volver_a_estructura", nada)
    monkeypatch.setattr(nexus, "volver_a_lista", nada)
    return llamadas


def _correr(state, factory):
    async def escenario():
        job = factory()
        for _ in range(300):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    async def main():
        return await escenario()

    return asyncio.run(main())


def _detalle(entregas=None):
    return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None, entregas)


def test_sync_completo_revisa_entregas_e_incremental_no(state, monkeypatch):
    llamadas = _montar(monkeypatch, state)

    async def abrir_tarea(page, e, t, numero=None, *, entregas=False, solo_entregas=False):
        llamadas.append((t, entregas, solo_entregas))
        if not entregas:
            return _detalle(None)
        return _detalle([Entrega("a.pdf", "2026-09-20T22:24")] if t == 0 else [])

    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)

    async def lanzar(modo):
        return state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, modo))

    def sync(modo):
        async def escenario():
            job = await lanzar(modo)
            for _ in range(300):
                if job.estado in ("ok", "error"):
                    break
                await asyncio.sleep(0.02)
            return job

        return asyncio.run(escenario())

    job = sync("completo")
    assert job.estado == "ok", job.mensaje
    assert all(c[1] for c in llamadas) and len(llamadas) == 3
    t0 = state.storage.get_tarea("100-1.0")
    assert t0["estado"] == "entregada" and t0["entregada_en"] == "2026-09-20T22:24"
    assert state.storage.get_tarea("100-1.1")["estado"] == "pendiente"

    llamadas.clear()
    job = sync("completo")
    assert job.estado == "ok"
    assert sorted(c[0] for c in llamadas) == [1, 2]

    llamadas.clear()
    state.storage._run("DELETE FROM detalle WHERE tarea_id = ?", ("100-1.1",))
    job = sync("incremental")
    assert job.estado == "ok"
    assert llamadas == [(1, False, False)]


def test_revisar_entregas_todas_las_no_entregadas(state, monkeypatch):
    llamadas = _montar(monkeypatch, state)
    state.storage.upsert_materia("100", "Lógica", 0)

    async def abrir_tarea(page, e, t, numero=None, *, entregas=False, solo_entregas=False):
        llamadas.append((t, solo_entregas))
        return _detalle([Entrega("a.pdf", "2026-09-21T08:00")] if t == 1 else [])

    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)

    def revisar():
        async def escenario():
            job = state.jobs.start(
                "revisar_entregas", lambda ctx: services.run_revisar_entregas(state, ctx)
            )
            for _ in range(300):
                if job.estado in ("ok", "error"):
                    break
                await asyncio.sleep(0.02)
            return job

        return asyncio.run(escenario())

    job = revisar()
    assert job.estado == "ok", job.mensaje
    assert job.resultado == {"revisadas": 3, "entregadas": 1, "pendientes": 2, "errores": []}
    assert all(s for _, s in llamadas)
    assert state.storage.get_tarea("100-1.1")["estado"] == "entregada"

    llamadas.clear()
    job = revisar()
    assert sorted(t for t, _ in llamadas) == [0, 2]
    assert job.resultado["revisadas"] == 2 and job.resultado["entregadas"] == 0
