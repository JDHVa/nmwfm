import asyncio

from backend.core import selectors as S
from backend.core import siase


class _Loc:
    first = property(lambda self: self)

    async def count(self):
        return 1

    async def hover(self):
        return None

    async def wait_for(self, **kw):
        return None

    async def click(self, **kw):
        return None


class _Frame:
    def locator(self, sel):
        return _Loc()


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
    frames = [_Frame()]

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
    def __init__(self):
        self.nueva = _SpaPage()

    async def new_page(self):
        return _Page()

    def expect_page(self):
        return _Expect(self.nueva)


def test_login_espera_la_lista_de_materias_y_no_la_url(monkeypatch):
    async def sin_pausa(*a, **kw):
        return None

    monkeypatch.setattr(siase, "pausa", sin_pausa)
    monkeypatch.setattr(siase, "pausa_larga", sin_pausa)
    ctx = _Ctx()
    page = asyncio.run(siase.login(ctx, "c", "p"))
    assert page is ctx.nueva
    assert page.esperado == S.NX_CARD
