from backend import api, respaldo
from backend.core import documents

from .asgi_client import MiniClient
from .test_herramientas_sueltas import falso_pdf, foto_bytes, multipart

TID = "100-1.1"


def descargar(client, url):
    r = client.get(url)
    assert r.status_code == 200, f"{url} dio {r.status_code}"
    return r.content


def test_las_carpetas_publicas_cubren_todo_lo_que_se_sirve():
    assert {"insumos", "generaciones", "herramientas", "respaldos"} <= set(api.PUBLIC_DIRS)


def test_el_pdf_de_imagenes_se_puede_descargar(app, state, tmp_path):
    client = MiniClient(app, headers={"X-Token": "dev"})
    cuerpo, cabeceras = multipart([("a.jpg", foto_bytes(tmp_path))])
    r = client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras)
    assert descargar(client, r.json()["pdf_url"]).startswith(b"%PDF")


def test_la_portada_suelta_se_puede_descargar(app, state, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.post("/herramientas/portada", json={"profesor": "DR. X"})
    cuerpo = r.json()
    assert descargar(client, cuerpo["docx_url"]).startswith(b"PK")
    assert descargar(client, cuerpo["pdf_url"]).startswith(b"%PDF")


def test_la_vista_previa_de_portada_se_puede_descargar(app, seeded, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.get(f"/tareas/{TID}/portada-preview")
    assert descargar(client, r.json()["pdf_url"]).startswith(b"%PDF")


def test_el_respaldo_se_puede_descargar(app, seeded):
    client = MiniClient(app, headers={"X-Token": "dev"})
    creado = client.post("/respaldo").json()
    assert descargar(client, creado["url"]).startswith(b"PK")
    assert respaldo.carpeta(seeded).name == "respaldos"


def test_el_token_tambien_vale_por_query_para_los_enlaces(app, state, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    cliente = MiniClient(app, headers={"X-Token": "dev"})
    url = cliente.post("/herramientas/portada", json={"profesor": "P"}).json()["pdf_url"]
    sin_cabecera = MiniClient(app)
    assert sin_cabecera.get(url).status_code in (200, 401, 403)
    assert sin_cabecera.get(f"{url}?token=dev").status_code == 200


def test_lo_sensible_sigue_sin_servirse(app, state):
    client = MiniClient(app, headers={"X-Token": "dev"})
    (state.paths.data / "browser_profile").mkdir(exist_ok=True)
    (state.paths.data / "browser_profile" / "Cookies").write_text("x")
    assert client.get("/files/browser_profile/Cookies").status_code == 404
    assert client.get("/files/nmwfm.db").status_code == 404
    assert client.get("/files/herramientas/../nmwfm.db").status_code == 404
