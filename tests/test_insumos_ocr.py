import asyncio

from PIL import Image

from backend import services
from backend.core import ocr

from .test_services import TID, FakeGemini, correr, listo  # noqa: F401


def imagen(ruta, color="white"):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (60, 40), color).save(ruta)
    return ruta


class MotorFalso:
    def __call__(self, arreglo):
        return (
            [
                [[[0, 50], [10, 50], [10, 60], [0, 60]], "segunda línea", 0.9],
                [[[0, 5], [10, 5], [10, 15], [0, 15]], "primera línea", 0.9],
            ],
            None,
        )


def test_extraer_texto_ordena_por_posicion(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "_motor", MotorFalso())
    assert ocr.extraer_texto(imagen(tmp_path / "a.png"), 90) == "primera línea\nsegunda línea"


def test_extraer_texto_sin_resultados(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "_motor", lambda arr: (None, None))
    assert ocr.extraer_texto(imagen(tmp_path / "a.png")) == ""


class CtxRegistro:
    def __init__(self):
        self.mensajes = []

    async def log(self, mensaje, nivel="info"):
        self.mensajes.append(mensaje)

    async def update(self, *a, **kw):
        return None


def agregar_imagen(state, tmp_path):
    original = imagen(state.paths.insumos / TID / "o.png")
    recortada = imagen(state.paths.insumos / TID / "c.jpg")
    return state.storage.add_insumo(
        TID, "imagen", original_path=str(original), recortada_path=str(recortada)
    )


def test_sin_ocr_instalado_avisa_y_sigue(seeded, tmp_path, monkeypatch):
    agregar_imagen(seeded, tmp_path)
    monkeypatch.setattr(ocr, "disponible", lambda: False)
    ctx = CtxRegistro()
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == ""
    assert any("rapidocr-onnxruntime" in m for m in ctx.mensajes)


def test_ocr_se_cachea_y_se_invalida_al_rotar(seeded, tmp_path, monkeypatch):
    fila = agregar_imagen(seeded, tmp_path)
    llamadas = []

    def falso(ruta, rotacion=0):
        llamadas.append(rotacion)
        return f"texto {rotacion}"

    monkeypatch.setattr(ocr, "disponible", lambda: True)
    monkeypatch.setattr(ocr, "extraer_texto", falso)
    ctx = CtxRegistro()
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == "texto 0"
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == "texto 0"
    assert llamadas == [0]
    assert seeded.insumo_public(seeded.storage.get_insumo(fila["id"]))["ocr_texto"] == "texto 0"
    seeded.storage.update_insumo(fila["id"], rotacion=90)
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == "texto 90"
    assert llamadas == [0, 90]


def test_generar_agrega_el_texto_ocr_al_prompt(listo, tmp_path, monkeypatch):  # noqa: F811
    agregar_imagen(listo, tmp_path)
    prompts = []

    class Captura(FakeGemini):
        async def generar(self, prompt, pdf_path, hooks):
            prompts.append(prompt)
            return "## R\n\nT"

    listo.gemini = Captura()
    monkeypatch.setattr(ocr, "disponible", lambda: True)
    monkeypatch.setattr(ocr, "extraer_texto", lambda ruta, rotacion=0: "Apunte: ley de Ohm")
    job = correr(listo)
    assert job.estado == "ok", job.mensaje
    assert "Texto extraído de las imágenes" in prompts[0] and "ley de Ohm" in prompts[0]
