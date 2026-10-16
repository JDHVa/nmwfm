import unicodedata

from .. import config

PALABRAS_PRODUCTO = (
    ("ficha_tecnica", ("ficha tecnica", "ficha")),
    ("mapa_mental", ("mapa mental", "mapa conceptual")),
    ("cuadro_comparativo", ("cuadro comparativo", "tabla comparativa")),
    ("cuadro_sinoptico", ("cuadro sinoptico", "sinoptico")),
    ("linea_tiempo", ("linea del tiempo", "linea de tiempo")),
    ("infografia", ("infografia",)),
    ("articulo_opinion", ("articulo de opinion", "opinion")),
    ("ensayo", ("ensayo",)),
    ("presentacion", ("presentacion", "diapositivas")),
    ("diagrama", ("diagrama",)),
    ("informe", ("informe",)),
    ("reporte", ("reporte",)),
)
TIPOS_CON_DIAGRAMA = ("mapa_mental", "cuadro_sinoptico", "diagrama", "linea_tiempo")


def _plano(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def _buscar(texto: str) -> str | None:
    plano = _plano(texto)
    for tipo, palabras in PALABRAS_PRODUCTO:
        if any(p in plano for p in palabras):
            return tipo
    return None


def detectar_producto(titulo: str, actividades: str = "") -> str:
    return _buscar(titulo) or _buscar(actividades) or "generico"


def plantilla_producto(tipo: str) -> str:
    carpeta = config.directorio_prompts()
    ruta = carpeta / f"{tipo}.md"
    if not ruta.exists():
        ruta = carpeta / "generico.md"
    return ruta.read_text(encoding="utf-8").strip()
