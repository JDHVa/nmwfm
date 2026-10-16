import asyncio
import json

import numpy as np
import pikepdf
from pikepdf import PdfImage
from PIL import Image

from backend import mcp, services
from backend.asistente import herramientas as h
from backend.core import documents

from .asgi_client import MiniClient

COLORES = [(220, 30, 30), (30, 200, 30), (30, 30, 220)]


def imagen_de_color(ruta, color):
    Image.new("RGB", (600, 800), color).save(ruta, quality=95)
    return ruta


def rutas_de_colores(tmp_path):
    return [imagen_de_color(tmp_path / f"{i}.jpg", c) for i, c in enumerate(COLORES)]


def color_de_pagina(pagina) -> tuple[int, int, int]:
    imagen = PdfImage(next(iter(pagina.images.values()))).as_pil_image().convert("RGB")
    return tuple(int(v) for v in np.asarray(imagen).reshape(-1, 3).mean(axis=0).round())


def dominante(color):
    return int(np.argmax(color))


def cover_falso(docx_path, pdf_path):
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with pikepdf.Pdf.new() as pdf:
        pdf.add_blank_page(page_size=(300, 400))
        pdf.save(pdf_path)
    return pdf_path


def abrir(ruta):
    return pikepdf.Pdf.open(ruta)


def test_una_pagina_por_imagen_en_el_orden_dado(state, tmp_path):
    rutas = rutas_de_colores(tmp_path)
    pdf = services.crear_pdf_imagenes(state, rutas, recortar=False)
    with abrir(pdf) as doc:
        assert len(doc.pages) == 3
        assert [dominante(color_de_pagina(p)) for p in doc.pages] == [0, 1, 2]
    invertido = services.crear_pdf_imagenes(state, rutas[::-1], recortar=False)
    with abrir(invertido) as doc:
        assert [dominante(color_de_pagina(p)) for p in doc.pages] == [2, 1, 0]


def test_con_recorte_sigue_siendo_una_pagina_por_imagen_en_orden(state, tmp_path):
    pdf = services.crear_pdf_imagenes(state, rutas_de_colores(tmp_path), recortar=True)
    with abrir(pdf) as doc:
        assert len(doc.pages) == 3
        assert [dominante(color_de_pagina(p)) for p in doc.pages] == [0, 1, 2]


def test_la_portada_va_como_primera_pagina(state, tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", cover_falso)
    pdf = services.crear_pdf_imagenes(
        state,
        rutas_de_colores(tmp_path),
        recortar=False,
        portada={"profesor": "DRA. X", "materia": "Física", "titulo": "Práctica 1"},
    )
    with abrir(pdf) as doc:
        assert len(doc.pages) == 4
        assert [float(v) for v in doc.pages[0].MediaBox] == [0, 0, 300, 400]
        assert [dominante(color_de_pagina(p)) for p in list(doc.pages)[1:]] == [0, 1, 2]


def test_sin_portada_solo_trae_imagenes(state, tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setattr(documents, "export_pdf", lambda *a: llamadas.append(1))
    pdf = services.crear_pdf_imagenes(state, rutas_de_colores(tmp_path), recortar=False)
    with abrir(pdf) as doc:
        assert len(doc.pages) == 3 and llamadas == []


def test_la_portada_exige_profesor(state, tmp_path):
    try:
        services.crear_pdf_imagenes(
            state, rutas_de_colores(tmp_path), recortar=False, portada={"materia": "x"}
        )
    except services.ApiError as exc:
        assert exc.status == 422
    else:
        raise AssertionError("debía fallar")


def multipart_con_campos(partes, campos):
    limite = "----lim"
    cuerpo = b""
    for nombre, valor in campos.items():
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


def partes(tmp_path):
    return [(f"{i}.jpg", r.read_bytes()) for i, r in enumerate(rutas_de_colores(tmp_path))]


def test_api_con_portada_y_descarga(app, tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", cover_falso)
    client = MiniClient(app, headers={"X-Token": "dev"})
    cuerpo, cabeceras = multipart_con_campos(
        partes(tmp_path),
        {"recortar": "false", "portada": json.dumps({"profesor": "DR. X", "fecha": "2026-12-01"})},
    )
    r = client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras)
    assert r.status_code == 200, r.content
    descarga = client.get(r.json()["pdf_url"])
    assert descarga.status_code == 200 and descarga.content.startswith(b"%PDF")
    destino = tmp_path / "bajado.pdf"
    destino.write_bytes(descarga.content)
    with abrir(destino) as doc:
        assert len(doc.pages) == 4


def test_api_sin_portada_y_errores_de_portada(app, tmp_path):
    client = MiniClient(app, headers={"X-Token": "dev"})
    cuerpo, cabeceras = multipart_con_campos(partes(tmp_path), {"recortar": "false"})
    r = client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras)
    destino = tmp_path / "sin.pdf"
    destino.write_bytes(client.get(r.json()["pdf_url"]).content)
    with abrir(destino) as doc:
        assert len(doc.pages) == 3
    for malo in ("{no es json", json.dumps(["x"]), json.dumps({"materia": "m"})):
        cuerpo, cabeceras = multipart_con_campos(partes(tmp_path), {"portada": malo})
        r = client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras)
        assert r.status_code == 422, malo


def test_api_portada_con_word_caido_da_502(app, tmp_path, monkeypatch):
    def falla(docx_path, pdf_path):
        raise RuntimeError("Word no disponible")

    monkeypatch.setattr(documents, "export_pdf", falla)
    client = MiniClient(app, headers={"X-Token": "dev"})
    cuerpo, cabeceras = multipart_con_campos(
        partes(tmp_path), {"recortar": "false", "portada": json.dumps({"profesor": "P"})}
    )
    r = client.post("/herramientas/pdf", content=cuerpo, headers=cabeceras)
    assert r.status_code == 502 and r.json()["error"]["code"] == "sin_word"


def test_la_herramienta_del_asistente_acepta_portada(state, tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "export_pdf", cover_falso)
    rutas = [str(r) for r in rutas_de_colores(tmp_path)]
    resultado = asyncio.run(
        h.ejecutar(
            state,
            "crear_pdf_imagenes",
            {"rutas": rutas, "recortar": False, "portada": {"profesor": "DR. X"}},
        )
    )
    with abrir(resultado["ruta"]) as doc:
        assert len(doc.pages) == 4
    esquema = h.HERRAMIENTAS["crear_pdf_imagenes"].esquema()["function"]["parameters"]
    assert esquema["properties"]["portada"]["required"] == ["profesor"]


def test_el_mcp_expone_el_parametro_portada(state):
    herramientas = asyncio.run(mcp.build_server(state).list_tools())
    esquema = next(t for t in herramientas if t.name == "crear_pdf_imagenes").inputSchema
    assert "portada" in esquema["properties"]
