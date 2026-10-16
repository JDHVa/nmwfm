import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator

from .. import services
from ..services import AppState
from . import herramientas as h
from .ollama import FiltroPensamiento, OllamaError

MAX_VUELTAS = 6
LIMITE_RESULTADO = 1500
PRESUPUESTO_HISTORIAL = 5000
LIMITE_INDICACIONES = 300

PROMPT_SISTEMA = (
    "Eres el asistente de tareas de un estudiante de preparatoria de la UANL que usa la "
    "plataforma NEXUS. Responde siempre en español, de forma breve y clara. Usa las "
    "herramientas para consultar datos reales (tareas, fechas, estados, indicaciones) y "
    "para ejecutar acciones; nunca inventes ids, fechas, calificaciones ni resultados. Si "
    "falta información para usar una herramienta, pregunta al usuario. Para entregar una "
    "tarea usa entregar_tarea: el usuario debe confirmarlo antes de que se ejecute. "
    "En buscar_tareas, materia es el nombre de la materia y texto son palabras del título "
    "de la tarea; no mezcles ambos. Fecha y hora actual (Monterrey): {ahora}. /no_think"
)


def estado_evento(clave: str, mensaje: str) -> dict:
    return {"type": "estado", "estado": clave, "mensaje": mensaje}


def pendientes(state: AppState) -> dict:
    if not hasattr(state, "asistente_pendientes"):
        state.asistente_pendientes = {}
    return state.asistente_pendientes


async def contexto_tarea(state: AppState, tarea_id: str) -> str:
    datos = await h.ejecutar(state, "ver_tarea", {"tarea_id": tarea_id})
    if "error" in datos:
        return ""
    resumen = {
        clave: datos.get(clave)
        for clave in ("id", "materia", "numero", "titulo", "tipo", "estado", "hasta", "vencida")
    }
    resumen["indicaciones"] = (datos.get("indicaciones") or "")[:LIMITE_INDICACIONES]
    return "El usuario está viendo esta tarea en la app:\n" + json.dumps(
        resumen, ensure_ascii=False
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


def recortar_historial(
    mensajes: list[dict], presupuesto: int = PRESUPUESTO_HISTORIAL
) -> list[dict]:
    elegidos, usado = [], 0
    for m in reversed(mensajes):
        peso = len(m.get("content", "")) + 40
        if elegidos and usado + peso > presupuesto:
            break
        elegidos.append(m)
        usado += peso
    elegidos.reverse()
    while len(elegidos) > 1 and elegidos[0]["role"] != "user":
        elegidos.pop(0)
    return elegidos


def _recortar(texto: str) -> str:
    return texto if len(texto) <= LIMITE_RESULTADO else texto[:LIMITE_RESULTADO] + "…"


async def conversar(
    state: AppState, mensajes: list[dict], tarea_id: str | None = None
) -> AsyncIterator[dict]:
    ajustes = state.storage.get_settings()
    modelo = ajustes["asistente_modelo"]
    keep_alive = f"{ajustes['asistente_keep_alive_s']}s"
    sistema = PROMPT_SISTEMA.format(ahora=services.ahora_monterrey().strftime("%Y-%m-%d %H:%M"))
    if tarea_id:
        sistema += "\n\n" + await contexto_tarea(state, tarea_id)
    historial = recortar_historial(_mensajes_ollama(mensajes))
    conversacion = [{"role": "system", "content": sistema.strip()}, *historial]
    esquemas = h.esquemas()

    try:
        with contextlib.suppress(OllamaError):
            if modelo not in await state.ollama.cargados():
                yield estado_evento("cargando", "Cargando modelo…")
        for _ in range(MAX_VUELTAS):
            texto, llamadas = "", []
            filtro = FiltroPensamiento()
            aviso_pensando = False
            async for trozo in state.ollama.chat(modelo, conversacion, esquemas, keep_alive):
                mensaje = trozo.get("message") or {}
                if mensaje.get("thinking") and not aviso_pensando:
                    aviso_pensando = True
                    yield estado_evento("pensando", "Pensando…")
                if mensaje.get("content"):
                    visible, pensando = filtro.procesar(mensaje["content"])
                    if pensando and not aviso_pensando:
                        aviso_pensando = True
                        yield estado_evento("pensando", "Pensando…")
                    if visible:
                        texto += visible
                        yield {"type": "token", "text": visible}
                llamadas.extend(mensaje.get("tool_calls") or [])
            resto = filtro.finalizar()
            if resto:
                texto += resto
                yield {"type": "token", "text": resto}
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


_tareas_precalentado: set = set()


async def precalentar(state: AppState) -> dict:
    ajustes = state.storage.get_settings()
    modelo = ajustes["asistente_modelo"]
    keep_alive = f"{ajustes['asistente_keep_alive_s']}s"
    if modelo in await state.ollama.cargados():
        return {"cargado": True, "cargando": False, "modelo": modelo}

    async def cargar() -> None:
        with contextlib.suppress(OllamaError):
            await state.ollama.precalentar(modelo, keep_alive)

    tarea = asyncio.get_running_loop().create_task(cargar())
    _tareas_precalentado.add(tarea)
    tarea.add_done_callback(_tareas_precalentado.discard)
    return {"cargado": False, "cargando": True, "modelo": modelo}


async def liberar(state: AppState) -> dict:
    modelo = state.storage.get_settings()["asistente_modelo"]
    try:
        await state.ollama.liberar(modelo)
    except OllamaError:
        return {"liberado": False, "modelo": modelo}
    return {"liberado": True, "modelo": modelo}
