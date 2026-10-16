import json
from collections.abc import AsyncIterator

OLLAMA_URL = "http://127.0.0.1:11434"
MODELO_POR_DEFECTO = "qwen3:4b"
KEEP_ALIVE_POR_DEFECTO = "90s"
ABRE_PENSAR = "<think>"
CIERRA_PENSAR = "</think>"


class OllamaError(Exception):
    pass


class OllamaNoDisponible(OllamaError):
    def __init__(self) -> None:
        super().__init__("Ollama no está corriendo")


def _sufijo_parcial(texto: str, etiqueta: str) -> int:
    for largo in range(min(len(etiqueta) - 1, len(texto)), 0, -1):
        if texto.endswith(etiqueta[:largo]):
            return largo
    return 0


class FiltroPensamiento:
    """Quita los bloques <think>...</think> de un flujo de texto, aunque lleguen partidos."""

    def __init__(self) -> None:
        self.dentro = False
        self.buffer = ""
        self._inicio_visible = True

    def procesar(self, trozo: str) -> tuple[str, bool]:
        self.buffer += trozo
        visible, empezo = "", False
        while True:
            if not self.dentro:
                i = self.buffer.find(ABRE_PENSAR)
                if i >= 0:
                    visible += self.buffer[:i]
                    self.buffer = self.buffer[i + len(ABRE_PENSAR) :]
                    self.dentro, empezo = True, True
                    continue
                resto = _sufijo_parcial(self.buffer, ABRE_PENSAR)
                limite = len(self.buffer) - resto
                visible += self.buffer[:limite]
                self.buffer = self.buffer[limite:]
                break
            i = self.buffer.find(CIERRA_PENSAR)
            if i >= 0:
                self.buffer = self.buffer[i + len(CIERRA_PENSAR) :]
                self.dentro = False
                self._inicio_visible = True
                continue
            self.buffer = self.buffer[
                len(self.buffer) - _sufijo_parcial(self.buffer, CIERRA_PENSAR) :
            ]
            break
        if visible and self._inicio_visible:
            visible = visible.lstrip()
            self._inicio_visible = not visible
        return visible, empezo

    def finalizar(self) -> str:
        resto = "" if self.dentro else self.buffer
        self.buffer = ""
        return resto


class OllamaCliente:
    def __init__(self, base: str = OLLAMA_URL, transporte=None, timeout: float = 300.0):
        self.base = base.rstrip("/")
        self.transporte = transporte
        self.timeout = timeout

    def _cliente(self):
        import httpx

        return httpx.AsyncClient(
            transport=self.transporte, timeout=httpx.Timeout(self.timeout, connect=3.0)
        )

    async def etiquetas(self) -> list[str]:
        import httpx

        try:
            async with self._cliente() as cliente:
                respuesta = await cliente.get(f"{self.base}/api/tags")
        except httpx.TransportError as exc:
            raise OllamaNoDisponible() from exc
        if respuesta.status_code != 200:
            raise OllamaError(f"Ollama respondió {respuesta.status_code}.")
        return [m["name"] for m in respuesta.json().get("models", [])]

    async def cargados(self) -> list[str]:
        import httpx

        try:
            async with self._cliente() as cliente:
                respuesta = await cliente.get(f"{self.base}/api/ps")
        except httpx.TransportError as exc:
            raise OllamaNoDisponible() from exc
        if respuesta.status_code != 200:
            return []
        return [m["name"] for m in respuesta.json().get("models", [])]

    async def liberar(self, modelo: str) -> None:
        import httpx

        try:
            async with self._cliente() as cliente:
                await cliente.post(
                    f"{self.base}/api/chat",
                    json={"model": modelo, "messages": [], "keep_alive": 0},
                )
        except httpx.TransportError as exc:
            raise OllamaNoDisponible() from exc

    async def precalentar(self, modelo: str, keep_alive: str = KEEP_ALIVE_POR_DEFECTO) -> None:
        import httpx

        try:
            async with self._cliente() as cliente:
                respuesta = await cliente.post(
                    f"{self.base}/api/chat",
                    json={"model": modelo, "messages": [], "keep_alive": keep_alive},
                )
        except httpx.TransportError as exc:
            raise OllamaNoDisponible() from exc
        if respuesta.status_code != 200:
            raise OllamaError(_mensaje_de_error(respuesta.status_code, respuesta.text, modelo))

    async def chat(
        self,
        modelo: str,
        mensajes: list[dict],
        herramientas: list[dict] | None = None,
        keep_alive: str = KEEP_ALIVE_POR_DEFECTO,
    ) -> AsyncIterator[dict]:
        import httpx

        carga: dict = {
            "model": modelo,
            "messages": mensajes,
            "stream": True,
            "keep_alive": keep_alive,
        }
        if herramientas:
            carga["tools"] = herramientas
        # Con think=false qwen3 razona igual pero dentro del contenido; sin el parámetro Ollama
        # separa el razonamiento en message.thinking y el contenido llega limpio.
        try:
            async with (
                self._cliente() as cliente,
                cliente.stream("POST", f"{self.base}/api/chat", json=carga) as r,
            ):
                if r.status_code != 200:
                    cuerpo = (await r.aread()).decode("utf-8", errors="replace")
                    raise OllamaError(_mensaje_de_error(r.status_code, cuerpo, modelo))
                async for linea in r.aiter_lines():
                    if linea.strip():
                        yield json.loads(linea)
        except httpx.TransportError as exc:
            raise OllamaNoDisponible() from exc


def _mensaje_de_error(status: int, cuerpo: str, modelo: str) -> str:
    try:
        detalle = json.loads(cuerpo).get("error", cuerpo)
    except ValueError:
        detalle = cuerpo
    if status == 404 or "not found" in str(detalle).lower():
        return f"El modelo {modelo} no está instalado (ejecuta: ollama pull {modelo})."
    return f"Ollama respondió {status}: {detalle}"
