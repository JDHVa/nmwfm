import contextlib
from pathlib import Path

_motor = None


def disponible() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def _obtener_motor():
    global _motor
    if _motor is None:
        from rapidocr_onnxruntime import RapidOCR

        _motor = RapidOCR()
    return _motor


def extraer_texto(ruta: Path, rotacion: int = 0) -> str:
    import numpy as np
    from PIL import Image

    imagen = Image.open(ruta).convert("RGB")
    if rotacion:
        imagen = imagen.rotate(-rotacion, expand=True)
    resultado, _ = _obtener_motor()(np.array(imagen))
    if not resultado:
        return ""
    lineas = []
    for _caja, texto, _confianza in sorted(resultado, key=lambda r: (r[0][0][1], r[0][0][0])):
        with contextlib.suppress(Exception):
            lineas.append(str(texto).strip())
    return "\n".join(ln for ln in lineas if ln)
