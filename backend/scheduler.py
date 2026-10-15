import asyncio
import contextlib
from collections.abc import Callable
from datetime import datetime, timedelta

from .jobs import Job
from .services import ApiError, AppState, require_credentials, run_sync

INTERVALO_REVISION_S = 60


def debe_sincronizar(horas: int, ultima: datetime | None, ahora: datetime) -> bool:
    return horas > 0 and (ultima is None or ahora - ultima >= timedelta(hours=horas))


def _fecha(texto: str | None) -> datetime | None:
    if not texto:
        return None
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(texto)
    return None


class Programador:
    def __init__(
        self,
        state: AppState,
        reloj: Callable[[], datetime] = datetime.now,
        intervalo: float = INTERVALO_REVISION_S,
    ):
        self.state = state
        self.reloj = reloj
        self.intervalo = intervalo
        self._tarea: asyncio.Task | None = None
        self._ultimo_intento: datetime | None = None

    def iniciar(self) -> None:
        self._tarea = asyncio.get_running_loop().create_task(self._bucle())

    async def detener(self) -> None:
        tarea, self._tarea = self._tarea, None
        if tarea is not None:
            tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarea

    async def _bucle(self) -> None:
        while True:
            with contextlib.suppress(Exception):
                await self.revisar()
            await asyncio.sleep(self.intervalo)

    async def revisar(self) -> Job | None:
        ajustes = self.state.storage.get_settings()
        ahora = self.reloj()
        referencias = [_fecha(ajustes["ultima_sync"]), self._ultimo_intento]
        ultima = max((f for f in referencias if f is not None), default=None)
        if not debe_sincronizar(ajustes["sync_cada_horas"], ultima, ahora):
            return None
        if self.state.jobs.activo("sync") or self.state.browser.lock.locked():
            return None
        try:
            require_credentials(self.state)
        except ApiError:
            return None
        self._ultimo_intento = ahora
        return self.state.jobs.start("sync", lambda ctx: run_sync(self.state, ctx, "auto"))
