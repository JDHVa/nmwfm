import asyncio

from backend import services
from backend.core import nexus
from backend.core import selectors as S

from . import fixtures


class _Loc:
    def __init__(self, page, sel, intercepta=False):
        self.page, self.sel, self.intercepta = page, sel, intercepta

    @property
    def first(self):
        return self

    def nth(self, i):
        return self

    def locator(self, sel, **kw):
        return _Loc(self.page, sel, self.intercepta or sel == S.NX_CARD_NAME)

    async def all_inner_texts(self):
        return ["Texto"]

    async def inner_text(self):
        if self.sel == S.NX_PORTADA and not self.page.portada_tras_clic:
            clics = [e for e in self.page.eventos if e[0] in ("click", "dispatch")]
            return "Texto" if len(clics) >= 2 else ""
        return "Texto"

    async def count(self):
        return 1

    async def wait_for(self, **kw):
        return None

    async def evaluate(self, script):
        if "outerHTML" in script:
            return fixtures.portada_html()
        self.page.eventos.append(("scroll", self.sel))

    async def click(self, **kw):
        if self.intercepta:
            raise TimeoutError("intercepta div.image-with-overlay")
        self.page.eventos.append(("click", self.sel))

    async def dispatch_event(self, nombre):
        self.page.eventos.append(("dispatch", self.sel, nombre))


class _Page:
    def __init__(self, portada_tras_clic=True):
        self.eventos = []
        self.portada_tras_clic = portada_tras_clic
        self.intentos = 0

    def locator(self, sel):
        return _Loc(self, sel)

    async def wait_for_selector(self, sel, **kw):
        return None


def _sin_pausa(monkeypatch):
    from backend.core import browser

    async def nada(*a, **kw):
        return None

    monkeypatch.setattr(browser, "pausa", nada)


def test_abrir_materia_usa_respaldo_si_el_clic_es_interceptado(monkeypatch):
    _sin_pausa(monkeypatch)
    page = _Page()
    portada = asyncio.run(nexus.abrir_materia(page, 0))
    assert portada.profesor == "CAVAZOS MARTÍNEZ RAFAEL ALFREDO"
    assert ("scroll", S.NX_CARD_NAME) in page.eventos
    assert ("dispatch", S.NX_CARD_CLICK, "click") in page.eventos


def test_abrir_materia_repite_el_clic_si_no_aparece_la_portada(monkeypatch):
    _sin_pausa(monkeypatch)
    esperar_real = nexus._esperar

    async def rapido(condicion, descripcion, timeout=20.0, intervalo=0.1):
        await esperar_real(condicion, descripcion, min(timeout, 0.3), 0.05)

    monkeypatch.setattr(nexus, "_esperar", rapido)
    page = _Page(portada_tras_clic=False)
    asyncio.run(nexus.abrir_materia(page, 0))
    assert page.eventos.count(("dispatch", S.NX_CARD_CLICK, "click")) >= 2


class _PaginaSync:
    url = "https://plataformanexus.uanl.mx/"

    def is_closed(self):
        return False

    async def close(self):
        return None

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


def _sync(state, monkeypatch, fallan):
    from backend.core.types import MateriaCard, Portada

    async def fake_ensure(st, hooks, **kw):
        return _PaginaSync()

    async def fake_leer(page):
        return [MateriaCard("1", "Uno", 0), MateriaCard("2", "Dos", 1)]

    async def fake_abrir(page, i):
        if i in fallan:
            raise TimeoutError("Timeout 30000ms\nlinea 2")
        return Portada("PROFE", "periodo", None)

    async def fake_estructura(page):
        return []

    async def fake_volver(page):
        return None

    async def fake_pestana(st, hooks, lock):
        return _PaginaSync()

    monkeypatch.setattr(services, "ensure_nexus", fake_ensure)
    monkeypatch.setattr(services, "_abrir_pestana", fake_pestana)
    monkeypatch.setattr(nexus, "leer_materias", fake_leer)
    monkeypatch.setattr(nexus, "abrir_materia", fake_abrir)
    monkeypatch.setattr(nexus, "abrir_estructura", fake_estructura)
    monkeypatch.setattr(nexus, "volver_a_lista", fake_volver)

    async def scenario():
        job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx))
        for _ in range(200):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    return asyncio.run(scenario())


def test_sync_continua_si_falla_una_materia(state, monkeypatch):
    job = _sync(state, monkeypatch, {0})
    assert job.estado == "ok", job.mensaje
    assert job.resultado["materias"] == 1
    assert len(job.resultado["errores"]) == 1 and job.resultado["errores"][0].startswith("Uno")


def test_sync_error_si_fallan_todas(state, monkeypatch):
    job = _sync(state, monkeypatch, {0, 1})
    assert job.estado == "error"
