import cv2
import numpy as np
import pytest

from backend.core import images

ANCHO, ALTO = 1600, 1200
FOCAL = 1000.0
HOJA = (0.8, 1.1)
VERDADERO = HOJA[0] / HOJA[1]
POSES = [
    ((0.5, 0.35, 0.1), 1.0, (-0.3, -0.4)),
    ((0.2, -0.4, 0.3), 1.1, (-0.4, -0.5)),
    ((0.7, 0.1, -0.2), 1.0, (-0.3, -0.45)),
    ((0.1, 0.05, 0.0), 1.2, (-0.4, -0.55)),
]


def camara():
    return np.array([[FOCAL, 0, ANCHO / 2], [0, FOCAL, ALTO / 2], [0, 0, 1]], dtype="float64")


def _proyectar(rot, t):
    r, _ = cv2.Rodrigues(np.array(rot, dtype="float64"))
    esquinas = np.array(
        [[0, 0, 0], [HOJA[0], 0, 0], [HOJA[0], HOJA[1], 0], [0, HOJA[1], 0]], dtype="float64"
    )
    proyectado = (camara() @ ((r @ esquinas.T).T + t).T).T
    return proyectado[:, :2] / proyectado[:, 2:3]


def cuadrilatero(rot, tz, desplazamiento):
    t = np.array([desplazamiento[0], desplazamiento[1], tz], dtype="float64")
    for _ in range(4):
        centro = _proyectar(rot, t).mean(axis=0)
        t[0] += (ANCHO / 2 - centro[0]) * tz / FOCAL
        t[1] += (ALTO / 2 - centro[1]) * tz / FOCAL
    return _proyectar(rot, t).astype("float32")


def escena_fisica(pose):
    """Foto de una hoja de 0.8x1.1 con una cámara real simulada (focal 1000 px)."""
    rot, tz, desplazamiento = pose
    quad = cuadrilatero(rot, tz, desplazamiento)
    rng = np.random.default_rng(1)
    mesa = np.full((ALTO, ANCHO, 3), (55, 85, 120), np.uint8)
    mesa = np.clip(mesa + rng.normal(0, 8, mesa.shape), 0, 255).astype(np.uint8)
    hoja = np.full((1100, 800, 3), 240, np.uint8)
    for k, y in enumerate(range(90, 1050, 50)):
        cv2.putText(
            hoja, f"Linea de texto {k}", (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (40, 40, 40), 2
        )
    origen = np.float32([[0, 0], [799, 0], [799, 1099], [0, 1099]])
    homografia = cv2.getPerspectiveTransform(origen, quad)
    plana = cv2.warpPerspective(hoja, homografia, (ANCHO, ALTO))
    mascara = cv2.warpPerspective(np.full((1100, 800), 255, np.uint8), homografia, (ANCHO, ALTO))
    mesa[mascara > 0] = plana[mascara > 0]
    return mesa, quad


@pytest.mark.parametrize("pose", POSES)
def test_estimate_aspect_recupera_la_proporcion_real(pose):
    quad = cuadrilatero(*pose)
    ratio = images.estimate_aspect(quad, (ALTO, ANCHO))
    assert ratio is not None and abs(ratio - VERDADERO) / VERDADERO < 0.01


def test_estimate_aspect_no_depende_del_orden_de_los_puntos():
    quad = cuadrilatero(*POSES[0])
    revuelto = quad[[2, 0, 3, 1]]
    assert abs(images.estimate_aspect(revuelto, (ALTO, ANCHO)) - VERDADERO) < 0.01


def test_sin_perspectiva_no_se_estima_y_se_usan_los_lados():
    rectangulo = np.float32([[400, 300], [1000, 300], [1000, 1100], [400, 1100]])
    assert images.estimate_aspect(rectangulo, (ALTO, ANCHO)) is None
    img = np.full((ALTO, ANCHO, 3), 200, np.uint8)
    plana = images.warp_page(img, rectangulo)
    assert abs(plana.shape[1] / plana.shape[0] - 600 / 800) < 0.02


def test_focal_implausible_cae_al_respaldo():
    paralelogramo = np.float32([[400, 300], [1000, 320], [1000, 1120], [400, 1100]])
    assert images.estimate_aspect(paralelogramo, (ALTO, ANCHO)) is None


@pytest.mark.parametrize("pose", POSES)
def test_warp_page_devuelve_el_aspecto_correcto(pose):
    imagen, quad = escena_fisica(pose)
    plana = images.warp_page(imagen, quad)
    ratio = plana.shape[1] / plana.shape[0]
    assert abs(ratio - VERDADERO) / VERDADERO < 0.08


@pytest.mark.parametrize("pose", POSES)
def test_crop_page_de_punta_a_punta_con_perspectiva(pose):
    imagen, _ = escena_fisica(pose)
    recortada, detectada = images.crop_page(imagen)
    assert detectada
    ratio = recortada.shape[1] / recortada.shape[0]
    assert abs(ratio - VERDADERO) / VERDADERO < 0.08
    assert recortada.mean() > 150


def test_el_aspecto_antiguo_era_incorrecto_en_esta_escena():
    imagen, quad = escena_fisica(POSES[0])
    tl, tr, br, bl = images.order_points(quad)
    antes = max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)) / max(
        np.linalg.norm(tr - br), np.linalg.norm(tl - bl)
    )
    assert abs(antes - VERDADERO) / VERDADERO > 0.08
