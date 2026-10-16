import hashlib
import sys
import types

import cv2
import numpy as np
import pytest

from backend.core import images, modelos

from .asgi_client import MiniClient
from .test_images import synthetic_photo


class SesionFalsa:
    def __init__(self, mascara_fn):
        self.mascara_fn = mascara_fn
        self.entradas = []

    def get_inputs(self):
        return [types.SimpleNamespace(name="entrada")]

    def run(self, salidas, alimentos):
        tensor = alimentos["entrada"]
        self.entradas.append(tensor)
        return [self.mascara_fn(tensor)]


def mascara_de_la_hoja(photo: np.ndarray):
    hoja = (photo.mean(axis=2) > 100).astype("float32")
    pequena = cv2.resize(hoja, (images.MODEL_INPUT, images.MODEL_INPUT))
    salida = 0.05 + 0.9 * pequena
    return lambda tensor: salida.reshape(1, 1, images.MODEL_INPUT, images.MODEL_INPUT)


def detector(sesion):
    return images.DetectorModelo("modelo.onnx", fabrica=lambda ruta: sesion)


def test_el_modelo_recorta_la_hoja_sin_usar_opencv(monkeypatch):
    photo, (w, h) = synthetic_photo()
    sesion = SesionFalsa(mascara_de_la_hoja(photo))

    def prohibido(img):
        raise AssertionError("no debía usarse OpenCV")

    monkeypatch.setattr(images, "detect_page", prohibido)
    recortada, detectada = images.crop_page(photo, detector(sesion))
    assert detectada
    alto, ancho = recortada.shape[:2]
    assert abs(ancho - w) / w < 0.12 and abs(alto - h) / h < 0.12
    entrada = sesion.entradas[0]
    assert entrada.shape == (1, 3, 320, 320) and entrada.dtype == np.float32


def test_si_el_modelo_falla_cae_a_opencv():
    photo, (w, h) = synthetic_photo()

    def explota(ruta):
        raise RuntimeError("sin DirectML ni CPU")

    det = images.DetectorModelo("modelo.onnx", fabrica=explota)
    recortada, detectada = images.crop_page(photo, det)
    assert detectada and det.fallo is True
    assert abs(recortada.shape[1] - w) / w < 0.1


def test_si_el_modelo_no_ve_hoja_cae_a_opencv():
    photo, _ = synthetic_photo()
    sesion = SesionFalsa(
        lambda t: np.zeros((1, 1, images.MODEL_INPUT, images.MODEL_INPUT), dtype="float32")
    )
    recortada, detectada = images.crop_page(photo, detector(sesion))
    assert detectada and sesion.entradas


def test_sin_detector_se_comporta_como_antes():
    photo, _ = synthetic_photo()
    assert images.crop_page(photo)[1] is True


def test_mascara_no_cuadrada_usa_rectangulo_minimo():
    photo, _ = synthetic_photo()
    base = mascara_de_la_hoja(photo)
    det = detector(SesionFalsa(base))
    quad = det.cuadrilatero(photo)
    assert quad is not None and quad.shape == (4, 2)


def test_process_upload_con_detector(tmp_path):
    photo, _ = synthetic_photo()
    src = tmp_path / "foto.jpg"
    images.save_image(photo, src)
    det = detector(SesionFalsa(mascara_de_la_hoja(photo)))
    assert images.process_upload(src, tmp_path / "c.jpg", tmp_path / "t.jpg", det)


def modulo_ort(disponibles, falla_dml=False):
    class Sesion:
        def __init__(self, ruta, providers):
            if falla_dml and "DmlExecutionProvider" in providers:
                raise RuntimeError("dml no pudo iniciar")
            self.providers = providers

    return types.SimpleNamespace(
        get_available_providers=lambda: disponibles, InferenceSession=Sesion
    )


def test_proveedores_prefieren_directml_y_cpu_de_respaldo(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "onnxruntime", modulo_ort(["DmlExecutionProvider", "CPUExecutionProvider"])
    )
    assert images._proveedores() == ["DmlExecutionProvider", "CPUExecutionProvider"]
    monkeypatch.setitem(sys.modules, "onnxruntime", modulo_ort(["CPUExecutionProvider"]))
    assert images._proveedores() == ["CPUExecutionProvider"]


def test_si_directml_no_inicia_la_sesion_usa_cpu(monkeypatch):
    modulo = modulo_ort(["DmlExecutionProvider", "CPUExecutionProvider"], falla_dml=True)
    monkeypatch.setitem(sys.modules, "onnxruntime", modulo)
    assert images._crear_sesion("x.onnx").providers == ["CPUExecutionProvider"]


def test_detector_del_estado_respeta_setting_y_archivo(state):
    assert state.detector_recorte() is None
    ruta = modelos.ruta_modelo(state.paths.models)
    ruta.write_bytes(b"onnx")
    primero = state.detector_recorte()
    assert isinstance(primero, images.DetectorModelo) and state.detector_recorte() is primero
    state.storage.set_settings({"recorte_modelo": "opencv"})
    assert state.detector_recorte() is None
    state.storage.set_settings({"recorte_modelo": "auto"})
    primero.fallo = True
    assert state.detector_recorte() is None


def test_api_setting_y_disponibilidad(app, state):
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.get("/settings").json()["modelo_recorte_disponible"] is False
    assert client.put("/settings", json={"recorte_modelo": "opencv"}).json()["recorte_modelo"] == (
        "opencv"
    )
    assert client.put("/settings", json={"recorte_modelo": "raro"}).status_code == 422
    modelos.ruta_modelo(state.paths.models).write_bytes(b"onnx")
    assert client.get("/settings").json()["modelo_recorte_disponible"] is True


def test_descarga_verifica_hash_y_no_deja_basura(tmp_path):
    origen = tmp_path / "origen.onnx"
    origen.write_bytes(b"contenido del modelo")
    url = origen.as_uri()
    bueno = hashlib.sha256(b"contenido del modelo").hexdigest()
    carpeta = tmp_path / "models"
    destino = modelos.descargar_modelo(carpeta, url, bueno)
    assert destino.read_bytes() == b"contenido del modelo"

    origen.write_bytes(b"otro")
    assert modelos.descargar_modelo(carpeta, url, bueno) == destino
    assert destino.read_bytes() == b"contenido del modelo"

    with pytest.raises(modelos.ModeloError):
        modelos.descargar_modelo(carpeta, url, bueno, forzar=True)
    assert destino.read_bytes() == b"contenido del modelo"
    assert not list(carpeta.glob("*.part"))


def test_descarga_sin_hash_configurado_acepta_el_archivo(tmp_path):
    origen = tmp_path / "m.onnx"
    origen.write_bytes(b"abc")
    destino = modelos.descargar_modelo(tmp_path / "models", origen.as_uri(), "")
    assert destino.exists()
