import asyncio
import inspect
from typing import Literal

from . import config
from .asistente import herramientas as h
from .services import AppState

ESPERA_JOB_S = 1800
ESTADOS_FINALES = ("ok", "error")


def _tipo(propiedad: dict):
    tipo = propiedad.get("type")
    if propiedad.get("enum"):
        return Literal[tuple(propiedad["enum"])]
    if tipo == "integer":
        return int
    if tipo == "boolean":
        return bool
    if tipo == "array":
        return list[str]
    if tipo == "object":
        return dict
    return str


def _firma(herramienta: h.Herramienta) -> inspect.Signature:
    parametros = []
    for nombre, propiedad in herramienta.parametros.items():
        requerido = nombre in herramienta.requeridos
        tipo = _tipo(propiedad)
        parametros.append(
            inspect.Parameter(
                nombre,
                inspect.Parameter.KEYWORD_ONLY,
                default=inspect.Parameter.empty if requerido else None,
                annotation=tipo if requerido else tipo | None,
            )
        )
    if herramienta.peligrosa:
        parametros.append(
            inspect.Parameter(
                "confirmar", inspect.Parameter.KEYWORD_ONLY, default=False, annotation=bool
            )
        )
    return inspect.Signature(parametros)


async def _esperar_job(state: AppState, resultado: dict) -> dict:
    job = state.jobs.get(resultado.get("job_id", ""))
    if job is None:
        return resultado
    fin = asyncio.get_running_loop().time() + ESPERA_JOB_S
    while job.estado not in ESTADOS_FINALES and asyncio.get_running_loop().time() < fin:  # noqa: ASYNC110
        await asyncio.sleep(0.5)
    return {
        **resultado,
        "estado": job.estado,
        "mensaje": job.mensaje,
        "resultado_job": job.resultado,
    }


def _crear_funcion(herramienta: h.Herramienta, obtener_estado):
    async def ejecutar(**argumentos):
        state = obtener_estado()
        confirmar = bool(argumentos.pop("confirmar", False))
        args = {k: v for k, v in argumentos.items() if v is not None}
        if herramienta.peligrosa and not confirmar:
            return {
                "error": (
                    f"{herramienta.nombre} exige confirmar=true. Pídele confirmación explícita "
                    "al usuario y vuelve a llamarla con confirmar=true."
                )
            }
        resultado = await h.ejecutar(state, herramienta.nombre, args, confirmado=confirmar)
        if isinstance(resultado, dict) and "job_id" in resultado:
            return await _esperar_job(state, resultado)
        return resultado

    ejecutar.__name__ = herramienta.nombre
    ejecutar.__signature__ = _firma(herramienta)
    ejecutar.__annotations__ = {
        p.name: p.annotation for p in ejecutar.__signature__.parameters.values()
    }
    return ejecutar


def build_server(state: AppState | None = None):
    from mcp.server.fastmcp import FastMCP

    cache: dict[str, AppState] = {}

    def obtener_estado() -> AppState:
        if state is not None:
            return state
        if "estado" not in cache:
            cache["estado"] = AppState(config.DATA_DIR, "mcp", dev=config.DEV)
        return cache["estado"]

    servidor = FastMCP("nmwfm")
    for herramienta in h.HERRAMIENTAS.values():
        descripcion = herramienta.descripcion
        if herramienta.peligrosa:
            descripcion += (
                " Requiere confirmar=true, solo tras la aprobación explícita del usuario."
            )
        servidor.add_tool(
            _crear_funcion(herramienta, obtener_estado),
            name=herramienta.nombre,
            description=descripcion,
        )
    return servidor


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
