import asyncio
from pathlib import Path

from backend import mcp, services
from backend.asistente import herramientas as h
from backend.core import nexus, siase

DATOS = Path(__file__).parent / "html_reales"
SIASE = siase.parse_evaluacion((DATOS / "siase_evaluacion.html").read_text(encoding="utf-8"))
NEXUS = nexus.parse_calificaciones((DATOS / "nexus_calificaciones.html").read_text("utf-8"))


def materia(resumen, clave):
    return next(m for m in resumen["materias"] if m["clave"] == clave)


def test_sin_lectura_de_siase_el_resumen_esta_vacio(client):
    r = client.get("/calificaciones").json()
    assert r["materias"] == [] and r["siase_leida_en"] is None
    assert r["semestre"]["actual"] == 0


def test_resumen_con_la_tabla_guardada(client, state):
    state.storage.set_siase_calificaciones(SIASE)
    r = client.get("/calificaciones").json()
    assert len(r["materias"]) == 10 and r["siase_leida_en"]
    calidad = materia(r, "095")
    assert calidad["tipo"] == "carrera" and calidad["materia_id"] is None
    assert materia(r, "019")["estado"] == "sin_datos"


def test_empareja_con_nexus_por_nombre_y_usa_su_portafolio(client, seeded):
    seeded.storage.set_siase_calificaciones(SIASE)
    seeded.storage.set_calificaciones("100", NEXUS)
    logica = materia(client.get("/calificaciones").json(), "033")
    assert logica["materia_id"] == "100"
    assert logica["tipo"] == "bachillerato"
    assert len(logica["portafolio"]) == 5
    assert next(x for x in logica["componentes"] if x["clave"] == "portafolio")["puntos"] == 16


def test_tarea_vencida_y_no_entregada_es_perdida(client, seeded):
    seeded.storage.set_siase_calificaciones(SIASE)
    tabla = {
        "columnas": ["Trabajo", "Elemento Evaluable", "", "Calificacion", "Valor", "Puntos"],
        "filas": [
            ["", "Dimensión 1 - Algo", "", "-", "20", "0"],
            ["", "Otra tarea", "", "-", "20", "0"],
            ["", "Hecha", "", "100", "10", "10"],
        ],
    }
    seeded.storage.set_calificaciones("100", tabla)
    seeded.storage._run(
        "UPDATE tareas SET hasta = ?, estado = ?", ("2020-01-01T10:00", "pendiente")
    )
    logica = materia(client.get("/calificaciones").json(), "033")
    perdidas = {x["titulo"]: x["perdida"] for x in logica["portafolio"]}
    assert perdidas == {"Dimensión 1 - Algo": True, "Otra tarea": False, "Hecha": False}
    assert sorted(p["titulo"] for p in logica["pendientes"] if p["clave"] == "portafolio") == [
        "Dimensión 1 - Algo",
        "Otra tarea",
    ]

    seeded.storage._run("UPDATE tareas SET estado = 'entregada'")
    logica = materia(client.get("/calificaciones").json(), "033")
    assert not any(x["perdida"] for x in logica["portafolio"])


def test_homonimos_se_emparejan_uno_a_uno(client, seeded):
    seeded.storage.set_siase_calificaciones(SIASE)
    tabla = {
        "columnas": ["Trabajo", "Elemento Evaluable", "", "Calificacion", "Valor", "Puntos"],
        "filas": [["", "Manual Técnico", "", "-", "10", "0"] for _ in range(3)],
    }
    seeded.storage.set_calificaciones("100", tabla)
    seeded.storage._run("UPDATE tareas SET hasta = ?", ("2999-01-01T10:00",))
    seeded.storage._run(
        "UPDATE tareas SET titulo = 'Manual Técnico', hasta = '2020-01-01T10:00' "
        "WHERE id = (SELECT id FROM tareas LIMIT 1)"
    )
    logica = materia(client.get("/calificaciones").json(), "033")
    assert [x["perdida"] for x in logica["portafolio"]] == [True, False, False]


def test_tarea_con_plazo_futuro_no_es_perdida(client, seeded):
    seeded.storage.set_siase_calificaciones(SIASE)
    tabla = {
        "columnas": ["Trabajo", "Elemento Evaluable", "", "Calificacion", "Valor", "Puntos"],
        "filas": [["", "Dimensión 1 - Algo", "", "-", "40", "0"]],
    }
    seeded.storage.set_calificaciones("100", tabla)
    seeded.storage._run("UPDATE tareas SET hasta = ?", ("2999-01-01T10:00",))
    logica = materia(client.get("/calificaciones").json(), "033")
    assert logica["portafolio"][0]["perdida"] is False


