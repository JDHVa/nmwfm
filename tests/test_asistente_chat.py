import asyncio
import json

import httpx
import pytest

from backend import services
from backend.asistente import chat
from backend.asistente.ollama import OllamaCliente, OllamaError, OllamaNoDisponible

from .asgi_client import MiniClient
from .test_herramientas_asistente import con_tareas  # noqa: F401


class FalsoOllama:
    def __init__(self, vueltas=None, instalados=None, error=None):
        self.vueltas = list(vueltas or [])
        self.instalados = instalados
        self.error = error
        self.llamadas = []

    async def chat(self, modelo, mensajes, herramientas=None):
        self.llamadas.append(
            {"modelo": modelo, "mensajes": [dict(m) for m in mensajes], "tools": herramientas}
        )
        if self.error:
            raise self.error
        for trozo in self.vueltas.pop(0):
            yield trozo

    async def etiquetas(self):
        if isinstance(self.instalados, Exception):
            raise self.instalados
        return self.instalados or []


def texto(contenido):
    return {"message": {"role": "assistant", "content": contenido}, "done": False}


def llamada(nombre, args):
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": nombre, "arguments": args}}],
        },
        "done": True,
    }


def recolectar(state, mensajes, tarea_id=None):
    async def escenario():
        return [e async for e in chat.conversar(state, mensajes, tarea_id)]

    return asyncio.run(escenario())


USUARIO = [{"rol": "user", "contenido": "¿Qué tareas tengo de lógica?"}]


def test_bucle_tool_call_resultado_y_respuesta_final(con_tareas):  # noqa: F811
    falso = FalsoOllama(
        [
            [llamada("buscar_tareas", {"materia": "logica", "estado": "pendiente"})],
            [texto("Tienes "), texto("2 tareas pendientes.")],
        ]
    )
    con_tareas.ollama = falso
    eventos = recolectar(con_tareas, USUARIO)
    tipos = [e["type"] for e in eventos]
    assert tipos == ["tool_call", "tool_result", "token", "token", "fin"]
    assert eventos[0]["nombre"] == "buscar_tareas" and eventos[0]["args"]["materia"] == "logica"
    resultado = eventos[1]["resultado"]
    assert {t["id"] for t in resultado} == {"100-1.1", "100-1.2", "100-1.3"}
    assert "".join(e["text"] for e in eventos if e["type"] == "token") == (
        "Tienes 2 tareas pendientes."
    )

    primera, segunda = falso.llamadas
    assert primera["modelo"] == "qwen3:4b" and len(primera["tools"]) == 11
    assert primera["mensajes"][0]["role"] == "system"
    assert "español" in primera["mensajes"][0]["content"]
    assert "2026" in primera["mensajes"][0]["content"]
    roles = [m["role"] for m in segunda["mensajes"]]
    assert roles == ["system", "user", "assistant", "tool"]
    assert segunda["mensajes"][2]["tool_calls"][0]["function"]["name"] == "buscar_tareas"
    assert segunda["mensajes"][3]["tool_name"] == "buscar_tareas"
    assert "100-1.1" in segunda["mensajes"][3]["content"]


def test_argumentos_como_texto_json_y_error_de_herramienta(con_tareas):  # noqa: F811
    falso = FalsoOllama(
        [[llamada("ver_tarea", '{"tarea_id": "no-existe"}')], [texto("No encontré esa tarea.")]]
    )
    con_tareas.ollama = falso
    eventos = recolectar(con_tareas, USUARIO)
    assert eventos[1]["type"] == "tool_result" and "error" in eventos[1]["resultado"]
    assert eventos[-1]["type"] == "fin"


def test_el_contexto_de_la_tarea_va_en_el_prompt_de_sistema(con_tareas):  # noqa: F811
    con_tareas.storage.set_indicaciones("100-1.1", "Entregar en hojas blancas")
    falso = FalsoOllama([[texto("ok")]])
    con_tareas.ollama = falso
    recolectar(con_tareas, USUARIO, "100-1.1")
    sistema = falso.llamadas[0]["mensajes"][0]["content"]
    assert "100-1.1" in sistema and "Entregar en hojas blancas" in sistema
    sin = FalsoOllama([[texto("ok")]])
    con_tareas.ollama = sin
    recolectar(con_tareas, USUARIO)
    assert "viendo esta tarea" not in sin.llamadas[0]["mensajes"][0]["content"]


