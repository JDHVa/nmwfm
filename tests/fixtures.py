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


ENTREGAR_TXT = Path(__file__).resolve().parent.parent / "htmls" / "nexus" / "entregar.txt"


def entregar_html() -> str:
    text = ENTREGAR_TXT.read_text(encoding="utf-8")
    return re.search(r"<mat-tab-group\b.*?</mat-tab-group>", text, re.S).group(0)


SNACKBAR_EXITO = (
    '<snack-bar-container class="mat-snack-bar-container snackbar-success">'
    '<simple-snack-bar class="mat-simple-snackbar">'
    "<span>La Tarea ha sido cargada y entregada con éxito</span>"
    '<div class="mat-simple-snackbar-action"><button class="mat-button">'
    '<span class="mat-button-wrapper">X</span></button></div>'
    "</simple-snack-bar></snack-bar-container>"
)


ENTREGADO_TXT = Path(__file__).resolve().parent.parent / "htmls" / "nexus" / "tareas_entregado.txt"


def entregas_tabla_html() -> str:
    return re.search(
        r"<table\b[^>]*mat-table.*?</table>", ENTREGADO_TXT.read_text(encoding="utf-8"), re.S
    ).group(0)


def entregas_vacio_html() -> str:
    return re.search(
        r"<div[^>]*>(?:(?!<div).)*?No se encontraron Entregas</div></div>",
        ENTREGADO_TXT.read_text(encoding="utf-8"),
        re.S,
    ).group(0)


def pestanas_entregas_html() -> str:
    return re.search(r"<nav\b.*?</nav>", ENTREGADO_TXT.read_text(encoding="utf-8"), re.S).group(0)


PIA_TXT = Path(__file__).resolve().parent.parent / "htmls" / "nexus" / "pia.txt"


def _pia_tramo(inicio: str, fin: str | None) -> str:
    texto = PIA_TXT.read_text(encoding="utf-8", errors="replace")
    i = texto.index(inicio) + len(inicio)
    return texto[i : texto.index(fin, i)] if fin else texto[i:]


def pia_item_html() -> str:
    return _pia_tramo("AQUI ACCEDES AL PIA", "AL ABRIRLO")


def pia_pestanas_html() -> str:
    return _pia_tramo("AL ABRIRLO SALE ESTO7", "AQUI ESTAN")


def pia_datos_html() -> str:
    return _pia_tramo("AQUI ESTAN LOS DAATOS", "AQUI LA RUBCIRCA")


def pia_rubrica_html() -> str:
    return _pia_tramo("AQUI LA RUBCIRCA", None)
