import asyncio
from datetime import datetime

import docx
import pytest
from docx.oxml.ns import qn

from backend import services
from backend.asistente import herramientas as h
from backend.core import documents
from backend.core.types import (
    DetalleTarea,
    EtapaItem,
    Rubrica,
    RubricaCriterio,
    RubricaNivel,
    TareaItem,
)

from .test_herramientas_sueltas import falso_pdf, foto_bytes

AHORA = datetime(2026, 10, 15, 12, 0)


def correr(coro):
    return asyncio.run(coro)


def ejecutar(state, nombre, args=None, **kw):
    return correr(h.ejecutar(state, nombre, args, **kw))


@pytest.fixture
def con_tareas(seeded, monkeypatch):
    monkeypatch.setattr(services, "ahora_monterrey", lambda: AHORA)
    st = seeded.storage
    st.replace_estructura(
        "100",
        [
            EtapaItem(
                "Etapa 1",
                "d",
                0,
                [
                    TareaItem("1.1", "Dimensión 1 - Ficha Técnica", "dimension", 2.0, None, 0),
                    TareaItem(
                        "1.2", "Dimensión 2 - Comprensión - Mapa mental", "dimension", 2.0, None, 1
                    ),
                    TareaItem("1.3", "Examen Diagnóstico Etapa 1", "examen", None, None, 2),
                    TareaItem("1.4", "Evidencia - Informe", "evidencia", 5.0, None, 3),
                ],
            )
        ],
    )
    for tid, hasta, estado in (
        ("100-1.1", "2026-10-20T00:00", "pendiente"),
        ("100-1.2", "2026-10-10T00:00", "pendiente"),
        ("100-1.3", "2026-10-30T00:00", "pendiente"),
        ("100-1.4", "2026-11-20T00:00", "entregada"),
    ):
        st._run("UPDATE tareas SET hasta = ?, estado = ? WHERE id = ?", (hasta, estado, tid))
    return seeded


def test_esquemas_completos_y_bien_formados():
    nombres = {e["function"]["name"] for e in h.esquemas()}
    assert nombres == {
        "buscar_tareas",
        "ver_tarea",
        "proximas_entregas",
        "agregar_indicaciones",
        "reemplazar_indicaciones",
        "crear_pdf_imagenes",
        "generar_portada",
        "sincronizar",
        "revisar_entregas",
        "generar_tarea",
        "entregar_tarea",
    }
    for esquema in h.esquemas():
        funcion = esquema["function"]
        assert esquema["type"] == "function" and funcion["description"].strip()
        params = funcion["parameters"]
        assert params["type"] == "object"
        assert set(params["required"]) <= set(params["properties"])
    assert h.HERRAMIENTAS["entregar_tarea"].peligrosa
    assert not any(t.peligrosa for n, t in h.HERRAMIENTAS.items() if n != "entregar_tarea")


def test_buscar_tareas_sin_acentos_y_con_filtros(con_tareas):
    encontradas = ejecutar(con_tareas, "buscar_tareas", {"texto": "dimension 2"})
    assert [t["id"] for t in encontradas] == ["100-1.2"]
    assert encontradas[0]["materia"] == "Lógica" and encontradas[0]["vencida"] is True
    assert [t["id"] for t in ejecutar(con_tareas, "buscar_tareas", {"materia": "logica"})][:1] == [
        "100-1.1"
    ]
    assert [
        t["numero"] for t in ejecutar(con_tareas, "buscar_tareas", {"estado": "entregada"})
    ] == ["1.4"]
    assert [t["numero"] for t in ejecutar(con_tareas, "buscar_tareas", {"tipo": "examen"})] == [
        "1.3"
    ]
    assert ejecutar(con_tareas, "buscar_tareas", {"texto": "zzz"}) == []


