import asyncio
import json

import httpx
import pytest

from backend import services
from backend.asistente import chat
from backend.asistente import herramientas as h
from backend.asistente.ollama import (
    FiltroPensamiento,
    OllamaCliente,
    OllamaError,
    OllamaNoDisponible,
)
from backend.core.storage import MODELO_ASISTENTE as M

from .asgi_client import MiniClient
from .test_herramientas_asistente import con_tareas  # noqa: F401


class FalsoOllama:
    def __init__(self, vueltas=None, instalados=None, error=None, cargados=(M,)):
        self.cargados_lista = list(cargados)
        self.precalentados = []
        self.vueltas = list(vueltas or [])
        self.instalados = instalados
        self.error = error
        self.llamadas = []

    async def chat(self, modelo, mensajes, herramientas=None, keep_alive="90s"):
        self.llamadas.append(
            {
                "modelo": modelo,
                "mensajes": [dict(m) for m in mensajes],
                "tools": herramientas,
                "keep_alive": keep_alive,
            }
        )
        if self.error:
            raise self.error
        for trozo in self.vueltas.pop(0):
            yield trozo

    async def cargados(self):
        if isinstance(self.error, OllamaNoDisponible):
            raise self.error
        return self.cargados_lista

    async def precalentar(self, modelo, keep_alive="90s"):
        self.precalentados.append((modelo, keep_alive))

    async def liberar(self, modelo):
        if isinstance(self.error, OllamaNoDisponible):
            raise self.error
        self.liberados = [*getattr(self, "liberados", []), modelo]

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
    assert primera["modelo"] == M and len(primera["tools"]) == 12
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
    assert eventos[-1] == {"type": "error", "message": "Ollama no está corriendo"}


def test_estado_del_asistente(app, state):
    client = MiniClient(app, headers={"X-Token": "dev"})
    state.ollama = FalsoOllama(instalados=[M, "llama3.2:3b"])
    assert client.get("/asistente/estado").json() == {
        "ollama": True,
        "modelo": M,
        "modelo_instalado": True,
        "error": None,
    }
    state.ollama = FalsoOllama(instalados=["llama3.2:3b"])
    assert client.get("/asistente/estado").json()["modelo_instalado"] is False
    state.ollama = FalsoOllama(instalados=OllamaNoDisponible())
    caido = client.get("/asistente/estado").json()
    assert caido["ollama"] is False and caido["error"] == "Ollama no está corriendo"


def test_setting_asistente_modelo(client):
    assert client.get("/settings").json()["asistente_modelo"] == M
    r = client.put("/settings", json={"asistente_modelo": " llama3.2:3b "})
    assert r.json()["asistente_modelo"] == "llama3.2:3b"
    assert client.put("/settings", json={"asistente_modelo": ""}).status_code == 422


def ndjson(*objetos) -> bytes:
    return ("\n".join(json.dumps(o) for o in objetos) + "\n").encode()


def cliente_http(handler):
    return OllamaCliente(transporte=httpx.MockTransport(handler))


def test_cliente_no_manda_think_y_transmite():
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
    assert "think" not in cargas[0] and cargas[0]["stream"] is True
    assert cargas[0]["tools"] == [{"t": 1}]

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


def test_filtro_quita_el_pensamiento_aunque_llegue_partido():
    filtro = FiltroPensamiento()
    visibles, pensando = [], 0
    for trozo in ["<th", "ink>\nrazono", " mucho</thi", "nk>\n\nHola", " mundo", "<"]:
        texto_visible, empezo = filtro.procesar(trozo)
        visibles.append(texto_visible)
        pensando += empezo
    visibles.append(filtro.finalizar())
    assert "".join(visibles) == "Hola mundo<" and pensando == 1


def test_filtro_sin_etiquetas_no_cambia_el_texto_y_descarta_pensamiento_sin_cerrar():
    filtro = FiltroPensamiento()
    assert filtro.procesar("Hola 5 < 6")[0] + filtro.finalizar() == "Hola 5 < 6"
    abierto = FiltroPensamiento()
    assert abierto.procesar("<think>nunca cierra")[0] == "" and abierto.finalizar() == ""


