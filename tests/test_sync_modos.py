import asyncio

import pytest

from backend import services
from backend.core import browser as browser_mod
from backend.core import nexus
from backend.core.browser import BrowserManager
from backend.core.types import (
    DetalleTarea,
    EtapaItem,
    MateriaCard,
    Portada,
    TareaItem,
)

from .asgi_client import MiniClient


class _Pagina:
    url = "https://plataformanexus.uanl.mx/#/App"

    def is_closed(self):
        return False

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


class FakeNexus:
    def __init__(self, monkeypatch, state, tareas_por_materia=2):
        self.detalles = []
        self.etapas = {
            0: [
                EtapaItem(
                    "E1",
                    "d",
                    0,
                    [
                        TareaItem(f"1.{k}", f"Tarea {k}", "evidencia", 1.0, None, k)
                        for k in range(tareas_por_materia)
                    ],
                )
            ]
        }
        self.titulo_extra = ""
        self.headless = []
        self.estructuras = 0

        async def ensure(st, hooks, **kw):
            self.headless.append(kw.get("headless"))
            return _Pagina()

        async def leer(page):
            return [MateriaCard("100", "Lógica", 0)]

        async def abrir_materia(page, i):
            return Portada("PROFE", "periodo", None)

        async def abrir_estructura(page):
            self.estructuras += 1
            etapas = self.etapas[0]
            for e in etapas:
                for t in e.tareas:
                    t.titulo = t.titulo.split(" *")[0] + self.titulo_extra
            return etapas

        async def abrir_tarea(page, e, t):
            self.detalles.append((e, t))
            return DetalleTarea("T", "1", None, None, 1.0, None, "act", "cont", "crit", None)

        async def nada(page):
            return None

        monkeypatch.setattr(services, "ensure_nexus", ensure)
        monkeypatch.setattr(nexus, "leer_materias", leer)
        monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
        monkeypatch.setattr(nexus, "abrir_estructura", abrir_estructura)
        monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
        monkeypatch.setattr(nexus, "volver_a_estructura", nada)
        monkeypatch.setattr(nexus, "volver_a_lista", nada)


def correr(state, modo="auto"):
    async def scenario():
        job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, modo))
        for _ in range(300):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    return asyncio.run(scenario())


def test_auto_elige_completo_y_luego_incremental(state, monkeypatch):
    fake = FakeNexus(monkeypatch, state)
    job = correr(state)
    assert job.estado == "ok"
    assert job.resultado["detalles_leidos"] == 2 and job.resultado["nuevas"] == 2
    settings = state.storage.get_settings()
    assert settings["sync_inicial_hecha"] is True and settings["ultima_sync"]
    assert set(fake.headless) == {True}

    fake.detalles.clear()
    job = correr(state)
    assert job.estado == "ok"
    assert job.resultado["detalles_leidos"] == 0 and fake.detalles == []


def test_incremental_solo_pide_detalle_de_nuevas(state, monkeypatch):
    fake = FakeNexus(monkeypatch, state, tareas_por_materia=1)
    assert correr(state, "completo").estado == "ok"
    fake.etapas[0][0].tareas.append(TareaItem("1.9", "Nueva", "evidencia", 1.0, None, 1))
    fake.detalles.clear()
    job = correr(state, "incremental")
    assert job.estado == "ok"
    assert fake.detalles == [(0, 1)]
    assert job.resultado["nuevas"] == 1 and job.resultado["tareas"] == 2


def test_incremental_trae_las_que_no_tienen_detalle(state, monkeypatch):
    fake = FakeNexus(monkeypatch, state)
    assert correr(state, "incremental").estado == "ok"
    assert len(fake.detalles) == 2


def test_idempotente_y_actualiza_titulos(state, monkeypatch):
    fake = FakeNexus(monkeypatch, state)
    assert correr(state, "completo").estado == "ok"
    assert correr(state, "completo").estado == "ok"
    etapas = state.storage.list_etapas("100")
    assert len(etapas) == 1 and len(etapas[0]["tareas"]) == 2
    fake.titulo_extra = " v2"
    assert correr(state, "completo").estado == "ok"
    titulos = [t["titulo"] for t in state.storage.list_etapas("100")[0]["tareas"]]
    assert all(t.endswith("v2") for t in titulos) and len(titulos) == 2
    assert len(state.storage.list_materias()) == 1


