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

ENSURE_REAL = services.ensure_nexus


class _Contador:
    def __init__(self, sel=""):
        self.sel = sel

    async def count(self):
        return 0 if self.sel == "text=/sesi[oó]n.{0,20}(cerrada|expir)/i" else 1


class _Pagina:
    url = "https://plataformanexus.uanl.mx/#/App"

    def is_closed(self):
        return False

    def on(self, evento, manejador):
        return None

    def locator(self, sel):
        return _Contador(sel)

    async def close(self):
        return None

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
        self.materias = [MateriaCard("100", "Lógica", 0)]
        self.pagina = _Pagina()
        self.headless = []
        self.estructuras = 0

        async def ensure(st, hooks, **kw):
            self.headless.append(kw.get("headless"))
            return self.pagina

        async def leer(page):
            return self.materias

        async def abrir_materia(page, i, nombre=None):
            await asyncio.sleep(0.05)
            return Portada("PROFE", "periodo", None)

        async def abrir_estructura(page):
            self.estructuras += 1
            etapas = self.etapas[0]
            for e in etapas:
                for t in e.tareas:
                    t.titulo = t.titulo.split(" *")[0] + self.titulo_extra
            return etapas

        async def abrir_tarea(page, e, t, numero=None, **kw):
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

    async def abrir_tarea(page, e, t, numero=None, **kw):
        if t == 0:
            raise TimeoutError("boom")
        fake.detalles.append((e, t))
        return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None)

    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    job = correr(state, "completo")
    assert job.estado == "ok"
    assert job.resultado["detalles_leidos"] == 1 and len(job.resultado["errores"]) == 1


def test_persistencia_incremental_y_reanudacion(state, monkeypatch):
    FakeNexus(monkeypatch, state, tareas_por_materia=4)
    leidas = []

    async def abrir_tarea(page, e, t, numero=None, **kw):
        if len(leidas) == 2:
            await asyncio.sleep(30)
        leidas.append(t)
        return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None)

    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)

    async def cortar():
        job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, "auto"))
        for _ in range(300):
            if len(leidas) == 2:
                break
            await asyncio.sleep(0.02)
        await state.jobs.shutdown()
        return job

    asyncio.run(cortar())
    guardadas = [f for f in state.storage.tareas_con_posicion("100") if f["tiene_detalle"]]
    assert len(guardadas) == 2
    assert state.storage.get_settings()["sync_inicial_hecha"] is False

    leidas.clear()

    async def normal(page, e, t, numero=None, **kw):
        leidas.append(t)
        return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None)

    monkeypatch.setattr(nexus, "abrir_tarea", normal)
    job = correr(state, "auto")
    assert job.estado == "ok"
    assert sorted(leidas) == [2, 3]
    assert state.storage.get_settings()["sync_inicial_hecha"] is True


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
        self.rutas = []
        self.timeouts = []

    async def route(self, patron, handler):
        self.rutas.append((patron, handler))

    def set_default_timeout(self, ms):
        self.timeouts.append(ms)

    def set_default_navigation_timeout(self, ms):
        self.timeouts.append(ms)

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


class _Frame:
    def __init__(self, url):
        self.url = url


class _Req:
    def __init__(self, tipo, url_pagina):
        self.resource_type = tipo
        self.frame = _Frame(url_pagina)


class _Route:
    def __init__(self, tipo, url_pagina):
        self.request = _Req(tipo, url_pagina)
        self.accion = None

    async def abort(self):
        self.accion = "abort"

    async def continue_(self):
        self.accion = "continue"


def test_route_bloquea_recursos_pesados_solo_fuera_de_gemini(manager):
    asyncio.run(manager.context(headless=True))
    ctx = manager._pw.lanzados[0]
    assert ctx.rutas and ctx.timeouts[0] == 10_000
    handler = ctx.rutas[0][1]

    async def accion(tipo, url):
        r = _Route(tipo, url)
        await handler(r)
        return r.accion

    nexus_url = "https://plataformanexus.uanl.mx/#/App"
    gemini_url = "https://gemini.google.com/app"

    async def todo():
        return [
            await accion("image", nexus_url),
            await accion("font", nexus_url),
            await accion("media", nexus_url),
            await accion("script", nexus_url),
            await accion("document", nexus_url),
            await accion("image", gemini_url),
            await accion("font", gemini_url),
        ]

    assert asyncio.run(todo()) == [
        "abort",
        "abort",
        "abort",
        "continue",
        "continue",
        "continue",
        "continue",
    ]