def test_el_chat_no_emite_los_bloques_think(con_tareas):  # noqa: F811
    con_tareas.ollama = FalsoOllama(
        [[texto("<think>\nplan"), texto(" secreto</think>\n\n"), texto("Hola"), texto("!")]]
    )
    eventos = recolectar(con_tareas, USUARIO)
    assert [e["type"] for e in eventos] == ["estado", "token", "token", "fin"]
    assert "".join(e.get("text", "") for e in eventos) == "Hola!"
    assert "secreto" not in json.dumps(eventos)


def test_el_historial_guardado_no_trae_el_pensamiento(con_tareas):  # noqa: F811
    falso = FalsoOllama(
        [[texto("<think>x</think>"), llamada("proximas_entregas", {})], [texto("listo")]]
    )
    con_tareas.ollama = falso
    recolectar(con_tareas, USUARIO)
    asistente_msg = falso.llamadas[1]["mensajes"][2]
    assert asistente_msg["role"] == "assistant" and asistente_msg["content"] == ""


def test_primer_mensaje_avisa_que_carga_el_modelo(con_tareas):  # noqa: F811
    con_tareas.ollama = FalsoOllama([[texto("hola")]], cargados=())
    eventos = recolectar(con_tareas, USUARIO)
    assert eventos[0] == chat.estado_evento("cargando", "Cargando modelo…")
    assert eventos[0]["mensaje"] == "Cargando modelo…" and "text" not in eventos[0]
    con_tareas.ollama = FalsoOllama([[texto("hola")]])
    assert recolectar(con_tareas, USUARIO)[0]["type"] == "token"


def test_el_contexto_de_la_tarea_es_corto(con_tareas):  # noqa: F811
    con_tareas.storage.set_indicaciones("100-1.1", "x" * 2000)
    falso = FalsoOllama([[texto("ok")]])
    con_tareas.ollama = falso
    recolectar(con_tareas, USUARIO, "100-1.1")
    sistema = falso.llamadas[0]["mensajes"][0]["content"]
    assert len(sistema) < 2400


def test_historial_largo_se_recorta_conservando_lo_reciente(con_tareas):  # noqa: F811
    historial = []
    for i in range(40):
        historial.append({"rol": "user", "contenido": f"pregunta {i} " + "x" * 400})
        historial.append({"rol": "assistant", "contenido": f"respuesta {i} " + "y" * 400})
    historial.append({"rol": "user", "contenido": "última pregunta"})
    falso = FalsoOllama([[texto("ok")]])
    con_tareas.ollama = falso
    recolectar(con_tareas, historial)
    enviados = falso.llamadas[0]["mensajes"]
    assert 2 < len(enviados) < 20
    assert enviados[1]["role"] == "user" and enviados[-1]["content"] == "última pregunta"
    assert sum(len(m["content"]) for m in enviados) < 7500


def test_api_precalentar(app, state):
    client = MiniClient(app, headers={"X-Token": "dev"})
    frio = FalsoOllama(cargados=())
    state.ollama = frio

    async def escenario():
        r = await client.arequest("POST", "/asistente/precalentar")
        await asyncio.sleep(0.05)
        return r

    r = asyncio.run(escenario())
    assert r.json() == {"cargado": False, "cargando": True, "modelo": M}
    assert frio.precalentados == [(M, "90s")]
    state.ollama = FalsoOllama()
    assert client.post("/asistente/precalentar").json()["cargado"] is True
    state.ollama = FalsoOllama(error=OllamaNoDisponible())
    r = client.post("/asistente/precalentar")
    assert r.status_code == 503 and r.json()["error"]["code"] == "ollama_no_disponible"


def test_cliente_keep_alive_cargados_y_precalentar():
    cargas = []

    def handler(peticion):
        if peticion.url.path == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
        cargas.append(json.loads(peticion.content))
        return httpx.Response(200, content=ndjson(texto("a")))

    cliente = cliente_http(handler)

    async def escenario():
        await cliente.precalentar("qwen3:4b", "90s")
        _ = [t async for t in cliente.chat("qwen3:4b", [], keep_alive="90s")]
        return await cliente.cargados()

    assert asyncio.run(escenario()) == ["qwen3:4b"]
    assert cargas[0]["messages"] == [] and cargas[0]["keep_alive"] == "90s"
    assert cargas[1]["keep_alive"] == "90s"


