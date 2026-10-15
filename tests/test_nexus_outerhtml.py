import asyncio
import re
from pathlib import Path

from backend import services
from backend.core import nexus
from backend.core import selectors as S

from . import fixtures


def _interior(full: str) -> str:
    return re.sub(r"^<[^>]*>|</[^>]*>$", "", full.strip(), flags=re.S)


class _Loc:
    def __init__(self, full: str):
        self.full = full

    def nth(self, i):
        return self

    @property
    def first(self):
        return self

    def locator(self, *a, **kw):
        return self

    def filter(self, **kw):
        return self

    async def click(self, **kw):
        return None

    async def all_inner_texts(self):
        return ["Texto"]

    async def inner_text(self):
        return "Texto"

    async def count(self):
        return 1

    async def wait_for(self, **kw):
        return None

    async def inner_html(self):
        return _interior(self.full)

    async def evaluate(self, script):
        assert "outerHTML" in script
        return self.full


class _Page:
    def __init__(self, htmls):
        self.htmls = htmls

    def locator(self, sel):
        return _Loc(self.htmls.get(sel, ""))

    async def wait_for_selector(self, *a, **kw):
        return None


def _sin_pausa(monkeypatch):
    async def nada(*a, **kw):
        return None

    from backend.core import browser

    monkeypatch.setattr(browser, "pausa", nada)


def test_leer_materias_con_page_que_separa_inner_y_outer():
    page = _Page({S.NX_CARDS_ROOT: fixtures.cards_html()})
    materias = asyncio.run(nexus.leer_materias(page))
    assert len(materias) == 10


def test_inner_html_solo_no_alcanza():
    interior = _interior(fixtures.cards_html())
    assert nexus.parse_materias(interior) == []


def test_abrir_materia_lee_portada(monkeypatch):
    _sin_pausa(monkeypatch)
    page = _Page({S.NX_CARD: "<x/>", S.NX_PORTADA: fixtures.portada_html(), S.NX_CARDS_ROOT: ""})
    portada = asyncio.run(nexus.abrir_materia(page, 0))
    assert portada.profesor == "CAVAZOS MARTÍNEZ RAFAEL ALFREDO"


def test_abrir_estructura_lee_etapas(monkeypatch):
    _sin_pausa(monkeypatch)
    page = _Page({S.NX_ESTRUCTURA: fixtures.estructura_html()})
    etapas = asyncio.run(nexus.abrir_estructura(page))
    assert len(etapas) == 5


class _Cuenta:
    def __init__(self, sel=""):
        self.sel = sel

    async def count(self):
        return 0 if self.sel == "text=/sesi[oó]n.{0,20}(cerrada|expir)/i" else 1


class _PaginaSync:
    def locator(self, sel):
        return _Cuenta(sel)

    def __init__(self):
        self.url = "https://plataformanexus.uanl.mx/"
        self.shots = []

    def is_closed(self):
        return False

    async def content(self):
        return "<html>vacio</html>"

    async def screenshot(self, path, **kw):
        self.shots.append(path)
        Path(path).write_bytes(b"png")


def test_sync_sin_materias_es_error_y_guarda_snapshot(state, monkeypatch):
    pagina = _PaginaSync()

    async def fake_ensure(st, hooks, **kw):
        return pagina

    async def fake_leer(page):
        return []

    monkeypatch.setattr(services, "ensure_nexus", fake_ensure)
    monkeypatch.setattr(nexus, "leer_materias", fake_leer)

    async def scenario():
        job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx))
        for _ in range(200):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    job = asyncio.run(scenario())
    assert job.estado == "error"
    assert job.mensaje == "No se encontraron materias en NEXUS"
    archivos = {f.suffix for f in state.paths.debug.iterdir()}
    assert archivos == {".html", ".png"}
