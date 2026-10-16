import os
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from backend import config
from backend.core import images, modelos


def _buscar_modelo() -> Path | None:
    candidatos = []
    if os.environ.get("NMWFM_MODELO_RECORTE"):
        candidatos.append(Path(os.environ["NMWFM_MODELO_RECORTE"]))
    for base in (config.ROOT, *config.ROOT.parents[:4]):
        candidatos.append(base / "data" / "models" / config.MODELO_RECORTE_ARCHIVO)
    return next((c for c in candidatos if c.is_file()), None)


MODELO = _buscar_modelo()
pytestmark = pytest.mark.skipif(MODELO is None, reason="El modelo u2netp.onnx no está descargado")


def escena(base_mesa=(60, 90, 130), seed=0, ancho=1600, alto=1200):
    rng = np.random.default_rng(seed)
    mesa = np.zeros((alto, ancho, 3), np.float32)
    gradiente = np.linspace(0.7, 1.15, ancho, dtype=np.float32)[None, :, None]
    mesa[:] = np.array(base_mesa, np.float32) * gradiente
    veta = cv2.GaussianBlur(rng.normal(0, 1, (alto, 1)).astype(np.float32), (1, 41), 0)
    mesa += veta.reshape(alto, 1, 1) * 25
    mesa += rng.normal(0, 10, mesa.shape).astype(np.float32)
    mesa = np.clip(mesa, 0, 255).astype(np.uint8)

    hoja = np.full((1100, 800, 3), 238, np.uint8)
    for k, y in enumerate(range(90, 1050, 48)):
        texto = f"Lorem ipsum dolor sit amet {k}"
        cv2.putText(
            hoja, texto, (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 40), 2, cv2.LINE_AA
        )
    origen = np.float32([[0, 0], [799, 0], [799, 1099], [0, 1099]])
    destino = np.float32([[300, 130], [1230, 190], [1190, 1070], [250, 1010]])
    matriz = cv2.getPerspectiveTransform(origen, destino)
    plana = cv2.warpPerspective(hoja, matriz, (ancho, alto))
    mascara = cv2.warpPerspective(np.full((1100, 800), 255, np.uint8), matriz, (ancho, alto))
    sombra = np.roll(cv2.GaussianBlur(mascara, (61, 61), 0), (14, 14), (0, 1))
    imagen = (mesa * (1 - 0.35 * (sombra[..., None] / 255.0))).astype(np.uint8)
    imagen[mascara > 0] = plana[mascara > 0]
    imagen = imagen.astype(np.float32) + rng.normal(0, 6, imagen.shape)
    return np.clip(imagen, 0, 255).astype(np.uint8), destino


def iou(a: np.ndarray, b: np.ndarray, forma) -> float:
    ma = np.zeros(forma[:2], np.uint8)
    mb = np.zeros(forma[:2], np.uint8)
    cv2.fillPoly(ma, [np.round(a).astype(np.int32)], 1)
    cv2.fillPoly(mb, [np.round(b).astype(np.int32)], 1)
    return float((ma & mb).sum() / max((ma | mb).sum(), 1))


def mediana_ms(funcion, repeticiones=7) -> float:
    tiempos = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        funcion()
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return float(np.median(tiempos))


def test_hash_del_modelo_coincide_con_config():
    assert modelos._sha256(MODELO) == config.MODELO_RECORTE_SHA256


@pytest.mark.parametrize(
    "mesa", [(60, 90, 130), (185, 195, 205)], ids=["mesa_oscura", "mesa_clara"]
)
def test_modelo_real_recorta_la_hoja_con_directml_o_cpu(mesa, capsys):
    import onnxruntime as ort

    imagen, real = escena(mesa)
    detector = images.DetectorModelo(MODELO)
    detector.cuadrilatero(imagen)
    proveedores = detector._sesion.get_providers()
    if "DmlExecutionProvider" in ort.get_available_providers():
        assert proveedores[0] == "DmlExecutionProvider"

    cuadrilatero = detector.cuadrilatero(imagen)
    assert cuadrilatero is not None
    assert iou(cuadrilatero, real, imagen.shape) > 0.85
    ms_modelo = mediana_ms(lambda: detector.cuadrilatero(imagen))

    opencv = images.detect_page(imagen)
    iou_opencv = iou(opencv, real, imagen.shape) if opencv is not None else 0.0
    ms_opencv = mediana_ms(lambda: images.detect_page(imagen))
    with capsys.disabled():
        print(
            f"\n[{proveedores[0]}] modelo {ms_modelo:.1f} ms IoU "
            f"{iou(cuadrilatero, real, imagen.shape):.3f} | OpenCV {ms_opencv:.1f} ms IoU "
            f"{iou_opencv:.3f}"
        )
    assert ms_modelo < 2000


def test_crop_page_con_el_modelo_real_coincide_con_el_recorte_opencv():
    imagen, _ = escena()
    con_modelo, detectada = images.crop_page(imagen, images.DetectorModelo(MODELO))
    con_opencv, _ = images.crop_page(imagen)
    assert detectada
    for a, b in zip(con_modelo.shape[:2], con_opencv.shape[:2], strict=True):
        assert abs(a - b) / b < 0.05
    assert con_modelo.mean() > 150


def test_la_salida_del_modelo_es_una_mascara_normalizada():
    imagen, _ = escena()
    detector = images.DetectorModelo(MODELO)
    mascara = detector.mascara(imagen)
    assert mascara.shape == (images.MODEL_INPUT, images.MODEL_INPUT)
    assert set(np.unique(mascara)) <= {0, 255}
    proporcion = (mascara > 0).mean()
    assert 0.25 < proporcion < 0.8
    sesion = detector._obtener_sesion()
    assert sesion.get_inputs()[0].shape == [1, 3, images.MODEL_INPUT, images.MODEL_INPUT]
