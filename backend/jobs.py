import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from . import config
from .core.types import Hooks

JobFn = Callable[["JobContext"], Awaitable[Any]]


@dataclass
class Job:
    id: str
    tipo: str
    estado: str = "en_cola"
    paso: str = ""
    progreso: int = 0
    mensaje: str | None = None
    resultado: Any = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "estado": self.estado,
            "paso": self.paso,
            "progreso": self.progreso,
            "mensaje": self.mensaje,
            "resultado": self.resultado,
        }


class UserInterventionTimeout(Exception):
    pass


class JobContext:
    def __init__(self, manager: "JobManager", job: Job):
        self.manager = manager
        self.job = job
        self._resume = asyncio.Event()

    async def update(
        self, paso: str | None = None, progreso: float | None = None, mensaje: str | None = None
    ) -> None:
        if paso is not None:
            self.job.paso = paso
        if progreso is not None:
            self.job.progreso = max(0, min(100, round(progreso * 100)))
        if mensaje is not None:
            self.job.mensaje = mensaje
        if self.job.estado == "esperando_usuario":
            self.job.estado = "corriendo"
            self.job.mensaje = mensaje
        await self.manager.publish_job(self.job)

    async def log(self, message: str, level: str = "info") -> None:
        await self.manager.publish({"type": "log", "level": level, "message": message})

    async def mark_waiting(self, message: str) -> None:
        self.job.estado = "esperando_usuario"
        self.job.mensaje = message
        await self.manager.publish_job(self.job)

    async def wait_user(self, message: str) -> None:
        self._resume.clear()
        await self.mark_waiting(message)
        try:
            await asyncio.wait_for(self._resume.wait(), timeout=config.USER_WAIT_TIMEOUT_S)
        except TimeoutError as exc:
            raise UserInterventionTimeout(
                "Se agoto el tiempo de espera de la intervencion del usuario."
            ) from exc
        self.job.estado = "corriendo"
        self.job.mensaje = None
        await self.manager.publish_job(self.job)

    def resume(self) -> None:
        self._resume.set()

    def hooks(self) -> Hooks:
        async def paso(texto: str, progreso: float | None = None) -> None:
            await self.update(paso=texto, progreso=progreso)

        return Hooks(
            log=self.log, esperar_usuario=self.wait_user, paso=paso, marcar_espera=self.mark_waiting
        )


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self._contexts: dict[str, JobContext] = {}
        self._tasks: set[asyncio.Task] = set()
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def publish(self, message: dict) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait(message)

    async def publish_job(self, job: Job) -> None:
        await self.publish({"type": "job", "job": job.to_dict()})

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def start(self, tipo: str, fn: JobFn) -> Job:
        job = Job(id=uuid.uuid4().hex, tipo=tipo)
        ctx = JobContext(self, job)
        self.jobs[job.id] = job
        self._contexts[job.id] = ctx
        task = asyncio.get_running_loop().create_task(self._run(job, ctx, fn))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job: Job, ctx: JobContext, fn: JobFn) -> None:
        job.estado = "corriendo"
        await self.publish_job(job)
        try:
            job.resultado = await fn(ctx)
            job.estado = "ok"
            job.progreso = 100
            job.mensaje = None
        except asyncio.CancelledError:
            job.estado = "error"
            job.mensaje = "Cancelado."
            raise
        except Exception as exc:
            job.estado = "error"
            job.mensaje = str(exc) or exc.__class__.__name__
            await ctx.log(job.mensaje, "error")
        finally:
            await self.publish_job(job)

    def resume(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job and job.estado == "esperando_usuario":
            self._contexts[job_id].resume()
        return job

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