def test_el_campo_thinking_de_ollama_solo_avisa_que_piensa(con_tareas):  # noqa: F811
    razonando = {"message": {"role": "assistant", "content": "", "thinking": "plan secreto"}}
    con_tareas.ollama = FalsoOllama([[razonando, razonando, texto("Hola")]])
    eventos = recolectar(con_tareas, USUARIO)
    assert [e["type"] for e in eventos] == ["estado", "token", "fin"]
    assert "secreto" not in json.dumps(eventos)


def test_keep_alive_configurable_llega_al_chat_y_al_precalentado(client, app, state):
    assert client.get("/settings").json()["asistente_keep_alive_s"] == 90
    r = client.put("/settings", json={"asistente_keep_alive_s": 30})
    assert r.json()["asistente_keep_alive_s"] == 30
    for malo in (0, -5, "x", True, 1.5):
        assert client.put("/settings", json={"asistente_keep_alive_s": malo}).status_code == 422
    falso = FalsoOllama([[texto("hola")]], cargados=())
    state.ollama = falso
    recolectar(state, USUARIO)
    assert falso.llamadas[0]["keep_alive"] == "30s"

    async def escenario():
        r = await client.arequest("POST", "/asistente/precalentar")
        await asyncio.sleep(0.05)
        return r

    asyncio.run(escenario())
    assert falso.precalentados[-1] == (M, "30s")


def test_liberar_descarga_el_modelo(app, state):
    client = MiniClient(app, headers={"X-Token": "dev"})
    state.ollama = FalsoOllama()
    assert client.post("/asistente/liberar").json() == {"liberado": True, "modelo": M}
    assert state.ollama.liberados == [M]
    state.ollama = FalsoOllama(error=OllamaNoDisponible())
    assert client.post("/asistente/liberar").json() == {"liberado": False, "modelo": M}


def test_cliente_liberar_manda_keep_alive_cero():
    cargas = []

    def handler(peticion):
        cargas.append(json.loads(peticion.content))
        return httpx.Response(200, json={"done": True})

    asyncio.run(cliente_http(handler).liberar("qwen3:4b"))
    assert cargas == [{"model": "qwen3:4b", "messages": [], "keep_alive": 0}]


def test_el_modelo_por_defecto_es_el_instruct_y_se_migra_el_anterior(state):
    assert state.storage.get_settings()["asistente_modelo"] == "qwen3:4b-instruct-2507-q4_K_M"
    state.storage.set_settings({"asistente_modelo": "qwen3:4b"})
    state.storage.reabrir()
    assert state.storage.get_settings()["asistente_modelo"] == M
    state.storage.set_settings({"asistente_modelo": "llama3.2:3b"})
    state.storage.reabrir()
    assert state.storage.get_settings()["asistente_modelo"] == "llama3.2:3b"


def test_no_think_solo_para_modelos_que_razonan(con_tareas):  # noqa: F811
    instruct = FalsoOllama([[texto("ok")]])
    con_tareas.ollama = instruct
    recolectar(con_tareas, USUARIO)
    assert "/no_think" not in instruct.llamadas[0]["mensajes"][0]["content"]
    con_tareas.storage.set_settings({"asistente_modelo": "qwen3:4b"})
    razona = FalsoOllama([[texto("ok")]], cargados=("qwen3:4b",))
    con_tareas.ollama = razona
    recolectar(con_tareas, USUARIO)
    assert "/no_think" in razona.llamadas[0]["mensajes"][0]["content"]


def test_el_prompt_y_la_herramienta_prohiben_confirmar_en_texto():
    assert "Nunca pidas confirmación en texto" in chat.PROMPT_SISTEMA
    assert "SIEMPRE" in chat.PROMPT_SISTEMA
    descripcion = h.HERRAMIENTAS["entregar_tarea"].descripcion
    assert "SIEMPRE llama a esta herramienta" in descripcion
    assert "Nunca pidas confirmación en texto" in descripcion


ENTREGA = [{"rol": "user", "contenido": "entrega la ficha técnica"}]


