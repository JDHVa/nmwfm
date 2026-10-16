from datetime import datetime
from pathlib import Path

import docx
from docx.oxml.ns import qn

from backend import services
from backend.core import documents, images

from .asgi_client import MiniClient
from .test_images import synthetic_photo


def multipart(partes, campos=None):
    limite = "----lim"
    cuerpo = b""
    for nombre, valor in (campos or {}).items():
        cuerpo += (
            f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"\r\n\r\n{valor}\r\n'
        ).encode()
    for nombre_archivo, datos in partes:
        cuerpo += (
            (
                f'--{limite}\r\nContent-Disposition: form-data; name="files[]"; '
                f'filename="{nombre_archivo}"\r\nContent-Type: image/jpeg\r\n\r\n'
            ).encode()
            + datos
            + b"\r\n"
        )
    cuerpo += f"--{limite}--\r\n".encode()
    return cuerpo, {"content-type": f"multipart/form-data; boundary={limite}"}


def foto_bytes(tmp_path, nombre="f.jpg") -> bytes:
    photo, _ = synthetic_photo()
    ruta = tmp_path / nombre
    images.save_image(photo, ruta)
    return ruta.read_bytes()


def ruta_de(state, url: str) -> Path:
    return state.paths.data / url.removeprefix("/files/")


def test_pdf_con_recorte_por_defecto(app, state, tmp_path, monkeypatch):
    llamadas = []
    real = images.process_upload

    def espia(*args, **kw):
        llamadas.append(1)
        return real(*args, **kw)

    monkeypatch.setattr(images, "process_upload", espia)
    client = MiniClient(app, headers={"X-Token": "dev"})
    cuerpo, cabeceras = multipart(
        [("a.jpg", foto_bytes(tmp_path)), ("b.jpg", foto_bytes(tmp_path))]
    )
    r = client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras)
    assert r.status_code == 200, r.content
    pdf = ruta_de(state, r.json()["pdf_url"])
    assert pdf.parent == state.paths.herramientas and pdf.read_bytes().startswith(b"%PDF")
    assert len(llamadas) == 2


def test_pdf_sin_recorte_por_campo_o_por_query(app, state, tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setattr(images, "process_upload", lambda *a, **k: llamadas.append(1))
    client = MiniClient(app, headers={"X-Token": "dev"})
    cuerpo, cabeceras = multipart([("a.jpg", foto_bytes(tmp_path))], {"recortar": "false"})
    assert client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras).status_code == 200
    cuerpo, cabeceras = multipart([("a.jpg", foto_bytes(tmp_path))])
    r = client.post("/herramientas/pdf?recortar=false", content=cuerpo, headers=cabeceras)
    assert r.status_code == 200 and llamadas == []


def test_pdf_errores(app, tmp_path):
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.post("/herramientas/pdf", json={}).status_code == 400
    cuerpo, cabeceras = multipart([("nota.txt", b"hola")])
    r = client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras)
    assert r.status_code == 400 and r.json()["error"]["code"] == "imagen_invalida"
    cuerpo, cabeceras = multipart([])
    assert client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras).status_code == 400


def test_servicio_crear_pdf_desde_rutas(state, tmp_path):
    foto = tmp_path / "x.jpg"
    foto.write_bytes(foto_bytes(tmp_path))
    pdf = services.crear_pdf_imagenes(state, [foto], recortar=False)
    assert pdf.read_bytes().startswith(b"%PDF")


def texto_docx(ruta) -> str:
    return "".join(t.text for t in docx.Document(str(ruta)).element.iter(qn("w:t")))


def falso_pdf(docx_path, pdf_path):
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF")
    return pdf_path


def test_portada_con_datos_arbitrarios(app, state, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    state.storage.set_settings({"nombre": "Ana Prueba", "matricula": "1999"})
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.post(
        "/herramientas/portada",
        json={"profesor": "DRA. LÓPEZ", "aula": "7", "grupo": "9X", "fecha": "2026-12-24"},
    )
    assert r.status_code == 200, r.content
    cuerpo = r.json()
    texto = texto_docx(ruta_de(state, cuerpo["docx_url"]))
    assert "DRA. LÓPEZ" in texto and "Ana Prueba" in texto and "1999" in texto
    assert "DE DICIEMBRE DEL 2026" not in texto
    assert "7" in texto and "9X" in texto and "MATUTINO" in texto
    assert "Materia:" not in texto and "Tarea:" not in texto
    assert ruta_de(state, cuerpo["pdf_url"]).exists()
    assert ruta_de(state, cuerpo["docx_url"]).parent.parent == state.paths.herramientas


def test_portada_fecha_por_defecto_es_hoy_en_monterrey(app, state, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    monkeypatch.setattr(services, "ahora_monterrey", lambda: datetime(2026, 3, 2, 23, 30))
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.post("/herramientas/portada", json={"profesor": "P"})
    texto = texto_docx(ruta_de(state, r.json()["docx_url"]))
    assert "A 2 DE MARZO DEL 2026" in texto and "Materia:" not in texto


def test_portada_usa_los_ajustes_para_omitidos_y_vacios(app, state, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", falso_pdf)
    state.storage.set_settings({"aula": "300", "turno": "NOCTURNO", "especialidad": "Redes"})
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = client.post("/herramientas/portada", json={"profesor": "P", "grupo": "  "})
    texto = texto_docx(ruta_de(state, r.json()["docx_url"]))
    assert "300" in texto and "NOCTURNO" in texto and "Redes" in texto and "5V1" in texto
    assert "(AULA)" not in texto and "(GRUPO)" not in texto


def test_portada_errores(app, monkeypatch):
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.post("/herramientas/portada", json={"profesor": "  "}).status_code == 422
    assert client.post("/herramientas/portada", json={}).status_code == 422

    def falla(docx_path, pdf_path):
        raise RuntimeError("Word no disponible")

    monkeypatch.setattr(documents, "export_pdf", falla)
    r = client.post("/herramientas/portada", json={"profesor": "P"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "sin_word"