def test_objetivos_se_guardan_y_se_borran(client, state):
    state.storage.set_siase_calificaciones(SIASE)
    r = client.put(
        "/calificaciones/objetivos", json={"semestre": 90, "materias": {"095": 85, "015": 95}}
    ).json()
    assert r["semestre"]["objetivo"] == 90
    assert materia(r, "095")["objetivo"] == 85 and materia(r, "015")["objetivo"] == 95
    r = client.put("/calificaciones/objetivos", json={"materias": {"095": None}}).json()
    assert materia(r, "095")["objetivo"] is None
    assert materia(r, "015")["objetivo"] == 95 and r["semestre"]["objetivo"] == 90
    r = client.put("/calificaciones/objetivos", json={"semestre": None}).json()
    assert r["semestre"]["objetivo"] is None and materia(r, "015")["objetivo"] == 95
    assert client.get("/calificaciones").json() == r


def test_objetivos_invalidos(client, state):
    state.storage.set_siase_calificaciones(SIASE)
    malo = client.put("/calificaciones/objetivos", json={"semestre": 101})
    assert malo.status_code == 422 and malo.json()["error"]["code"] == "validacion"
    negativo = client.put("/calificaciones/objetivos", json={"materias": {"095": -1}})
    assert negativo.status_code == 422
    desconocida = client.put("/calificaciones/objetivos", json={"materias": {"999": 80}})
    assert desconocida.status_code == 404
    texto = client.put("/calificaciones/objetivos", json={"semestre": "mucho"})
    assert texto.status_code == 422
    assert state.storage.get_objetivos() == {}


def test_tipo_manual(client, state):
    state.storage.set_siase_calificaciones(SIASE)
    r = client.put("/calificaciones/tipo", json={"clave": "019", "tipo": "portafolio"}).json()
    vocacional = materia(r, "019")
    assert vocacional["tipo"] == "portafolio" and vocacional["tipo_manual"] is True
    assert vocacional["componentes"][0]["peso"] == 100
    r = client.put("/calificaciones/tipo", json={"clave": "019", "tipo": None}).json()
    assert materia(r, "019")["tipo"] is None and not materia(r, "019")["tipo_manual"]


def test_tipo_invalido_o_materia_desconocida(client, state):
    state.storage.set_siase_calificaciones(SIASE)
    assert client.put("/calificaciones/tipo", json={"clave": "019", "tipo": "x"}).status_code == 422
    assert (
        client.put("/calificaciones/tipo", json={"clave": "999", "tipo": "carrera"}).status_code
        == 404
    )


def test_la_tabla_de_siase_sobrevive_a_reabrir_la_base(state):
    state.storage.set_siase_calificaciones(SIASE)
    state.storage.set_objetivo("095", 88)
    state.storage.set_tipo_manual("019", "portafolio")
    state.storage.reabrir()
    assert state.storage.get_siase_calificaciones()["materias"] == SIASE
    assert state.storage.get_objetivos() == {"095": 88}
    assert state.storage.get_tipos_manuales() == {"019": "portafolio"}


def ejecutar(state, args=None):
    return asyncio.run(h.ejecutar(state, "ver_calificaciones", args or {}))


def test_herramienta_compacta_y_con_detalle(state):
    state.storage.set_siase_calificaciones(SIASE)
    resumen = ejecutar(state)
    assert len(resumen["materias"]) == 10
    assert "componentes" not in resumen["materias"][0]
    assert {"nombre", "proyectada", "prob_aprobar", "estado"} <= set(resumen["materias"][0])
    detalle = ejecutar(state, {"materia": "calidad"})
    assert [m["clave"] for m in detalle["materias"]] == ["095"]
    assert detalle["materias"][0]["componentes"] and detalle["materias"][0]["pendientes"]
    assert not h.HERRAMIENTAS["ver_calificaciones"].peligrosa


def test_herramienta_sin_datos(state):
    assert ejecutar(state)["materias"] == []


def test_mcp_expone_ver_calificaciones(state):
    state.storage.set_siase_calificaciones(SIASE)
    servidor = mcp.build_server(state)
    nombres = {t.name for t in asyncio.run(servidor.list_tools())}
    assert "ver_calificaciones" in nombres
    assert services.resumen_calificaciones(state)["materias"]
