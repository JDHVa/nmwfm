import json
import uuid
from collections.abc import AsyncIterator

from .. import services
from ..services import AppState
from . import herramientas as h
from .ollama import OllamaError

MAX_VUELTAS = 6
LIMITE_RESULTADO = 4000

PROMPT_SISTEMA = (
    "Eres el asistente de tareas de un estudiante de preparatoria de la UANL que usa la "
    "plataforma NEXUS. Responde siempre en español, de forma breve y clara. Usa las "
    "herramientas para consultar datos reales (tareas, fechas, estados, indicaciones) y "
    "para ejecutar acciones; nunca inventes ids, fechas, calificaciones ni resultados. Si "
    "falta información para usar una herramienta, pregunta al usuario. Para entregar una "
    "tarea usa entregar_tarea: el usuario debe confirmarlo antes de que se ejecute. "
    "Fecha y hora actual (Monterrey): {ahora}."
)


def pendientes(state: AppState) -> dict:
    if not hasattr(state, "asistente_pendientes"):
        state.asistente_pendientes = {}
    return state.asistente_pendientes


async def contexto_tarea(state: AppState, tarea_id: str) -> str:
    datos = await h.ejecutar(state, "ver_tarea", {"tarea_id": tarea_id})
    if "error" in datos:
        return ""
    return "El usuario está viendo esta tarea en la app (usa su id si hace falta):\n" + json.dumps(
        datos, ensure_ascii=False
    )


def _mensajes_ollama(mensajes: list[dict]) -> list[dict]:
    salida = []
    for m in mensajes:
        rol = m.get("rol")
        if rol == "tool":
            salida.append(
                {
                    "role": "tool",
                    "content": m.get("contenido", ""),
                    "tool_name": m.get("herramienta", ""),
                }
            )
        elif rol in ("user", "assistant"):
            salida.append({"role": rol, "content": m.get("contenido", "")})
    return salida


def _recortar(texto: str) -> str:
    return texto if len(texto) <= LIMITE_RESULTADO else texto[:LIMITE_RESULTADO] + "…"


async def conversar(
    state: AppState, mensajes: list[dict], tarea_id: str | None = None
) -> AsyncIterator[dict]:
    modelo = state.storage.get_settings()["asistente_modelo"]
    sistema = PROMPT_SISTEMA.format(ahora=services.ahora_monterrey().strftime("%Y-%m-%d %H:%M"))
    if tarea_id:
        sistema += "\n\n" + await contexto_tarea(state, tarea_id)
    conversacion = [{"role": "system", "content": sistema.strip()}, *_mensajes_ollama(mensajes)]
    esquemas = h.esquemas()

    try:
        for _ in range(MAX_VUELTAS):
            texto, llamadas = "", []
            async for trozo in state.ollama.chat(modelo, conversacion, esquemas):
                mensaje = trozo.get("message") or {}
                if mensaje.get("content"):
                    texto += mensaje["content"]
                    yield {"type": "token", "text": mensaje["content"]}
                llamadas.extend(mensaje.get("tool_calls") or [])
            if not llamadas:
                yield {"type": "fin"}
                return
            conversacion.append({"role": "assistant", "content": texto, "tool_calls": llamadas})
            for llamada in llamadas:
                funcion = llamada.get("function") or {}
                nombre = funcion.get("name", "")
                args = funcion.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args or "{}")
                yield {"type": "tool_call", "nombre": nombre, "args": args}
                try:
                    resultado = await h.ejecutar(state, nombre, args)
                except h.ConfirmacionRequerida as exc:
                    confirmacion = uuid.uuid4().hex[:12]
                    pendientes(state)[confirmacion] = (exc.accion, exc.argumentos)
                    yield {
                        "type": "confirmar",
                        "accion": exc.accion,
                        "args": exc.argumentos,
                        "id": confirmacion,
                    }
                    yield {"type": "fin"}
                    return
                yield {"type": "tool_result", "nombre": nombre, "resultado": resultado}
                conversacion.append(
                    {
                        "role": "tool",
                        "tool_name": nombre,
                        "content": _recortar(json.dumps(resultado, ensure_ascii=False)),
                    }
                )
        yield {
            "type": "token",
            "text": "Me detuve porque usé demasiadas herramientas seguidas. ¿Qué sigue?",
        }
        yield {"type": "fin"}
    except OllamaError as exc:
        yield {"type": "error", "message": str(exc)}


async def confirmar(state: AppState, confirmacion_id: str, aceptar: bool) -> dict | None:
    pendiente = pendientes(state).pop(confirmacion_id, None)
    if pendiente is None:
        return None
    if not aceptar:
        return {"cancelado": True}
    accion, args = pendiente
    return await h.ejecutar(state, accion, args, confirmado=True)


async def estado(state: AppState) -> dict:
    modelo = state.storage.get_settings()["asistente_modelo"]
    try:
        instalados = await state.ollama.etiquetas()
    except OllamaError as exc:
        return {"ollama": False, "modelo": modelo, "modelo_instalado": False, "error": str(exc)}
    base = modelo.split(":")[0]
    instalado = modelo in instalados or (
        ":" not in modelo and any(i.split(":")[0] == base for i in instalados)
    )
    return {"ollama": True, "modelo": modelo, "modelo_instalado": instalado, "error": None}
