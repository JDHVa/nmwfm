import asyncio

from backend.core import selectors as S
from backend.core import siase


class _Loc:
    def __init__(self, eventos):
        self.eventos = eventos

    first = property(lambda self: self)

    async def count(self):
        return 1

    async def hover(self, **kw):
        raise TimeoutError("el form SelCarrera intercepta el hover")

    async def wait_for(self, **kw):
        return None

    async def evaluate(self, script):
        return None

    async def click(self, **kw):
        self.eventos.append("click")

    async def dispatch_event(self, nombre):
        self.eventos.append(("dispatch", nombre))


class _Frame:
    def __init__(self, eventos, evaluate_falla=False):
        self.eventos = eventos
        self.evaluate_falla = evaluate_falla

    def locator(self, sel):
        return _Loc(self.eventos)

    async def evaluate(self, script):
        if self.evaluate_falla:
            raise RuntimeError("muestra no definido")
        self.eventos.append(("evaluate", script))


class _SpaPage:
    def __init__(self):
        self.esperado = None

    async def wait_for_selector(self, sel, **kw):
        self.esperado = sel

    async def wait_for_url(self, *a, **kw):
        raise AssertionError("la SPA solo cambia el hash; no hay evento load")

    async def wait_for_load_state(self, *a, **kw):
        raise AssertionError("la SPA solo cambia el hash; no hay evento load")


class _Page(_SpaPage):
    def __init__(self, frame):
        super().__init__()
        self.frames = [frame]

    async def goto(self, *a, **kw):
        return None


class _Expect:
    def __init__(self, nueva):
        self.nueva = nueva

    async def __aenter__(self):
        async def valor():
            return self.nueva

        self.value = valor()
        return self

    async def __aexit__(self, *exc):
        return False


class _Ctx:
    def __init__(self, frame):
        self.nueva = _SpaPage()
        self.frame = frame

    async def new_page(self):
        return _Page(self.frame)

    def expect_page(self):
        return _Expect(self.nueva)


def _correr(monkeypatch, evaluate_falla=False):
    async def sin_pausa(*a, **kw):
        return None

    monkeypatch.setattr(siase, "pausa", sin_pausa)
    monkeypatch.setattr(siase, "pausa_larga", sin_pausa)
    eventos = []
    ctx = _Ctx(_Frame(eventos, evaluate_falla))
    page = asyncio.run(siase.login(ctx, "c", "p"))
    return ctx, page, eventos


def test_login_espera_la_lista_de_materias_y_no_la_url(monkeypatch):
    ctx, page, _ = _correr(monkeypatch)
    assert page is ctx.nueva
    assert page.esperado == S.NX_CARD


def test_login_no_depende_del_hover_real(monkeypatch):
    _, _, eventos = _correr(monkeypatch)
    assert ("evaluate", S.SIASE_MOSTRAR_NEXUS_JS) in eventos
    assert "click" in eventos


def test_login_respaldo_mouseover_si_falla_el_handler(monkeypatch):
    _, _, eventos = _correr(monkeypatch, evaluate_falla=True)
    assert ("dispatch", "mouseover") in eventos
