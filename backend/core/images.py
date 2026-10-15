import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import img2pdf
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

A4_PT = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
MIN_AREA_RATIO = 0.2
MAX_AREA_RATIO = 0.97
WORK_SIZE = 900
THUMB_SIZE = 320
TEXT_PAGE_PX = (1240, 1754)
FONT_CANDIDATES = (
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
)


@dataclass
class InsumoRef:
    tipo: str
    original: Path | None = None
    recortada: Path | None = None
    texto: str | None = None
    rotacion: int = 0
    usar_recorte: bool = True


def load_image(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def save_image(img: np.ndarray, path: Path, quality: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix or ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError(f"No se pudo codificar la imagen {path.name}")
    buf.tofile(str(path))


def order_points(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype("float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
        dtype="float32",
    )


def _quad_from_mask(mask: np.ndarray, min_area: float) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    full_area = mask.shape[0] * mask.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(contour)
        if area < min_area:
            break
        if area > MAX_AREA_RATIO * full_area:
            continue
        hull = cv2.convexHull(contour)
        peri = cv2.arcLength(hull, True)
        for eps in (0.02, 0.03, 0.05, 0.08):
            approx = cv2.approxPolyDP(hull, eps * peri, True)
            if len(approx) == 4:
                return approx.reshape(4, 2)
    return None


def detect_page(img: np.ndarray) -> np.ndarray | None:
    h, w = img.shape[:2]
    scale = WORK_SIZE / max(h, w)
    small = (
        cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else img
    )
    scale = min(scale, 1.0)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 0)
    min_area = MIN_AREA_RATIO * small.shape[0] * small.shape[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    candidates = []
    edges = cv2.Canny(blur, 40, 130)
    candidates.append(
        cv2.morphologyEx(cv2.dilate(edges, kernel), cv2.MORPH_CLOSE, kernel, iterations=2)
    )
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates.append(cv2.morphologyEx(otsu, cv2.MORPH_OPEN, kernel, iterations=2))
    adaptive = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, -5
    )
    candidates.append(cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel, iterations=3))

    for mask in candidates:
        quad = _quad_from_mask(mask, min_area)
        if quad is not None:
            return (quad.astype("float32") / scale).astype("float32")
    return None


def warp_page(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = order_points(quad)
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 50 or height < 50:
        return img
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32"
    )
    matrix = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], dtype="float32"), dst)
    return cv2.warpPerspective(img, matrix, (width, height), flags=cv2.INTER_CUBIC)


def enhance(img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge((clahe.apply(l_chan), a_chan, b_chan)), cv2.COLOR_LAB2BGR)


def crop_page(img: np.ndarray) -> tuple[np.ndarray, bool]:
    quad = detect_page(img)
    if quad is None:
        return img, False
    warped = warp_page(img, quad)
    if warped is img:
        return img, False
    return enhance(warped), True


def rotate(img: np.ndarray, degrees: int) -> np.ndarray:
    degrees %= 360
    if degrees == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def process_upload(src: Path, recortada_out: Path, thumb_out: Path) -> bool:
    img = load_image(src)
    cropped, detected = crop_page(img)
    save_image(cropped, recortada_out)
    make_thumbnail(cropped, thumb_out)
    return detected


def make_thumbnail(img: np.ndarray, out: Path, size: int = THUMB_SIZE) -> None:
    h, w = img.shape[:2]
    scale = size / max(h, w)
    thumb = (
        cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else img
    )
    save_image(thumb, out, quality=80)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


def render_text_pages(texto: str, size: tuple[int, int] = TEXT_PAGE_PX) -> list[Image.Image]:
    width, height = size
    margin = 110
    font = _font(34)
    line_h = 50
    max_w = width - 2 * margin
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    lines: list[str] = []
    for raw in texto.replace("\r", "").split("\n"):
        words, current = raw.split(" "), ""
        for word in words:
            trial = f"{current} {word}".strip() if current else word
            if probe.textlength(trial, font=font) <= max_w:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)

    per_page = max(1, (height - 2 * margin) // line_h)
    pages = []
    for start in range(0, max(len(lines), 1), per_page):
        page = Image.new("RGB", size, "white")
        draw = ImageDraw.Draw(page)
        for i, line in enumerate(lines[start : start + per_page]):
            draw.text((margin, margin + i * line_h), line, fill="black", font=font)
        pages.append(page)
    return pages


def _jpeg_bytes(img: Image.Image | np.ndarray) -> bytes:
    if isinstance(img, np.ndarray):
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def build_pdf(insumos: Sequence[InsumoRef], out: Path) -> Path:
    pages: list[bytes] = []
    for ins in insumos:
        if ins.tipo == "texto":
            pages.extend(_jpeg_bytes(p) for p in render_text_pages(ins.texto or ""))
            continue
        path = ins.recortada if ins.usar_recorte and ins.recortada else ins.original
        if path is None or not Path(path).exists():
            continue
        pages.append(_jpeg_bytes(rotate(load_image(Path(path)), ins.rotacion)))
    if not pages:
        raise ValueError("No hay insumos para armar el PDF.")
    layout = img2pdf.get_layout_fun(A4_PT, fit=img2pdf.FitMode.into, auto_orient=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img2pdf.convert(pages, layout_fun=layout))
    return out
