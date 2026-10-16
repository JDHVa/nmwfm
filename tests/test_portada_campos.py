import asyncio
from datetime import datetime

from backend import services
from backend.asistente import herramientas as h
from backend.core import documents

from .asgi_client import MiniClient
from .test_ajustes_finales import falso_pdf, texto_docx
from .test_services import TID


def test_settings_de_portada_editables(app, state):
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.put(
        "/settings",
        json={"aula": " 12 ", "grupo": "6B", "turno": "VESPERTINO", "especialidad": "X"},
    )
    body = r.json()
    assert r.status_code == 200
    assert (body["aula"], body["grupo"], body["turno"], body["especialidad"]) == (
        "12",
        "6B",
        "VESPERTINO",
        "X",
    )
    assert client.put("/settings", json={"aula": 5}).status_code == 422


def test_settings_vacios_caen_al_valor_por_defecto_en_la_portada(seeded, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    seeded.storage.set_settings({"aula": "", "grupo": "   "})
    docx_path, _ = services._portada_archivos(seeded, {"profesor": "P"})
    texto = texto_docx(docx_path)
    assert "144" in texto and "5V1" in texto


def test_fecha_de_la_portada_siempre_es_hoy(seeded, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    monkeypatch.setattr(services, "ahora_monterrey", lambda: datetime(2027, 1, 9, 10, 0))
    docx_path, _ = services._portada_archivos(seeded, {"profesor": "P", "fecha": "2020-01-01"})
    assert "A 9 DE ENERO DEL 2027" in texto_docx(docx_path)


def test_profesores_distintos_con_sus_materias(app, seeded):
    st = seeded.storage
    st.set_portada("100", "PROFE UNO", None)
    r = MiniClient(app, headers={"X-Token": "dev"}).get("/profesores")
    assert r.status_code == 200
    assert r.json() == [{"nombre": "PROFE UNO", "materias": [st.get_materia("100")["nombre"]]}]


def test_profesores_ignora_nulos_y_agrupa(app, seeded):
    st = seeded.storage
    st.set_portada("100", "PROFE UNO", None)
    st._db.execute(
        "INSERT INTO materias(id, nombre, profesor, orden) VALUES('101', 'Otra', 'PROFE UNO', 1)"
    )
    st._db.execute("INSERT INTO materias(id, nombre, orden) VALUES('102', 'Sin', 2)")
    r = MiniClient(app, headers={"X-Token": "dev"}).get("/profesores")
    assert len(r.json()) == 1 and len(r.json()[0]["materias"]) == 2


def test_generar_tarea_pasa_la_portada(seeded, monkeypatch):
    recibido = {}

    async def falso(state, ctx, tarea_id, extra, portada=None, instrucciones=None):
        recibido["portada"] = portada
        return {}

    monkeypatch.setattr(services, "run_generar", falso)

    async def escenario():
        await h.ejecutar(
            seeded,
            "generar_tarea",
            {"tarea_id": TID, "portada": {"aula": "9", "titulo": "x", "fecha": "y"}},
        )
        await asyncio.sleep(0.1)

    asyncio.run(escenario())
    assert recibido["portada"] == {"aula": "9"}