def test_historial_con_resultados_de_herramientas_se_traduce(con_tareas):  # noqa: F811
    falso = FalsoOllama([[texto("listo")]])
    con_tareas.ollama = falso
    recolectar(
        con_tareas,
        [
            {"rol": "user", "contenido": "hola"},
            {"rol": "assistant", "contenido": "buscando"},
            {"rol": "tool", "contenido": '{"x": 1}', "herramienta": "buscar_tareas"},
            {"rol": "user", "contenido": "gracias"},
        ],
    )
    mensajes = falso.llamadas[0]["mensajes"]
    assert [m["role"] for m in mensajes] == ["system", "user", "assistant", "tool", "user"]
    assert mensajes[3]["tool_name"] == "buscar_tareas"


def test_maximo_seis_vueltas(con_tareas):  # noqa: F811
    falso = FalsoOllama([[llamada("proximas_entregas", {})] for _ in range(10)])
    con_tareas.ollama = falso
    eventos = recolectar(con_tareas, USUARIO)
    assert len(falso.llamadas) == chat.MAX_VUELTAS == 6
    assert eventos[-1]["type"] == "fin"
    assert any("demasiadas herramientas" in e.get("text", "") for e in eventos)


def test_entregar_pide_confirmacion_y_no_se_ejecuta(con_tareas, monkeypatch):  # noqa: F811
    lanzados = []

    async def entregar(state, ctx, tarea_id):
        lanzados.append(tarea_id)

    monkeypatch.setattr(services, "run_entregar", entregar)
    base = con_tareas.paths.generaciones
    con_tareas.storage.set_generacion("100-1.1", "md", str(base / "a.docx"), str(base / "a.pdf"))
    falso = FalsoOllama([[llamada("entregar_tarea", {"tarea_id": "100-1.1"})]])
    con_tareas.ollama = falso
    eventos = recolectar(con_tareas, [{"rol": "user", "contenido": "entrega la ficha"}])
    assert [e["type"] for e in eventos] == ["tool_call", "confirmar", "fin"]
    pedido = eventos[1]
    assert pedido["accion"] == "entregar_tarea" and pedido["args"] == {"tarea_id": "100-1.1"}
    assert lanzados == [] and len(falso.llamadas) == 1


def test_api_confirmar_acepta_cancela_y_no_reutiliza(app, con_tareas, monkeypatch):  # noqa: F811
    lanzados = []

    async def entregar(state, ctx, tarea_id):
        lanzados.append(tarea_id)

    monkeypatch.setattr(services, "run_entregar", entregar)
    base = con_tareas.paths.generaciones
    con_tareas.storage.set_generacion("100-1.1", "md", str(base / "a.docx"), str(base / "a.pdf"))
    client = MiniClient(app, headers={"X-Token": "dev"})

    def pedir():
        con_tareas.ollama = FalsoOllama([[llamada("entregar_tarea", {"tarea_id": "100-1.1"})]])
        r = client.post("/asistente/chat", json={"mensajes": USUARIO})
        eventos = [
            json.loads(ln[6:]) for ln in r.content.decode().splitlines() if ln.startswith("data: ")
        ]
        return next(e for e in eventos if e["type"] == "confirmar")["id"]

    cancelado = pedir()
    assert client.post("/asistente/confirmar", json={"id": cancelado, "aceptar": False}).json() == {
        "cancelado": True
    }
    assert lanzados == []

    aceptado = pedir()

    async def escenario():
        r = await client.arequest(
            "POST", "/asistente/confirmar", json={"id": aceptado, "aceptar": True}
        )
        await asyncio.sleep(0.05)
        return r

    r = asyncio.run(escenario())
    assert r.status_code == 200 and r.json()["tipo"] == "entregar" and lanzados == ["100-1.1"]
    repetido = client.post("/asistente/confirmar", json={"id": aceptado, "aceptar": True})
    assert repetido.status_code == 404
    assert (
        client.post("/asistente/confirmar", json={"id": "nada", "aceptar": True}).status_code == 404
    )