def test_buscar_tareas_limita_resultados(con_tareas):
    con_tareas.storage.replace_estructura(
        "100",
        [
            EtapaItem(
                "E",
                "d",
                0,
                [TareaItem(f"1.{k}", f"Tarea {k}", "evidencia", 1.0, None, k) for k in range(40)],
            )
        ],
    )
    assert len(ejecutar(con_tareas, "buscar_tareas", {"texto": "tarea"})) == h.LIMITE_RESULTADOS


def test_ver_tarea_resume_el_detalle(con_tareas):
    rubrica = Rubrica(["Completa"], [RubricaCriterio("Explica bien", [RubricaNivel(3, "ok")])])
    con_tareas.storage.set_detalle(
        "100-1.1",
        DetalleTarea("T", "1.1", None, None, 2.0, None, "A" * 3000, "cont", "crit", rubrica),
    )
    con_tareas.storage.set_indicaciones("100-1.1", "Máximo 2 hojas")
    r = ejecutar(con_tareas, "ver_tarea", {"tarea_id": "100-1.1"})
    assert r["titulo"] == "Dimensión 1 - Ficha Técnica" and r["profesor"] == "PROFE UNO"
    assert r["criterios_rubrica"] == ["Explica bien"] and r["indicaciones"] == "Máximo 2 hojas"
    assert len(r["actividades"]) < 1600 and r["actividades"].endswith("(recortado)")
    assert r["tiene_generacion"] is False


def test_ver_tarea_inexistente_devuelve_error(con_tareas):
    assert "error" in ejecutar(con_tareas, "ver_tarea", {"tarea_id": "nada"})


def test_proximas_entregas(con_tareas):
    ids = [t["id"] for t in ejecutar(con_tareas, "proximas_entregas")]
    assert ids == ["100-1.1", "100-1.3"]
    todas = [t["id"] for t in ejecutar(con_tareas, "proximas_entregas", {"incluir_vencidas": True})]
    assert todas == ["100-1.1", "100-1.3", "100-1.2"]
    assert [t["id"] for t in ejecutar(con_tareas, "proximas_entregas", {"dias": 7})] == ["100-1.1"]
    assert len(ejecutar(con_tareas, "proximas_entregas", {"limite": 1})) == 1


def test_agregar_y_reemplazar_indicaciones(con_tareas):
    ejecutar(con_tareas, "agregar_indicaciones", {"tarea_id": "100-1.1", "texto": "Usar Arial"})
    r = ejecutar(
        con_tareas, "agregar_indicaciones", {"tarea_id": "100-1.1", "texto": "Sin portada"}
    )
    assert r["indicaciones"] == "Usar Arial\nSin portada"
    r = ejecutar(con_tareas, "reemplazar_indicaciones", {"tarea_id": "100-1.1", "texto": " Nuevo "})
    assert r["indicaciones"] == "Nuevo"
    assert "error" in ejecutar(con_tareas, "agregar_indicaciones", {"tarea_id": "x", "texto": "a"})


def test_crear_pdf_imagenes_desde_rutas(con_tareas, tmp_path):
    foto = tmp_path / "foto.jpg"
    foto.write_bytes(foto_bytes(tmp_path))
    r = ejecutar(con_tareas, "crear_pdf_imagenes", {"rutas": [str(foto)], "recortar": False})
    assert r["pdf_url"].startswith("/files/herramientas/") and r["ruta"].endswith(".pdf")
    malo = ejecutar(con_tareas, "crear_pdf_imagenes", {"rutas": [str(tmp_path / "no.jpg")]})
    assert "error" in malo


