import asyncio
import json
from urllib.parse import quote

from backend import services
from backend.asistente import herramientas as h
from backend.core import gemini
from backend.core.gemini import GeminiWeb
from backend.core.prompt_builder import PromptData, build_prompt
from backend.core.types import DetalleTarea
from tests.asgi_client import MiniClient

IDS = [
    "rubrica_maxima",
    "cubrir_contenido",
    "tono_preparatoria",
    "no_mencionar_rubrica",
    "referencias_apa7",
]
TID = "100-1.1"


def _prompt(**kw):
    return build_prompt(PromptData(materia="Lógica", titulo="Tarea", **kw))


def test_defaults_de_sistema(client):
    s = client.get("/settings").json()
    assert [i["id"] for i in s["instrucciones_fijas"]] == IDS
    assert all(i["activa"] and i["sistema"] for i in s["instrucciones_fijas"])
    assert s["gemini_espera_envio_s"] == 3


def test_prompt_incluye_fijas_y_apa():
    p = _prompt()
    assert "APA 7" in p and "nivel máximo" in p and "Responde SOLO en Markdown" in p


def test_desactivar_apa_quita_la_linea(client):
    fijas = client.get("/settings").json()["instrucciones_fijas"]
    for i in fijas:
        if i["id"] == "referencias_apa7":
            i["activa"] = False
    r = client.put("/settings", json={"instrucciones_fijas": fijas})
    assert r.status_code == 200
    guardadas = client.get("/settings").json()["instrucciones_fijas"]
    assert "APA 7" not in _prompt(instrucciones_fijas=guardadas)


def test_override_por_generacion_y_orden_y_custom():
    fijas = [
        {"id": "u-1", "texto": "Mi regla", "activa": True, "sistema": False},
        {"id": "referencias_apa7", "texto": "Usa APA 7.", "activa": True, "sistema": True},
    ]
    p = _prompt(instrucciones_fijas=fijas)
    assert p.index("Mi regla") < p.index("Usa APA 7.")
    sin_apa = _prompt(instrucciones_fijas=fijas, instrucciones={"referencias_apa7": False})
    assert "APA 7" not in sin_apa
    sin_rubrica = _prompt(instrucciones={"rubrica_maxima": False})
    assert "APA 7" in sin_rubrica and "nivel máximo" not in sin_rubrica


def test_validacion_y_reagregado(client):
    malo = [{"id": "a", "texto": "  ", "activa": True}]
    assert client.put("/settings", json={"instrucciones_fijas": malo}).status_code == 422
    dup = [{"id": "a", "texto": "x", "activa": True}, {"id": "a", "texto": "y", "activa": True}]
    assert client.put("/settings", json={"instrucciones_fijas": dup}).status_code == 422
    assert client.put("/settings", json={"instrucciones_fijas": "x"}).status_code == 422
    assert client.put("/settings", json={"gemini_espera_envio_s": 16}).status_code == 422
    assert client.put("/settings", json={"gemini_espera_envio_s": True}).status_code == 422
    r = client.put(
        "/settings",
        json={
            "instrucciones_fijas": [{"id": "u-9", "texto": "Hola", "activa": True}],
            "gemini_espera_envio_s": 0,
        },
    )
    s = r.json()
    assert s["gemini_espera_envio_s"] == 0
    assert [i["id"] for i in s["instrucciones_fijas"]] == ["u-9", *IDS]
    assert s["instrucciones_fijas"][0]["sistema"] is False
    assert not any(i["activa"] for i in s["instrucciones_fijas"][1:])


def test_prompt_preview(app, seeded):
    seeded.storage.set_detalle(
        TID, DetalleTarea("T", "1.1", None, None, None, None, "Haz algo", "Cont", "Crit", None)
    )
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert "APA 7" in client.get(f"/prompt-preview/{TID}").json()["prompt"]
    q = client.get(
        f"/prompt-preview/{TID}?instrucciones=" + quote(json.dumps({"referencias_apa7": False}))
    )
    assert "APA 7" not in q.json()["prompt"]
    assert client.get(f"/prompt-preview/{TID}?instrucciones=%7B").status_code == 422


def test_generar_pasa_overrides(app, seeded, monkeypatch):
    recibido = {}

    async def falso(state, ctx, tarea_id, extra, portada=None, instrucciones=None):
        recibido["i"] = instrucciones
        return {}

    monkeypatch.setattr(services, "run_generar", falso)
    client = MiniClient(app, headers={"X-Token": "dev"})

    async def escenario():
        r = await client.arequest(
            "POST", f"/tareas/{TID}/generar", json={"instrucciones": {"referencias_apa7": False}}
        )
        await asyncio.sleep(0.1)
        return r

    assert asyncio.run(escenario()).status_code == 200
    assert recibido["i"] == {"referencias_apa7": False}


def test_herramienta_sin_referencias(seeded, monkeypatch):
    recibido = {}

    async def falso(state, ctx, tarea_id, extra=None, portada=None, instrucciones=None):
        recibido["i"] = instrucciones

    monkeypatch.setattr(services, "run_generar", falso)
    seeded.storage.set_settings({"cuenta": "c"})
    seeded.credentials.set("c", "p")

    async def escenario():
        await h.ejecutar(seeded, "generar_tarea", {"tarea_id": TID, "sin_referencias": True})
        await asyncio.sleep(0.05)

    asyncio.run(escenario())
    assert recibido["i"] == {"referencias_apa7": False}


class _Editor:
    @property
    def first(self):
        return self

    async def click(self):
        pass

    async def fill(self, t):
        self.t = t

    async def inner_text(self):
        return self.t


class _Boton:
    def __init__(self, eventos):
        self.eventos = eventos

    @property
    def first(self):
        return self

    async def wait_for(self, **kw):
        pass

    async def click(self):
        self.eventos.append("enviar")


class _Page:
    def __init__(self, eventos):
        self.eventos = eventos
        self.editor = _Editor()

    def locator(self, sel):
        return self.editor if sel == gemini.S.GM_EDITOR else _Boton(self.eventos)


def _enviar(espera):
    eventos = []

    async def dormir(s):
        eventos.append(("espera", s))

    real = gemini.asyncio.sleep
    gemini.asyncio.sleep = dormir
    try:
        asyncio.run(GeminiWeb(None, lambda: espera)._escribir_y_enviar(_Page(eventos), "hola"))
    finally:
        gemini.asyncio.sleep = real
    return eventos


def test_espera_antes_de_enviar():
    assert _enviar(7) == [("espera", 7), "enviar"]


def test_espera_cero_no_duerme():
    assert _enviar(0) == ["enviar"]


def test_espera_por_defecto_de_config():
    assert GeminiWeb(None).espera_envio_s() == 3
