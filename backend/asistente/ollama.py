import json
from collections.abc import AsyncIterator

OLLAMA_URL = "http://127.0.0.1:11434"
MODELO_POR_DEFECTO = "qwen3:4b"


class OllamaError(Exception):
    pass


class OllamaNoDisponible(OllamaError):
    def __init__(self) -> None:
        super().__init__("Ollama no está corriendo")


def es_qwen3(modelo: str) -> bool:
    return modelo.lower().startswith("qwen3")


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

    async def chat(
        self, modelo: str, mensajes: list[dict], herramientas: list[dict] | None = None
    ) -> AsyncIterator[dict]:
        import httpx

        carga: dict = {"model": modelo, "messages": mensajes, "stream": True}
        if herramientas:
            carga["tools"] = herramientas
        if es_qwen3(modelo):
            carga["think"] = False
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