def test_si_pide_entregar_y_el_modelo_pregunta_en_texto_se_reintenta(con_tareas):  # noqa: F811
    falso = FalsoOllama(
        [
            [texto("¿Estás seguro de que quieres entregarla?")],
            [llamada("entregar_tarea", {"tarea_id": "100-1.1"})],
        ]
    )
    con_tareas.ollama = falso
    base = con_tareas.paths.generaciones
    con_tareas.storage.set_generacion("100-1.1", "md", str(base / "a.docx"), str(base / "a.pdf"))
    eventos = recolectar(con_tareas, ENTREGA)
    assert [e["type"] for e in eventos] == ["tool_call", "confirmar", "fin"]
    assert not any("seguro" in e.get("text", "") for e in eventos)
    segunda = falso.llamadas[1]["mensajes"]
    assert segunda[-2]["role"] == "assistant" and "seguro" in segunda[-2]["content"]
    assert segunda[-1]["role"] == "user" and "entregar_tarea" in segunda[-1]["content"]


def test_el_reintento_ocurre_una_sola_vez_y_luego_se_muestra_el_texto(con_tareas):  # noqa: F811
    falso = FalsoOllama([[texto("Primero dime cuál.")], [texto("No sé cuál.")]])
    con_tareas.ollama = falso
    eventos = recolectar(con_tareas, ENTREGA)
    assert len(falso.llamadas) == 2
    assert [e["type"] for e in eventos] == ["token", "fin"] and eventos[0]["text"] == "No sé cuál."


def test_tras_buscar_la_tarea_tambien_se_exige_llamar_a_entregar(con_tareas):  # noqa: F811
    base = con_tareas.paths.generaciones
    con_tareas.storage.set_generacion("100-1.1", "md", str(base / "a.docx"), str(base / "a.pdf"))
    falso = FalsoOllama(
        [
            [llamada("buscar_tareas", {"texto": "ficha"})],
            [texto("Encontré la ficha, ¿la entrego?")],
            [llamada("entregar_tarea", {"tarea_id": "100-1.1"})],
        ]
    )
    con_tareas.ollama = falso
    eventos = recolectar(con_tareas, ENTREGA)
    tipos = [e["type"] for e in eventos]
    assert tipos == ["tool_call", "tool_result", "tool_call", "confirmar", "fin"]
    assert len(falso.llamadas) == 3


def test_sin_intencion_de_entrega_los_tokens_se_emiten_en_vivo(con_tareas):  # noqa: F811
    con_tareas.ollama = FalsoOllama([[texto("Hola "), texto("a todos")]])
    tipos = [e["type"] for e in recolectar(con_tareas, USUARIO)]
    assert tipos == ["token", "token", "fin"]
    assert chat.pide_entregar([{"rol": "user", "contenido": "entrega la 1.2"}])
    assert chat.pide_entregar([{"rol": "user", "contenido": "Quiero entregar la ficha"}])
    assert not chat.pide_entregar([{"rol": "user", "contenido": "¿Cuándo vence la entrega?"}])
    assert not chat.pide_entregar([{"rol": "user", "contenido": "¿Qué vence hoy?"}])


def test_generar_tarea_se_bloquea_si_el_usuario_no_lo_pidio(con_tareas, monkeypatch):  # noqa: F811
    lanzados = []

    async def generar(state, ctx, tarea_id, extra=None, portada=None, instrucciones=None):
        lanzados.append(tarea_id)

    monkeypatch.setattr(services, "run_generar", generar)
    con_tareas.ollama = FalsoOllama(
        [[llamada("generar_tarea", {"tarea_id": "100-1.1"})], [texto("listo")]]
    )
    eventos = recolectar(con_tareas, [{"rol": "user", "contenido": "¿qué onda con la 1.1?"}])
    resultado = next(e for e in eventos if e["type"] == "tool_result")["resultado"]
    assert "no pidió generar_tarea" in resultado["error"] and lanzados == []


def test_generar_tarea_se_permite_si_el_usuario_la_pide(con_tareas, monkeypatch):  # noqa: F811
    lanzados = []

    async def generar(state, ctx, tarea_id, extra=None, portada=None, instrucciones=None):
        lanzados.append(tarea_id)

    monkeypatch.setattr(services, "run_generar", generar)
    con_tareas.storage.set_settings({"cuenta": "1"})
    con_tareas.credentials.set("1", "pw")
    con_tareas.ollama = FalsoOllama(
        [[llamada("generar_tarea", {"tarea_id": "100-1.1"})], [texto("generando")]]
    )

    async def escenario():
        eventos = [
            e
            async for e in chat.conversar(
                con_tareas, [{"rol": "user", "contenido": "genera la ficha técnica"}], None
            )
        ]
        await asyncio.sleep(0.05)
        return eventos

    eventos = asyncio.run(escenario())
    assert next(e for e in eventos if e["type"] == "tool_result")["resultado"]["tipo"] == "generar"
    assert lanzados == ["100-1.1"]


