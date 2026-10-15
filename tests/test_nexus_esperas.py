import asyncio

import pytest

from backend.core import nexus
from backend.core import selectors as S

from . import fixtures


class _Loc:
    def __init__(self, page, sel):
        self.page, self.sel = page, sel

    @property
    def first(self):
        return self

    def nth(self, i):
        return _Loc(self.page, self.sel + f"[{i}]")

    def locator(self, sel, **kw):
        return _Loc(self.page, sel)

    def filter(self, **kw):
        return self

    @property
    def last(self):
        return _Loc(self.page, self.sel + " >> last")

    async def count(self):
        if self.sel == "mat-sidenav-content":
            return 2
        if self.sel == S.NX_CONTENIDO_MATERIA:
            return 1
        return 3

    async def wait_for(self, **kw):
        return None

    async def click(self, **kw):
        self.page.clics.append(self.sel)
        if S.NX_PANEL_ITEM_LINK in self.sel:
            self.page.tras_clic = True
            self.page.sondeos = 0

    async def dispatch_event(self, nombre):
        await self.click()

    async def evaluate(self, script):
        if self.sel == "mat-sidenav-content":
            raise RuntimeError("strict mode violation: resolved to 2 elements")
        if "outerHTML" in script:
            return self.page.html()

    async def all_inner_texts(self):
        if self.sel == S.NX_DETALLE_ENCABEZADO:
            self.page.sondeos += 1
            return [self.page.encabezado()]
        if self.sel == S.NX_DETALLE_CARDS:
            return ["contenido" if self.page.sondeos > 0 else ""]
        return ["Texto"]


class _Page:
    def __init__(self, viejo_durante=3, numero_final="1.2"):
        self.clics = []
        self.tras_clic = False
        self.sondeos = 0
        self.viejo_durante = viejo_durante
        self.numero_final = numero_final

    def encabezado(self):
        if self.sondeos <= self.viejo_durante:
            return "9.9 - Tarea anterior"
        return f"{self.numero_final} - Dimensión 2"

    def html(self):
        return fixtures.detalle_html()

    def locator(self, sel):
        return _Loc(self, sel)

    async def wait_for_selector(self, *a, **kw):
        return None


def test_espera_el_detalle_nuevo_y_no_lee_el_viejo():
    page = _Page(viejo_durante=3)
    detalle = asyncio.run(nexus.abrir_tarea(page, 0, 1, "1.2"))
    assert detalle.numero == "1.2"
    assert page.sondeos > 3


def test_lectura_de_otra_tarea_reintenta_y_falla(monkeypatch):
    real = nexus.parse_detalle

    def otra(markup):
        detalle = real(markup)
        detalle.numero = "5.5"
        return detalle

    monkeypatch.setattr(nexus, "parse_detalle", otra)
    page = _Page(viejo_durante=0, numero_final="1.2")
    with pytest.raises(nexus.LecturaIncorrecta):
        asyncio.run(nexus.abrir_tarea(page, 0, 1, "1.2"))
    clics_tarea = [c for c in page.clics if S.NX_PANEL_ITEM_LINK in c]
    assert len(clics_tarea) == 2


def test_numero_coincide_exacto():
    assert nexus.numero_coincide("1.2 - Dimensión", "1.2")
    assert not nexus.numero_coincide("11.2 - X", "1.2")
    assert not nexus.numero_coincide("1.2.1 - X", "1.2")
    assert nexus.numero_coincide("PIA - Proyecto", "PIA")


def test_detalle_cargado_requiere_numero_y_tarjeta_con_texto():
    assert not nexus.detalle_cargado(["1.1 - A"], ["x"], "1.2")
    assert not nexus.detalle_cargado(["1.2 - A"], ["  "], "1.2")
    assert nexus.detalle_cargado(["1.2 - A"], ["x"], "1.2")
    assert nexus.detalle_cargado([], ["x"], None)


def test_rubrica_espera_criterios_y_pestana_contenidos(monkeypatch):
    estado = {"criterios": 0, "activa": 0}

    class Loc(_Loc):
        async def count(self):
            if self.sel == S.NX_RUBRICA_CRITERIO:
                estado["criterios"] += 1
                return 0 if estado["criterios"] < 3 else 4
            return 1

        async def all_inner_texts(self):
            if self.sel == S.NX_TAB_ACTIVA:
                estado["activa"] += 1
                return ["Rúbrica"] if estado["activa"] < 3 else ["Contenidos"]
            return ["Texto"]

        async def evaluate(self, script):
            return fixtures.rubrica_html()

    class Page(_Page):
        def locator(self, sel):
            return Loc(self, sel)

    rubrica = asyncio.run(nexus._leer_rubrica_pestana(Page()))
    assert rubrica is not None
    assert estado["criterios"] >= 3 and estado["activa"] >= 3


def test_html_ambiguo_usa_el_ultimo_en_vez_de_fallar(caplog):
    page = _Page()
    html = asyncio.run(nexus._html(page.locator("mat-sidenav-content")))
    assert html == page.html()
    assert "resolvio a 2 elementos" in caplog.text


def test_parse_detalle_con_dos_mat_sidenav_content():
    interior = f'<mat-sidenav-content class="p-3">{fixtures.detalle_html()}</mat-sidenav-content>'
    pagina = (
        f'<mat-sidenav-content class="app"><app-curso>{interior}</app-curso></mat-sidenav-content>'
    )
    for markup in (pagina, interior):
        detalle = nexus.parse_detalle(markup)
        assert detalle.numero == "1.2" and detalle.actividades