def test_tarea_fallida_guarda_snapshot(state, monkeypatch):
    FakeNexus(monkeypatch, state, tareas_por_materia=1)

    async def abrir_tarea(page, e, t, numero=None, **kw):
        raise TimeoutError("Timeout esperando el detalle de la tarea 1.0")

    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    job = correr(state, "completo")
    assert job.estado == "ok" and len(job.resultado["errores"]) == 1
    nombres = [f.name for f in state.paths.debug.iterdir()]
    assert any(n.startswith("sync-tarea-100-1_0") and n.endswith(".html") for n in nombres)


class _CtxNexus:
    def __init__(self):
        self.pages = []
        self.logins = 0
        self.max_vivas = 0

    def abrir(self):
        pagina = _PaginaNexus(self)
        self.pages.append(pagina)
        self.max_vivas = max(self.max_vivas, len(self.pages))
        return pagina


class _PaginaNexus(_Pagina):
    def __init__(self, ctx):
        self.ctx = ctx
        self.url = "https://plataformanexus.uanl.mx/#/App/UnidadesAprendizaje"
        self.cerrada = False

    def is_closed(self):
        return self.cerrada

    async def close(self):
        self.cerrada = True
        if self in self.ctx.pages:
            self.ctx.pages.remove(self)


def _real_ensure(state, monkeypatch, ctx):
    async def contexto(headless=None):
        return ctx

    async def login(c, cuenta, password, hooks=None):
        ctx.logins += 1
        return ctx.abrir()

    state.storage.set_settings({"cuenta": "1"})
    state.credentials.set("1", "pw")
    monkeypatch.setattr(services, "ensure_nexus", ENSURE_REAL)
    monkeypatch.setattr(state.browser, "context", contexto)
    monkeypatch.setattr(services.siase, "login", login)


def test_una_sola_pagina_de_nexus_reutilizada_entre_jobs(state, monkeypatch):
    ctx = _CtxNexus()
    fake = FakeNexus(monkeypatch, state, tareas_por_materia=1)
    _real_ensure(state, monkeypatch, ctx)
    _parchar_nexus(monkeypatch, fake)
    assert correr(state, "completo").estado == "ok"
    assert correr(state, "incremental").estado == "ok"
    assert ctx.logins == 1 and ctx.max_vivas == 1 and len(ctx.pages) == 1


def _parchar_nexus(monkeypatch, fake):
    async def leer(page):
        return fake.materias

    async def abrir_materia(page, i, nombre=None):
        return Portada("PROFE", "periodo", None)

    async def abrir_estructura(page):
        return fake.etapas[0]

    async def abrir_tarea(page, e, t, numero=None, **kw):
        fake.detalles.append((e, t))
        return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None)

    async def nada(page):
        return None

    monkeypatch.setattr(nexus, "leer_materias", leer)
    monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
    monkeypatch.setattr(nexus, "abrir_estructura", abrir_estructura)
    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    monkeypatch.setattr(nexus, "volver_a_estructura", nada)
    monkeypatch.setattr(nexus, "volver_a_lista", nada)


def test_pestana_muerta_cierra_la_vieja_reconecta_y_deja_snapshot(state, monkeypatch):
    ctx = _CtxNexus()
    fake = FakeNexus(monkeypatch, state, tareas_por_materia=1)
    _real_ensure(state, monkeypatch, ctx)
    _parchar_nexus(monkeypatch, fake)
    intentos = {"n": 0}

    async def abrir_tarea(page, e, t, numero=None, **kw):
        intentos["n"] += 1
        if intentos["n"] == 1:
            page.url = "https://plataformanexus.uanl.mx/#/LoginSIASE"
            raise TimeoutError("la sesion murio")
        return DetalleTarea("T", "1", None, None, 1.0, None, "a", "c", "k", None)

    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    job = correr(state, "completo")
    assert job.estado == "ok", job.mensaje
    assert job.resultado["detalles_leidos"] == 1 and job.resultado["errores"] == []
    assert ctx.logins == 2 and ctx.max_vivas == 1 and len(ctx.pages) == 1
    assert any(f.name.startswith("sesion-nexus-muerta") for f in state.paths.debug.iterdir())


def test_ensure_nexus_cierra_paginas_nexus_ajenas_antes_de_abrir_otra(state, monkeypatch):
    ctx = _CtxNexus()
    ajena = ctx.abrir()
    ajena.url = "https://plataformanexus.uanl.mx/#/LoginSIASE"
    _real_ensure(state, monkeypatch, ctx)
    state.nexus_page = ajena
    page = asyncio.run(services.ensure_nexus(state, services.Hooks(), headless=True))
    assert page is not ajena and ajena.cerrada
    assert ctx.pages == [page] and ctx.max_vivas == 1
