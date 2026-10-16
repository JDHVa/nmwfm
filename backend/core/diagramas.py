import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

BLOQUE_MERMAID = re.compile(r"```mermaid[^\n]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
MARCADOR = "[[DIAGRAMA:{n}]]"
_ENCABEZADO_GRAFO = re.compile(r"^(?:graph|flowchart)\s*(TD|TB|LR|RL|BT)?", re.IGNORECASE)
_FLECHA = re.compile(r"\s*(?:-->|---|-\.->|==>|--o|--x)\s*(?:\|([^|]*)\|)?\s*")
_TEXTO_EN_ENLACE = re.compile(r"--\s+([^->|]+?)\s+-->")
_NODO = re.compile(
    r'^\s*([A-Za-z0-9_]+)\s*(?:\[\[?"?(.*?)"?\]?\]|\(\(?"?(.*?)"?\)?\)|\{"?(.*?)"?\}|>"?(.*?)"?\])?\s*$'
)
_FORMA = re.compile(r"^\w*[\(\[\{]+\"?(.*?)\"?[\)\]\}]+$")
_IGNORAR = ("subgraph", "end", "style", "classdef", "class ", "linkstyle", "%%", "click")
DIRECCION = {"TD": "TB", "TB": "TB", "LR": "LR", "RL": "RL", "BT": "BT"}


@dataclass
class Grafo:
    tipo: str
    direccion: str = "TB"
    nodos: dict[str, str] = field(default_factory=dict)
    aristas: list[tuple[str, str, str]] = field(default_factory=list)
    items: list[tuple[int, str]] = field(default_factory=list)


def extraer_bloques(markdown: str) -> list[str]:
    return [m.group(1) for m in BLOQUE_MERMAID.finditer(markdown)]


def _etiqueta(texto: str) -> str:
    texto = texto.strip()
    forma = _FORMA.match(texto)
    if forma:
        texto = forma.group(1)
    return re.sub(r"<br\s*/?>", "\n", texto).strip()


def _parsear_grafo(lineas: list[str], direccion: str) -> Grafo:
    grafo = Grafo(tipo="grafo", direccion=direccion)
    for linea in lineas:
        plano = linea.strip()
        if not plano or plano.lower().startswith(_IGNORAR):
            continue
        plano = _TEXTO_EN_ENLACE.sub(r"-->|\1|", plano)
        partes = _FLECHA.split(plano)
        tokens = partes[0::2]
        etiquetas = partes[1::2]
        ids = []
        for token in tokens:
            if "&" in token or not token.strip():
                continue
            m = _NODO.match(token)
            if m:
                nodo = m.group(1)
                texto = next((g for g in m.groups()[1:] if g), None)
                if texto or nodo not in grafo.nodos:
                    grafo.nodos[nodo] = _etiqueta(texto) if texto else nodo
            else:
                nodo = f"n{len(grafo.nodos)}"
                grafo.nodos[nodo] = _etiqueta(token)
            ids.append(nodo)
        for i in range(len(ids) - 1):
            etiqueta = (etiquetas[i] or "").strip() if i < len(etiquetas) else ""
            grafo.aristas.append((ids[i], ids[i + 1], etiqueta))
    return grafo


def _parsear_mindmap(lineas: list[str]) -> Grafo:
    grafo = Grafo(tipo="mindmap", direccion="LR")
    pila: list[tuple[int, str]] = []
    for linea in lineas:
        if not linea.strip() or linea.strip().startswith("%%"):
            continue
        nivel = len(linea) - len(linea.lstrip(" \t"))
        texto = _etiqueta(linea)
        nodo = f"n{len(grafo.nodos)}"
        grafo.nodos[nodo] = texto
        while pila and pila[-1][0] >= nivel:
            pila.pop()
        if pila:
            grafo.aristas.append((pila[-1][1], nodo, ""))
        grafo.items.append((len(pila), texto))
        pila.append((nivel, nodo))
    return grafo


def _parsear_timeline(lineas: list[str]) -> Grafo:
    grafo = Grafo(tipo="timeline", direccion="LR")
    anterior = None
    for linea in lineas:
        plano = linea.strip()
        if not plano or plano.startswith("%%"):
            continue
        minuscula = plano.lower()
        if minuscula.startswith("title"):
            grafo.items.append((0, plano[5:].strip()))
            continue
        if minuscula.startswith("section"):
            grafo.items.append((0, plano[7:].strip()))
            continue
        periodo, _, resto = plano.partition(":")
        eventos = [e.strip() for e in resto.split(":") if e.strip()]
        texto = "\n".join([periodo.strip(), *eventos])
        nodo = f"n{len(grafo.nodos)}"
        grafo.nodos[nodo] = texto
        if anterior:
            grafo.aristas.append((anterior, nodo, ""))
        grafo.items.append((0, periodo.strip()))
        grafo.items.extend((1, e) for e in eventos)
        anterior = nodo
    return grafo


def parsear_mermaid(codigo: str) -> Grafo | None:
    lineas = [ln.rstrip() for ln in codigo.strip("\n").splitlines()]
    lineas = [ln for ln in lineas if ln.strip()]
    if not lineas:
        return None
    cabecera = lineas[0].strip()
    minuscula = cabecera.lower()
    if minuscula.startswith("mindmap"):
        grafo = _parsear_mindmap(lineas[1:])
    elif minuscula.startswith("timeline"):
        grafo = _parsear_timeline(lineas[1:])
    else:
        m = _ENCABEZADO_GRAFO.match(cabecera)
        if not m:
            return None
        grafo = _parsear_grafo(lineas[1:], DIRECCION.get((m.group(1) or "TD").upper(), "TB"))
    return grafo if grafo.nodos else None


def _dot_texto(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def a_dot(grafo: Grafo) -> str:
    lineas = [
        "digraph G {",
        f"  rankdir={grafo.direccion}; dpi=150; nodesep=0.4; ranksep=0.6;",
        '  node [shape=box, style="rounded,filled", fillcolor="#eef3fb", color="#355c9a",'
        ' fontname="Arial", fontsize=12];',
        '  edge [color="#355c9a", fontname="Arial", fontsize=10];',
    ]
    for nodo, texto in grafo.nodos.items():
        lineas.append(f'  "{nodo}" [label="{_dot_texto(texto)}"];')
    for origen, destino, etiqueta in grafo.aristas:
        extra = f' [label="{_dot_texto(etiqueta)}"]' if etiqueta else ""
        lineas.append(f'  "{origen}" -> "{destino}"{extra};')
    lineas.append("}")
    return "\n".join(lineas)


def a_markdown(grafo: Grafo) -> str:
    if grafo.items:
        return "\n".join(f"{'  ' * nivel}- {texto}" for nivel, texto in grafo.items if texto)
    filas = ["| Origen | Relación | Destino |", "|---|---|---|"]
    for origen, destino, etiqueta in grafo.aristas:
        filas.append(
            f"| {grafo.nodos.get(origen, origen)} | {etiqueta or '→'} | "
            f"{grafo.nodos.get(destino, destino)} |"
        )
    if not grafo.aristas:
        filas.append("| " + " | ".join(["", "", ""]) + " |")
    return "\n".join(filas)


RUTAS_DOT = (
    r"C:\Program Files\Graphviz\bin\dot.exe",
    r"C:\Program Files (x86)\Graphviz\bin\dot.exe",
)


def buscar_dot() -> str | None:
    encontrado = shutil.which("dot")
    if encontrado:
        return encontrado
    return next((r for r in RUTAS_DOT if Path(r).exists()), None)


def _renderizar_con_binario(dot: str) -> bytes | None:
    binario = buscar_dot()
    if binario is None:
        return None
    try:
        resultado = subprocess.run(
            [binario, "-Tpng"], input=dot.encode("utf-8"), capture_output=True, check=False
        )
    except OSError:
        return None
    return resultado.stdout if resultado.returncode == 0 and resultado.stdout else None


def renderizar_png(dot: str) -> bytes | None:
    try:
        import graphviz

        return graphviz.Source(dot, engine="dot").pipe(format="png")
    except Exception:
        return _renderizar_con_binario(dot)


def procesar_diagramas(
    markdown: str, work_dir: Path, avisos: list[str] | None = None
) -> tuple[str, dict[str, Path]]:
    avisos = avisos if avisos is not None else []
    imagenes: dict[str, Path] = {}
    contador = 0

    def reemplazo(m: re.Match) -> str:
        nonlocal contador
        contador += 1
        grafo = parsear_mermaid(m.group(1))
        if grafo is None:
            avisos.append(f"Diagrama {contador}: no se pudo interpretar el código Mermaid.")
            return f"\n{m.group(1).strip()}\n"
        png = renderizar_png(a_dot(grafo))
        if png is None:
            avisos.append(
                f"Diagrama {contador}: no hay renderizador local (Graphviz); se muestra como lista."
            )
            return "\n" + a_markdown(grafo) + "\n"
        work_dir.mkdir(parents=True, exist_ok=True)
        ruta = work_dir / f"diagrama{contador}.png"
        ruta.write_bytes(png)
        marcador = MARCADOR.format(n=contador)
        imagenes[marcador] = ruta
        return f"\n{marcador}\n"

    return BLOQUE_MERMAID.sub(reemplazo, markdown), imagenes
