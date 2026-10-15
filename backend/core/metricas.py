import contextlib
import time
from collections import defaultdict
from contextvars import ContextVar


class Metricas:
    def __init__(self) -> None:
        self._fases: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])

    def registrar(self, fase: str, segundos: float) -> None:
        acumulado = self._fases[fase]
        acumulado[0] += 1
        acumulado[1] += segundos

    def resumen(self) -> dict[str, dict[str, float]]:
        return {
            fase: {
                "n": int(n),
                "total_s": round(total, 2),
                "media_s": round(total / n, 2) if n else 0.0,
            }
            for fase, (n, total) in self._fases.items()
        }

    def texto(self) -> str:
        partes = [
            f"{fase}: {r['n']}x, total {r['total_s']}s, media {r['media_s']}s"
            for fase, r in self.resumen().items()
        ]
        return "Tiempos · " + " | ".join(partes) if partes else "Tiempos · sin datos"


actual: ContextVar[Metricas | None] = ContextVar("metricas", default=None)


@contextlib.asynccontextmanager
async def medir(fase: str):
    inicio = time.perf_counter()
    try:
        yield
    finally:
        metricas = actual.get()
        if metricas is not None:
            metricas.registrar(fase, time.perf_counter() - inicio)