def test_acciones_que_piden_permiso_explicito():
    pide = lambda nombre, texto: chat.accion_permitida(  # noqa: E731
        nombre, [{"rol": "user", "contenido": texto}]
    )
    assert pide("sincronizar", "sincroniza mis tareas") and not pide("sincronizar", "hola")
    assert pide("revisar_entregas", "revisa qué ya entregué")
    assert not pide("generar_tarea", "entrega la 1.2")
    assert pide("buscar_tareas", "lo que sea") and pide("entregar_tarea", "lo que sea")
    assert "no inventes una" in chat.PROMPT_SISTEMA and "ver_tarea" in chat.PROMPT_SISTEMA


def test_intenciones_que_exigen_una_herramienta():
    def pide(texto):
        requerida = chat.herramienta_requerida([{"rol": "user", "contenido": texto}])
        return requerida[0] if requerida else None

    assert pide("El profe dijo que la 1.3 es en equipo de 3") == "agregar_indicaciones"
    assert pide("la maestra pidió máximo 2 hojas") == "agregar_indicaciones"
    assert pide("Explícame la 1.2 de Lógica") == "ver_tarea"
    assert pide("¿de qué trata la ficha?") == "ver_tarea"
    assert pide("entrega la 1.2") == "entregar_tarea"
    assert pide("¿Qué vence esta semana?") is None


def test_si_cuenta_una_indicacion_y_no_la_guarda_se_reintenta(con_tareas):  # noqa: F811
    falso = FalsoOllama(
        [
            [llamada("buscar_tareas", {"texto": "1.1"})],
            [texto("Listo, anotado ✅")],
            [llamada("agregar_indicaciones", {"tarea_id": "100-1.1", "texto": "En equipo de 3"})],
            [texto("Guardé la indicación.")],
        ]
    )
    con_tareas.ollama = falso
    eventos = recolectar(
        con_tareas, [{"rol": "user", "contenido": "El profe dijo que la 1.1 es en equipo de 3"}]
    )
    assert con_tareas.storage.get_indicaciones("100-1.1") == "En equipo de 3"
    assert eventos[-1]["type"] == "fin"
    assert "anotado" not in "".join(e.get("text", "") for e in eventos)
    assert "agregar_indicaciones" in falso.llamadas[2]["mensajes"][-1]["content"]


def test_si_pide_explicar_y_no_llama_a_ver_tarea_se_reintenta(con_tareas):  # noqa: F811
    falso = FalsoOllama(
        [
            [llamada("buscar_tareas", {"texto": "1.1"})],
            [texto("Es una ficha.")],
            [llamada("ver_tarea", {"tarea_id": "100-1.1"})],
            [texto("Trata de una ficha técnica.")],
        ]
    )
    con_tareas.ollama = falso
    eventos = recolectar(con_tareas, [{"rol": "user", "contenido": "Explícame la 1.1"}])
    nombres = [e["nombre"] for e in eventos if e["type"] == "tool_call"]
    assert nombres == ["buscar_tareas", "ver_tarea"]
    assert "".join(e.get("text", "") for e in eventos) == "Trata de una ficha técnica."


def test_quitar_emojis_elimina_emojis_y_secuencias():
    assert chat.quitar_emojis("a😀b") == "ab"
    assert chat.quitar_emojis("Hola 👍🏽 ❤️ 🇲🇽 ⭐") == "Hola    "
    assert chat.quitar_emojis("👨‍👩‍👧") == ""
    assert chat.quitar_emojis("a‍b️c") == "abc"


def test_quitar_emojis_conserva_texto_normal():
    normal = "¡Hola! ¿Qué tal, señor Peña? “Listo” — 100% … áéíóú"
    assert chat.quitar_emojis(normal) == normal


def test_prompt_sistema_prohibe_emojis():
    assert "No uses emojis ni emoticonos" in chat.PROMPT_SISTEMA
