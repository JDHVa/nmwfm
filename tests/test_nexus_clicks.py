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
        if sel == S.NX_PORTADA and not self.portada_tras_clic and self.intentos == 0:
            self.intentos += 1
            raise TimeoutError("sin portada")


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


def test_abrir_materia_dispara_click_si_no_aparece_la_portada(monkeypatch):
    _sin_pausa(monkeypatch)
    page = _Page(portada_tras_clic=False)
    asyncio.run(nexus.abrir_materia(page, 0))
    assert page.eventos.count(("dispatch", S.NX_CARD_CLICK, "click")) >= 2


class _PaginaSync:
    url = "https://plataformanexus.uanl.mx/"

    def is_closed(self):
        return False

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


def _sync(state, monkeypatch, fallan):
    from backend.core.types import MateriaCard, Portada

    async def fake_ensure(st, hooks):
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

    monkeypatch.setattr(services, "ensure_nexus", fake_ensure)
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
    assert job.estado == "ok"
    assert job.resultado["materias"] == 1
    assert len(job.resultado["errores"]) == 1 and job.resultado["errores"][0].startswith("Uno")


def test_sync_error_si_fallan_todas(state, monkeypatch):
    job = _sync(state, monkeypatch, {0, 1})
    assert job.estado == "error"
