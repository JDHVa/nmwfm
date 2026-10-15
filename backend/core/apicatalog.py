import asyncio
import contextlib
import json
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

HOST_NEXUS = "plataformanexus.uanl.mx"
TIPOS_API = ("xhr", "fetch")
_SEGMENTO_ID = re.compile(r"^(?:\d{3,}|[0-9a-fA-F]{16,}|[\w-]{24,})$")
MAX_CLAVES = 30
MAX_PROFUNDIDAD = 4


def plantilla_url(url: str) -> str:
    partes = urlsplit(url)
    ruta = "/".join("{id}" if _SEGMENTO_ID.match(s) else s for s in partes.path.split("/"))
    claves = sorted({p.split("=", 1)[0] for p in partes.query.split("&") if p})
    consulta = "?" + "&".join(claves) if claves else ""
    return f"{partes.netloc}{ruta}{consulta}"


def forma(dato, profundidad: int = 0):
    if isinstance(dato, dict):
        if profundidad >= MAX_PROFUNDIDAD:
            return "{...}"
        return {k: forma(v, profundidad + 1) for k, v in list(dato.items())[:MAX_CLAVES]}
    if isinstance(dato, list):
        if not dato or profundidad >= MAX_PROFUNDIDAD:
            return [f"len={len(dato)}"]
        return [forma(dato[0], profundidad + 1), f"len={len(dato)}"]
    return type(dato).__name__


class Catalogo:
    def __init__(self, directorio: Path | None = None, capacidad: int = 200):
        self.directorio = directorio
        self.endpoints: dict[tuple[str, str, int], dict] = {}
        self.cuerpos: deque = deque(maxlen=capacidad)
        self._tareas: set[asyncio.Task] = set()

    def adjuntar(self, page) -> None:
        page.on("response", self._al_responder)

    def _al_responder(self, response) -> None:
        tarea = asyncio.get_running_loop().create_task(self.procesar(response))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def procesar(self, response) -> None:
        with contextlib.suppress(Exception):
            peticion = response.request
            if peticion.resource_type not in TIPOS_API or HOST_NEXUS not in response.url:
                return
            cuerpo = None
            with contextlib.suppress(Exception):
                cuerpo = await response.json()
            plantilla = plantilla_url(response.url)
            clave = (peticion.method, plantilla, response.status)
            entrada = self.endpoints.setdefault(
                clave,
                {
                    "metodo": peticion.method,
                    "url": plantilla,
                    "status": response.status,
                    "veces": 0,
                    "forma": forma(cuerpo) if cuerpo is not None else "no-json",
                },
            )
            entrada["veces"] += 1
            if cuerpo is not None:
                self.cuerpos.append((time.monotonic(), response.url, cuerpo))

    def buscar(self, patron: str, desde: float = 0.0) -> list:
        regex = re.compile(patron)
        return [c for t, u, c in self.cuerpos if t >= desde and regex.search(u)]

    async def esperar_json(self, patron: str, desde: float, timeout: float = 10.0):
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            encontrados = self.buscar(patron, desde)
            if encontrados:
                return encontrados[-1]
            await asyncio.sleep(0.05)
        return None

    def guardar(self) -> Path | None:
        if self.directorio is None or not self.endpoints:
            return None
        self.directorio.mkdir(parents=True, exist_ok=True)
        ruta = self.directorio / f"catalogo-{datetime.now():%Y%m%d-%H%M%S}.json"
        datos = sorted(self.endpoints.values(), key=lambda e: (e["url"], e["metodo"]))
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        return ruta