def test_api_chat_es_sse(app, con_tareas):  # noqa: F811
    con_tareas.ollama = FalsoOllama([[texto("Hola"), texto(" mundo")]])
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.post("/asistente/chat", json={"mensajes": USUARIO, "tarea_id": None})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    lineas = [ln for ln in r.content.decode().split("\n\n") if ln]
    assert all(ln.startswith("data: ") for ln in lineas)
    assert [json.loads(ln[6:])["type"] for ln in lineas] == ["token", "token", "fin"]
    assert (
        client.post(
            "/asistente/chat", json={"mensajes": [{"rol": "x", "contenido": ""}]}
        ).status_code
        == 422
    )


def test_ollama_apagado_da_error_claro(con_tareas):  # noqa: F811
    con_tareas.ollama = FalsoOllama(error=OllamaNoDisponible())
    eventos = recolectar(con_tareas, USUARIO)
    assert eventos == [{"type": "error", "message": "Ollama no está corriendo"}]


def test_estado_del_asistente(app, state):
    client = MiniClient(app, headers={"X-Token": "dev"})
    state.ollama = FalsoOllama(instalados=["qwen3:4b", "llama3.2:3b"])
    assert client.get("/asistente/estado").json() == {
        "ollama": True,
        "modelo": "qwen3:4b",
        "modelo_instalado": True,
        "error": None,
    }
    state.ollama = FalsoOllama(instalados=["llama3.2:3b"])
    assert client.get("/asistente/estado").json()["modelo_instalado"] is False
    state.ollama = FalsoOllama(instalados=OllamaNoDisponible())
    caido = client.get("/asistente/estado").json()
    assert caido["ollama"] is False and caido["error"] == "Ollama no está corriendo"


def test_setting_asistente_modelo(client):
    assert client.get("/settings").json()["asistente_modelo"] == "qwen3:4b"
    r = client.put("/settings", json={"asistente_modelo": " llama3.2:3b "})
    assert r.json()["asistente_modelo"] == "llama3.2:3b"
    assert client.put("/settings", json={"asistente_modelo": ""}).status_code == 422


def ndjson(*objetos) -> bytes:
    return ("\n".join(json.dumps(o) for o in objetos) + "\n").encode()


def cliente_http(handler):
    return OllamaCliente(transporte=httpx.MockTransport(handler))


def test_cliente_envia_think_false_solo_para_qwen3_y_transmite():
    cargas = []

    def handler(peticion):
        cargas.append(json.loads(peticion.content))
        return httpx.Response(200, content=ndjson(texto("a"), texto("b")))

    cliente = cliente_http(handler)

    async def escenario():
        return [
            t
            async for t in cliente.chat("qwen3:4b", [{"role": "user", "content": "x"}], [{"t": 1}])
        ]

    trozos = asyncio.run(escenario())
    assert [t["message"]["content"] for t in trozos] == ["a", "b"]
    assert (
        cargas[0]["think"] is False
        and cargas[0]["stream"] is True
        and cargas[0]["tools"] == [{"t": 1}]
    )

    async def otro():
        return [t async for t in cliente.chat("llama3.2:3b", [])]

    asyncio.run(otro())
    assert "think" not in cargas[1] and "tools" not in cargas[1]


def test_cliente_modelo_no_instalado_y_ollama_caido():
    def no_esta(peticion):
        return httpx.Response(404, json={"error": "model 'x' not found"})

    async def consumir(cliente):
        return [t async for t in cliente.chat("x:1b", [])]

    with pytest.raises(OllamaError, match="no está instalado"):
        asyncio.run(consumir(cliente_http(no_esta)))

    def caido(peticion):
        raise httpx.ConnectError("rechazado")

    with pytest.raises(OllamaNoDisponible, match="Ollama no está corriendo"):
        asyncio.run(consumir(cliente_http(caido)))
    with pytest.raises(OllamaNoDisponible):
        asyncio.run(cliente_http(caido).etiquetas())


def test_cliente_lista_modelos():
    def handler(peticion):
        assert peticion.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}, {"name": "a:1"}]})

    assert asyncio.run(cliente_http(handler).etiquetas()) == ["qwen3:4b", "a:1"]