def test_generar_portada_suelta(con_tareas, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    r = ejecutar(con_tareas, "generar_portada", {"profesor": "DR. X", "aula": "88"})
    assert r["docx_url"].endswith("portada.docx") and r["ruta_pdf"].endswith("portada.pdf")
    texto = "".join(
        t.text
        for t in docx.Document(
            str(con_tareas.paths.data / r["docx_url"].removeprefix("/files/"))
        ).element.iter(qn("w:t"))
    )
    assert "DR. X" in texto and "88" in texto and "5V1" in texto
    assert "error" in ejecutar(con_tareas, "generar_portada", {"profesor": "  "})


def con_credenciales(state):
    state.storage.set_settings({"cuenta": "1"})
    state.credentials.set("1", "pw")


def test_sincronizar_exige_credenciales_y_no_duplica_jobs(con_tareas, monkeypatch):
    lanzados = []

    async def falso(state, ctx, modo="auto"):
        lanzados.append(modo)
        await asyncio.sleep(0.2)
        return {}

    monkeypatch.setattr(services, "run_sync", falso)
    assert "error" in ejecutar(con_tareas, "sincronizar")
    con_credenciales(con_tareas)

    async def escenario():
        a = await h.ejecutar(con_tareas, "sincronizar", {"modo": "incremental"})
        b = await h.ejecutar(con_tareas, "sincronizar", {})
        return a, b

    a, b = correr(escenario())
    assert a["tipo"] == "sync" and a["ya_estaba_corriendo"] is False
    assert b["job_id"] == a["job_id"] and b["ya_estaba_corriendo"] is True
    assert lanzados == ["incremental"]


def test_revisar_y_generar_lanzan_sus_jobs(con_tareas, monkeypatch):
    llamadas = []

    async def revisar(state, ctx):
        llamadas.append("revisar")

    async def generar(state, ctx, tarea_id, extra=None, portada=None):
        llamadas.append(("generar", tarea_id, extra))

    monkeypatch.setattr(services, "run_revisar_entregas", revisar)
    monkeypatch.setattr(services, "run_generar", generar)
    con_credenciales(con_tareas)

    async def escenario():
        a = await h.ejecutar(con_tareas, "revisar_entregas", {})
        b = await h.ejecutar(
            con_tareas, "generar_tarea", {"tarea_id": "100-1.1", "instrucciones_extra": "x"}
        )
        await asyncio.sleep(0.05)
        return a, b

    a, b = correr(escenario())
    assert a["tipo"] == "revisar_entregas" and b["tipo"] == "generar"
    assert llamadas == ["revisar", ("generar", "100-1.1", "x")]


def test_entregar_exige_confirmacion(con_tareas, monkeypatch):
    lanzados = []

    async def entregar(state, ctx, tarea_id):
        lanzados.append(tarea_id)

    monkeypatch.setattr(services, "run_entregar", entregar)
    with pytest.raises(h.ConfirmacionRequerida) as info:
        ejecutar(con_tareas, "entregar_tarea", {"tarea_id": "100-1.1"})
    assert info.value.accion == "entregar_tarea"
    assert info.value.argumentos == {"tarea_id": "100-1.1"}
    assert lanzados == []
    sin = ejecutar(con_tareas, "entregar_tarea", {"tarea_id": "100-1.1"}, confirmado=True)
    assert sin["error"].startswith("Genera el documento")

    base = con_tareas.paths.generaciones
    con_tareas.storage.set_generacion("100-1.1", "md", str(base / "a.docx"), str(base / "a.pdf"))

    async def escenario():
        r = await h.ejecutar(con_tareas, "entregar_tarea", {"tarea_id": "100-1.1"}, confirmado=True)
        await asyncio.sleep(0.05)
        return r

    r = correr(escenario())
    assert r["tipo"] == "entregar" and lanzados == ["100-1.1"]


def test_ejecutar_herramienta_desconocida_o_sin_argumentos(con_tareas):
    assert "No existe" in ejecutar(con_tareas, "borrar_todo")["error"]
    assert "Faltan argumentos" in ejecutar(con_tareas, "ver_tarea", {})["error"]
    assert (
        "Faltan argumentos"
        in ejecutar(con_tareas, "agregar_indicaciones", {"tarea_id": "x"})["error"]
    )
