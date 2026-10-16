import asyncio
import json

from backend import mcp, services
from backend.asistente import herramientas as h

from .test_herramientas_asistente import con_tareas  # noqa: F401


def correr(coro):
    return asyncio.run(coro)


def servidor(state):
    return mcp.build_server(state)


def llamar(srv, nombre, args=None):
    async def ir():
        return await srv.call_tool(nombre, args or {})

    contenido = correr(ir())
    bloques = contenido[0] if isinstance(contenido, tuple) else contenido
    texto = bloques[0].text
    try:
        return json.loads(texto)
    except ValueError:
        return texto


def test_lista_las_mismas_herramientas_que_el_asistente(con_tareas):  # noqa: F811
    herramientas = correr(servidor(con_tareas).list_tools())
    assert {t.name for t in herramientas} == set(h.HERRAMIENTAS)
    for t in herramientas:
        assert t.description.strip()
        assert t.inputSchema["type"] == "object"


def test_los_esquemas_respetan_requeridos_tipos_y_enumeraciones(con_tareas):  # noqa: F811
    por_nombre = {t.name: t.inputSchema for t in correr(servidor(con_tareas).list_tools())}
    assert por_nombre["ver_tarea"]["required"] == ["tarea_id"]
    assert por_nombre["agregar_indicaciones"]["required"] == ["tarea_id", "texto"]
    assert "required" not in por_nombre["buscar_tareas"]
    assert por_nombre["crear_pdf_imagenes"]["properties"]["rutas"]["type"] == "array"
    estado = por_nombre["buscar_tareas"]["properties"]["estado"]
    assert "pendiente" in json.dumps(estado)
    assert por_nombre["proximas_entregas"]["properties"]["dias"]["anyOf"][0]["type"] == "integer"


def test_ejecuta_herramientas_de_lectura_y_escritura(con_tareas):  # noqa: F811
    srv = servidor(con_tareas)
    encontradas = llamar(srv, "buscar_tareas", {"texto": "ficha"})
    primera = encontradas[0] if isinstance(encontradas, list) else encontradas
    assert primera["id"] == "100-1.1"
    llamar(srv, "reemplazar_indicaciones", {"tarea_id": "100-1.1", "texto": "Desde MCP"})
    assert con_tareas.storage.get_indicaciones("100-1.1") == "Desde MCP"
    ver = llamar(srv, "ver_tarea", {"tarea_id": "100-1.1"})
    assert ver["indicaciones"] == "Desde MCP"


def test_entregar_exige_confirmar_true(con_tareas, monkeypatch):  # noqa: F811
    lanzados = []

    async def entregar(state, ctx, tarea_id):
        lanzados.append(tarea_id)
        return {"entregada": True}

    monkeypatch.setattr(services, "run_entregar", entregar)
    base = con_tareas.paths.generaciones
    con_tareas.storage.set_generacion("100-1.1", "md", str(base / "a.docx"), str(base / "a.pdf"))
    srv = servidor(con_tareas)

    sin = llamar(srv, "entregar_tarea", {"tarea_id": "100-1.1"})
    assert "confirmar=true" in sin["error"] and lanzados == []
    falso = llamar(srv, "entregar_tarea", {"tarea_id": "100-1.1", "confirmar": False})
    assert "error" in falso and lanzados == []

    ok = llamar(srv, "entregar_tarea", {"tarea_id": "100-1.1", "confirmar": True})
    assert lanzados == ["100-1.1"]
    assert ok["estado"] == "ok" and ok["resultado_job"] == {"entregada": True}


def test_las_herramientas_lentas_esperan_el_resultado_del_job(con_tareas, monkeypatch):  # noqa: F811
    async def revisar(state, ctx):
        await asyncio.sleep(0.1)
        return {"revisadas": 3, "entregadas": 1, "pendientes": 2, "errores": []}

    monkeypatch.setattr(services, "run_revisar_entregas", revisar)
    con_tareas.storage.set_settings({"cuenta": "1"})
    con_tareas.credentials.set("1", "pw")
    resultado = llamar(servidor(con_tareas), "revisar_entregas")
    assert resultado["estado"] == "ok" and resultado["resultado_job"]["revisadas"] == 3


def test_errores_de_herramienta_llegan_como_texto_util(con_tareas):  # noqa: F811
    resultado = llamar(servidor(con_tareas), "ver_tarea", {"tarea_id": "nada"})
    assert "No existe la tarea" in resultado["error"]


def test_el_estado_se_crea_una_sola_vez_y_el_modulo_tiene_main(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp.config, "DATA_DIR", tmp_path / "data")
    srv = mcp.build_server()
    assert callable(mcp.main)
    herramientas = correr(srv.list_tools())
    assert len(herramientas) == 12
