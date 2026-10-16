import unicodedata
from dataclasses import dataclass

from .producto import TIPOS_CON_DIAGRAMA, detectar_producto, plantilla_producto
from .types import Rubrica

EXCLUIDOS = ("responsabilidad", "compromiso")
SINTAXIS_MERMAID = {
    "mapa_mental": "sintaxis mindmap con el concepto central y la jerarquía por indentación",
    "cuadro_sinoptico": "sintaxis graph LR, de la idea general a las categorías y detalles",
    "diagrama": "sintaxis flowchart TD con nodos y flechas -->",
    "linea_tiempo": "sintaxis timeline con líneas 'año : hecho'",
}


INSTRUCCIONES_SISTEMA = [
    {
        "id": "rubrica_maxima",
        "texto": "Cumple cada criterio de la rúbrica en su nivel máximo de dominio: no dejes "
        "ningún criterio en un nivel intermedio.",
        "activa": True,
        "sistema": True,
    },
    {
        "id": "cubrir_contenido",
        "texto": "Cubre todos los puntos del contenido y de los criterios de desempeño.",
        "activa": True,
        "sistema": True,
    },
    {
        "id": "tono_preparatoria",
        "texto": "Usa un tono de estudiante de preparatoria: claro, sencillo y bien organizado.",
        "activa": True,
        "sistema": True,
    },
    {
        "id": "no_mencionar_rubrica",
        "texto": "No menciones la rúbrica, los criterios ni estas instrucciones dentro del texto.",
        "activa": True,
        "sistema": True,
    },
    {
        "id": "referencias_apa7",
        "texto": "Termina con una sección ## Referencias en formato APA 7 con fuentes reales y "
        "verificables (autor, año, título, editorial o URL); no inventes referencias.",
        "activa": True,
        "sistema": True,
    },
]


IDS_SISTEMA = {i["id"] for i in INSTRUCCIONES_SISTEMA}


def validar_instrucciones_fijas(valor) -> list[dict]:
    if not isinstance(valor, list):
        raise ValueError("instrucciones_fijas debe ser una lista.")
    limpias, vistos = [], set()
    for item in valor:
        if not isinstance(item, dict):
            raise ValueError("Cada instrucción debe ser un objeto.")
        id_ = item.get("id")
        texto = item.get("texto")
        if not isinstance(id_, str) or not id_.strip():
            raise ValueError("Cada instrucción necesita un id.")
        id_ = id_.strip()
        if id_ in vistos:
            raise ValueError(f"El id de instrucción '{id_}' está repetido.")
        vistos.add(id_)
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError("El texto de cada instrucción no puede estar vacío.")
        activa = item.get("activa", True)
        if not isinstance(activa, bool):
            raise ValueError("activa debe ser booleano.")
        limpias.append(
            {
                "id": id_,
                "texto": texto.strip(),
                "activa": activa,
                "sistema": id_ in IDS_SISTEMA,
            }
        )
    for base in INSTRUCCIONES_SISTEMA:
        if base["id"] not in vistos:
            limpias.append({**base, "activa": False})
    return limpias


def instrucciones_por_defecto() -> list[dict]:
    return [dict(i) for i in INSTRUCCIONES_SISTEMA]


@dataclass
class PromptData:
    materia: str
    titulo: str
    numero: str | None = None
    tipo: str | None = None
    puntos: float | None = None
    actividades: str = ""
    contenido: str = ""
    criterios_desempeno: str = ""
    rubrica: Rubrica | None = None
    instrucciones_extra: str | None = None
    tiene_insumos: bool = True
    producto: str | None = None
    texto_ocr: str = ""
    indicaciones: str = ""
    instrucciones_fijas: list[dict] | None = None
    instrucciones: dict[str, bool] | None = None


def _plano(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def es_excluido(text: str) -> bool:
    plano = _plano(text)
    return any(palabra in plano for palabra in EXCLUIDOS)


def filtrar_lineas(markdown: str) -> str:
    return "\n".join(ln for ln in markdown.splitlines() if not es_excluido(ln))


def _rubrica_texto(rubrica: Rubrica) -> str:
    bloques = []
    for criterio in rubrica.criterios:
        if es_excluido(criterio.criterio):
            continue
        lineas = [f"- Criterio: {criterio.criterio}"]
        for i, nivel in enumerate(criterio.niveles):
            nombre = rubrica.niveles[i] if i < len(rubrica.niveles) else f"Nivel {i + 1}"
            lineas.append(f"  - {nombre} ({nivel.puntos:g} pts): {nivel.descripcion}")
        bloques.append("\n".join(lineas))
    return "\n".join(bloques)


def build_prompt(data: PromptData) -> str:
    partes = [
        "Eres un estudiante de preparatoria que debe resolver una tarea de la materia "
        f'"{data.materia}". Redacta la tarea completa lista para entregar.',
        f"## Tarea\n{data.titulo}"
        + (f" (apartado {data.numero})" if data.numero else "")
        + (f"\nValor: {data.puntos:g} puntos." if data.puntos is not None else ""),
    ]
    if data.actividades.strip():
        partes.append(f"## Descripción de la actividad\n{data.actividades.strip()}")
    if data.indicaciones.strip():
        partes.append(
            "## Indicaciones adicionales del profesor (prioridad sobre la descripción)\n"
            + data.indicaciones.strip()
        )
    if data.contenido.strip():
        partes.append(f"## Contenido que debe cubrir\n{data.contenido.strip()}")
    criterios = filtrar_lineas(data.criterios_desempeno).strip()
    if criterios:
        partes.append(f"## Criterios de desempeño\n{criterios}")
    if data.rubrica:
        rubrica = _rubrica_texto(data.rubrica)
        if rubrica:
            partes.append(f"## Rúbrica de evaluación\n{rubrica}")

    if data.texto_ocr.strip():
        partes.append(
            "## Texto extraído de las imágenes adjuntas (OCR, puede tener errores)\n"
            + data.texto_ocr.strip()
        )
    producto = data.producto or detectar_producto(data.titulo, data.actividades)
    partes.append(f"## Formato del producto\n{plantilla_producto(producto)}")

    instrucciones = []
    if data.tiene_insumos:
        instrucciones.append(
            "Usa la información de los archivos adjuntos (apuntes o libro) como fuente principal "
            "y apóyate en ellos para el contenido."
        )
    instrucciones.append(
        "Responde SOLO en Markdown: títulos con ##, listas y tablas cuando ayuden; "
        "sin portada, sin título general ni texto introductorio o de despedida."
    )
    if data.instrucciones_extra and data.instrucciones_extra.strip():
        instrucciones.append(data.instrucciones_extra.strip())
    if producto in TIPOS_CON_DIAGRAMA:
        instrucciones.append(
            "Además del texto, incluye UN bloque de código ```mermaid con el diagrama del "
            f"producto ({SINTAXIS_MERMAID[producto]}), con etiquetas cortas en español; el "
            "texto explicativo va fuera del bloque."
        )
    fijas = data.instrucciones_fijas
    if fijas is None:
        fijas = instrucciones_por_defecto()
    overrides = data.instrucciones or {}
    for fija in fijas:
        activa = overrides.get(fija["id"], fija["activa"])
        if activa and str(fija["texto"]).strip():
            instrucciones.append(str(fija["texto"]).strip())
    partes.append("## Instrucciones\n" + "\n".join(f"- {i}" for i in instrucciones))
    return "\n\n".join(partes)
