import cv2
import numpy as np
import pytest
from PIL import Image

from backend.core import images


def synthetic_photo(angle: float = 12.0) -> tuple[np.ndarray, tuple[int, int]]:
    canvas = np.full((900, 1200, 3), 25, dtype=np.uint8)
    sheet = np.full((600, 450, 3), 240, dtype=np.uint8)
    for y in range(80, 560, 60):
        cv2.line(sheet, (40, y), (410, y), (120, 90, 60), 2)
    center = (600, 450)
    matrix = cv2.getRotationMatrix2D((225, 300), angle, 1.0)
    matrix[:, 2] += [center[0] - 225, center[1] - 300]
    rotated = cv2.warpAffine(
        sheet, matrix, (1200, 900), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0)
    )
    mask = cv2.warpAffine(
        np.full((600, 450), 255, np.uint8), matrix, (1200, 900), flags=cv2.INTER_LINEAR
    )
    canvas[mask > 0] = rotated[mask > 0]
    return canvas, (450, 600)


def test_detect_and_crop_rotated_sheet():
    photo, (w, h) = synthetic_photo()
    cropped, detected = images.crop_page(photo)
    assert detected
    ch, cw = cropped.shape[:2]
    assert abs(cw - w) / w < 0.1
    assert abs(ch - h) / h < 0.1
    assert cropped.mean() > 150


def test_no_page_returns_original():
    noise = np.random.default_rng(0).integers(0, 255, (300, 400, 3), dtype=np.uint8)
    flat = np.full((300, 400, 3), 128, dtype=np.uint8)
    out, detected = images.crop_page(flat)
    assert not detected and out is flat
    assert noise.shape == (300, 400, 3)


def test_rotate():
    img = np.zeros((10, 20, 3), dtype=np.uint8)
    assert images.rotate(img, 90).shape[:2] == (20, 10)
    assert images.rotate(img, 180).shape[:2] == (10, 20)
    assert images.rotate(img, 0) is img


def test_process_upload_and_thumb(tmp_path):
    photo, _ = synthetic_photo()
    src = tmp_path / "foto.jpg"
    images.save_image(photo, src)
    detected = images.process_upload(src, tmp_path / "crop.jpg", tmp_path / "thumb.jpg")
    assert detected
    with Image.open(tmp_path / "thumb.jpg") as thumb:
        assert max(thumb.size) <= images.THUMB_SIZE


def test_text_pages_wrap():
    pages = images.render_text_pages("palabra " * 2000)
    assert len(pages) >= 2
    assert pages[0].size == images.TEXT_PAGE_PX


def test_build_pdf(tmp_path):
    photo, _ = synthetic_photo()
    src = tmp_path / "foto.jpg"
    images.save_image(photo, src)
    refs = [
        images.InsumoRef(tipo="imagen", original=src, rotacion=90, usar_recorte=False),
        images.InsumoRef(tipo="texto", texto="Apuntes de prueba\nsegunda línea"),
    ]
    pdf = images.build_pdf(refs, tmp_path / "insumos.pdf")
    assert pdf.read_bytes().startswith(b"%PDF")
    import pikepdf

    with pikepdf.open(pdf) as doc:
        assert len(doc.pages) == 2


def test_build_pdf_empty(tmp_path):
    with pytest.raises(ValueError):
        images.build_pdf([], tmp_path / "x.pdf")
