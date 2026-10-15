import asyncio

from backend.core import gemini
from backend.core.gemini import GeminiWeb


class _Editor:
    def __init__(self, fill_ok=True, pega_ok=True):
        self.fill_ok, self.pega_ok = fill_ok, pega_ok
        self.texto = ""
        self.eventos = []

    async def click(self):
        self.eventos.append("click")

    async def fill(self, texto):
        if not self.fill_ok:
            raise RuntimeError("no editable")
        self.texto = texto

    async def inner_text(self):
        return self.texto

    async def press_sequentially(self, texto, delay=0):
        self.eventos.append("tecleo")
        self.texto += texto


class _Teclado:
    def __init__(self, editor):
        self.editor = editor

    async def press(self, tecla):
        self.editor.eventos.append(tecla)
        if tecla == "Control+V" and self.editor.pega_ok:
            self.editor.texto = "pegado"


class _Page:
    def __init__(self, editor):
        self.keyboard = _Teclado(editor)

    async def evaluate(self, script, arg=None):
        return None


def _pegar(editor):
    web = GeminiWeb(browser=None)
    asyncio.run(web._pegar_prompt(_Page(editor), editor, "hola\nmundo"))
    return editor


def test_prompt_de_golpe_con_fill():
    editor = _pegar(_Editor())
    assert editor.texto == "hola\nmundo" and "tecleo" not in editor.eventos


def test_respaldo_clipboard():
    editor = _pegar(_Editor(fill_ok=False))
    assert editor.texto == "pegado" and "Control+V" in editor.eventos


def test_ultimo_respaldo_tecleo(monkeypatch):
    async def teclear(page, target, texto):
        target.texto = texto
        target.eventos.append("tecleo")

    monkeypatch.setattr(gemini, "escribir_humano", teclear)
    editor = _pegar(_Editor(fill_ok=False, pega_ok=False))
    assert "tecleo" in editor.eventos