def test_error_en_una_tarea_continua(state, monkeypatch):
    fake = FakeNexus(monkeypatch, state)

    async def abrir_tarea(page, e, t):
        if t == 0:
            raise TimeoutError("boom")
        fake.detalles.append((e, t))
        return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None)

    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    job = correr(state, "completo")
    assert job.estado == "ok"
    assert job.resultado["detalles_leidos"] == 1 and len(job.resultado["errores"]) == 1


def test_sesion_caida_reintenta_con_login(state, monkeypatch):
    fake = FakeNexus(monkeypatch, state, tareas_por_materia=1)
    estado = {"logins": 0, "intentos": 0}

    class Caida(_Pagina):
        url = "https://plataformanexus.uanl.mx/#/LoginSIASE"

    async def ensure(st, hooks, **kw):
        estado["logins"] += 1
        st.nexus_page = Caida() if estado["logins"] == 1 else _Pagina()
        return st.nexus_page

    async def abrir_tarea(page, e, t):
        estado["intentos"] += 1
        if estado["intentos"] == 1:
            raise TimeoutError("sesion")
        return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None)

    monkeypatch.setattr(services, "ensure_nexus", ensure)
    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    job = correr(state, "completo")
    assert job.estado == "ok", job.mensaje
    assert job.resultado["detalles_leidos"] == 1 and job.resultado["errores"] == []
    assert estado["logins"] == 2 and estado["intentos"] == 2
    assert fake.estructuras == 2


def test_sync_concurrente_devuelve_el_mismo_job(app, state, monkeypatch):
    FakeNexus(monkeypatch, state)
    state.storage.set_settings({"cuenta": "1"})
    state.credentials.set("1", "pw")
    client = MiniClient(app, headers={"X-Token": "dev"})

    async def scenario():
        a = await client.arequest("POST", "/sync")
        b = await client.arequest("POST", "/sync", json={"modo": "completo"})
        return a.json(), b.json()

    a, b = asyncio.run(scenario())
    assert a["id"] == b["id"] and a["tipo"] == "sync"


def test_sync_modo_invalido(client):
    assert client.post("/sync", json={"modo": "raro"}).status_code == 422


class _FakeCtx:
    def __init__(self, headless):
        self.headless = headless
        self.cerrado = False
        self.handlers = []

    def on(self, evento, fn):
        self.handlers.append(fn)

    async def close(self):
        self.cerrado = True


class _FakePw:
    def __init__(self):
        self.lanzados = []
        self.chromium = self

    async def launch_persistent_context(self, **kw):
        ctx = _FakeCtx(kw["headless"])
        ctx.kw = kw
        self.lanzados.append(ctx)
        return ctx


@pytest.fixture
def manager(tmp_path, monkeypatch):
    mgr = BrowserManager(tmp_path / "perfil", dev=True)
    mgr._pw = _FakePw()
    return mgr


def test_browser_relanza_solo_si_cambia_el_modo(manager):
    async def scenario():
        a = await manager.context(headless=True)
        b = await manager.context(headless=True)
        c = await manager.context()
        d = await manager.context()
        e = await manager.context(headless=True)
        return a, b, c, d, e

    a, b, c, d, e = asyncio.run(scenario())
    assert a is b and c is d
    assert a is not c and a.cerrado and c.cerrado
    assert [x.headless for x in manager._pw.lanzados] == [True, False, True]
    assert e is manager._pw.lanzados[-1]


def test_browser_sin_dev_es_headless_por_defecto(tmp_path):
    mgr = BrowserManager(tmp_path / "p", dev=False)
    mgr._pw = _FakePw()
    asyncio.run(mgr.context())
    assert mgr._pw.lanzados[0].headless is True
    assert browser_mod


def test_viewport_fijo_igual_en_ambos_modos(manager):
    async def scenario():
        await manager.context(headless=True)
        await manager.context(headless=False)

    asyncio.run(scenario())
    kws = [c.kw for c in manager._pw.lanzados]
    assert kws[0]["viewport"] == kws[1]["viewport"] == {"width": 1366, "height": 900}
    assert "no_viewport" not in kws[0]
