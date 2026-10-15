import asyncio

from backend.core import nexus

from . import fixtures


def test_dialogo_pestana_pc_con_input_file():
    d = nexus.parse_dialogo_entrega(fixtures.entregar_html())
    assert d.pestanas == ["PC", "OneDrive", "Recurso Externo"]
    assert d.activa == "PC"
    assert d.tiene_input_file
    assert d.tiene_dropzone


def test_snackbar_exito():
    snack = nexus.parse_snackbar(fixtures.SNACKBAR_EXITO)
    assert snack.exito
    assert snack.texto == "La Tarea ha sido cargada y entregada con éxito"


def test_snackbar_exito_sin_acentos_ni_mayusculas():
    html = fixtures.SNACKBAR_EXITO.replace("entregada con éxito", "ENTREGADA CON EXITO")
    assert nexus.parse_snackbar(html).exito


def test_snackbar_sin_clase_de_exito_es_error():
    html = fixtures.SNACKBAR_EXITO.replace(" snackbar-success", " snackbar-error").replace(
        "La Tarea ha sido cargada y entregada con éxito", "Archivo demasiado grande"
    )
    snack = nexus.parse_snackbar(html)
    assert not snack.exito
    assert snack.texto == "Archivo demasiado grande"


def test_snackbar_exito_con_otro_texto_no_cuenta():
    html = fixtures.SNACKBAR_EXITO.replace("entregada con éxito", "guardada")
    assert not nexus.parse_snackbar(html).exito


def test_sin_snackbar():
    assert nexus.parse_snackbar("<div></div>") is None


class _Loc:
    def __init__(self, page, sel):
        self.page, self.sel = page, sel

    @property
    def first(self):
        return self

    async def set_input_files(self, path):
        self.page.eventos.append(("input", path))

    async def click(self, **kw):
        self.page.eventos.append(("click", self.sel))


class _Chooser:
    def __init__(self, page):
        self.page = page

    async def set_files(self, path):
        self.page.eventos.append(("chooser", path))


class _Ctx:
    def __init__(self, page):
        self.page = page

    async def __aenter__(self):
        async def valor():
            return _Chooser(self.page)

        self.value = valor()
        return self

    async def __aexit__(self, *exc):
        return False


class _Page:
    def __init__(self, input_ok):
        self.input_ok = input_ok
        self.eventos = []

    async def wait_for_selector(self, sel, **kw):
        if not self.input_ok:
            raise TimeoutError("sin input")

    def locator(self, sel):
        return _Loc(self, sel)

    def expect_file_chooser(self):
        return _Ctx(self)


def test_subida_directa_al_input():
    page = _Page(True)
    asyncio.run(nexus._subir_archivo(page, "a.pdf"))
    assert page.eventos == [("input", "a.pdf")]


def test_subida_plan_b_con_file_chooser():
    page = _Page(False)
    asyncio.run(nexus._subir_archivo(page, "a.pdf"))
    assert page.eventos == [("click", "#dropZone"), ("chooser", "a.pdf")]
