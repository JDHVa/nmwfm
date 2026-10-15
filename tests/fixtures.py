import re
from pathlib import Path

NEXUS_TXT = Path(__file__).resolve().parent.parent / "htmls" / "nexus" / "NEXUS.txt"


def _text() -> str:
    return NEXUS_TXT.read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    text = _text()
    i = text.index(start) + len(start)
    return text[i : text.index(end, i)]


def cards_html() -> str:
    return re.search(r"<app-cursos-card\b.*?</app-cursos-card>", _text(), re.S).group(0)


def portada_html() -> str:
    return re.search(r"<app-curso-portada\b.*?</app-curso-portada>", _text(), re.S).group(0)


def estructura_html() -> str:
    return re.search(
        r"<app-estructura-competencias\b.*?</app-estructura-competencias>", _text(), re.S
    ).group(0)


def detalle_html() -> str:
    return _between("SE DESPLIEGA TODO ESTO", "LO IMPORTANTE ES LA DESCRIPCION")


def rubrica_html() -> str:
    return _between("SECCION QUE ES RUBRICA", "SE DEBE DE CUMPLIR")
