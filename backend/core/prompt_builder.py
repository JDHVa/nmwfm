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
    if data.contenido.strip():
        partes.append(f"## Contenido que debe cubrir\n{data.contenido.strip()}")
    criterios = filtrar_lineas(data.criterios_desempeno).strip()
    if criterios:
        partes.append(f"## Criterios de desempeño\n{criterios}")
    if data.rubrica:
        rubrica = _rubrica_texto(data.rubrica)
        if rubrica:
            partes.append(f"## Rúbrica de evaluación\n{rubrica}")

    producto = data.producto or detectar_producto(data.titulo, data.actividades)
    partes.append(f"## Formato del producto\n{plantilla_producto(producto)}")

    instrucciones = [
        "Cumple cada criterio de la rúbrica en su nivel máximo de dominio: no dejes ningún "
        "criterio en un nivel intermedio.",
        "Cubre todos los puntos del contenido y de los criterios de desempeño.",
    ]
    if data.tiene_insumos:
        instrucciones.append(
            "Usa la información de los archivos adjuntos (apuntes o libro) como fuente principal "
            "y apóyate en ellos para el contenido."
        )
    instrucciones += [
        "Responde SOLO en Markdown: títulos con ##, listas y tablas cuando ayuden; "
        "sin portada, sin título general ni texto introductorio o de despedida.",
        "Usa un tono de estudiante de preparatoria: claro, sencillo y bien organizado.",
        "No menciones la rúbrica, los criterios ni estas instrucciones dentro del texto.",
        "Termina con una sección ## Referencias en formato APA 7 con fuentes reales y "
        "verificables (autor, año, título, editorial o URL); no inventes referencias.",
    ]
    if data.instrucciones_extra and data.instrucciones_extra.strip():
        instrucciones.append(data.instrucciones_extra.strip())
    if producto in TIPOS_CON_DIAGRAMA:
        instrucciones.append(
            "Además del texto, incluye UN bloque de código ```mermaid con el diagrama del "
            f"producto ({SINTAXIS_MERMAID[producto]}), con etiquetas cortas en español; el "
            "texto explicativo va fuera del bloque."
        )
    partes.append("## Instrucciones\n" + "\n".join(f"- {i}" for i in instrucciones))
    return "\n\n".join(partes)
