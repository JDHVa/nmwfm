import asyncio
import contextlib
import json
import re
import uuid
from collections.abc import AsyncIterator

from .. import services
from ..services import AppState
from . import herramientas as h
from .ollama import FiltroPensamiento, OllamaError

MAX_VUELTAS = 6
INTENCIONES = (
    (
        "entregar_tarea",
        re.compile(
            r"^\W*(por favor,?\s+)?(entrega|entr[eé]gala|entregala|sube|s[uú]bela|subela)\b"
            r"|\b(quiero|puedes|podr[ií]as|necesito|ya|hay que)\s+(entregar|subir)\b",
            re.IGNORECASE,
        ),
        "Recuerda: para entregar una tarea debes llamar a la herramienta entregar_tarea con su "
        "tarea_id (usa buscar_tareas si no lo tienes). La app mostrará la confirmación al "
        "usuario; nunca la pidas en texto.",
    ),
    (
        "agregar_indicaciones",
        re.compile(
            r"\b(el|la)\s+(profe|profesor|profesora|maestro|maestra|miss)\b.*"
            r"\b(dijo|indic\w+|pidi\w+|pide|quiere|mand\w+|aclar\w+)\b"
            r"|\bdijo que\b|\bnueva indicaci\w+|\bagrega\w*\s+(una\s+)?(indicaci|nota)",
            re.IGNORECASE,
        ),
        "Recuerda: si el usuario te cuenta una indicación del profesor, debes guardarla llamando "
        "a agregar_indicaciones con el tarea_id (obtenlo con buscar_tareas). No digas que la "
        "guardaste sin llamar a la herramienta.",
    ),
    (
        "ver_tarea",
        re.compile(
            r"\bexpl[ií]ca\w*|\bdetalles?\b|\bde qu[eé] trata\b|\bqu[eé] (piden|hay que hacer)\b"
            r"|\bqu[eé] tengo que hacer\b|\bdescr[ií]be\w*",
            re.IGNORECASE,
        ),
        "Recuerda: para explicar una tarea llama a ver_tarea con su tarea_id (obtenlo con "
        "buscar_tareas) y explícala con sus datos reales.",
    ),
)
ACCIONES_SOLO_SI_SE_PIDEN = {
    "generar_tarea": re.compile(
        r"\bgener\w*|\bhaz\b|\bhazla\b|\belabora\w*|\bredacta\w*|\bresuelve\b", re.I
    ),
    "sincronizar": re.compile(r"\bsincroni\w*|\bactualiza\w*", re.I),
    "revisar_entregas": re.compile(r"\brevis\w*|\bverifica\w*", re.I),
}
LIMITE_RESULTADO = 1500
PRESUPUESTO_HISTORIAL = 5000
LIMITE_INDICACIONES = 300

PROMPT_SISTEMA = (
    "Eres el asistente de tareas de un estudiante de preparatoria de la UANL que usa la "
    "plataforma NEXUS. Responde siempre en español, de forma breve y clara. Usa las "
    "herramientas para consultar datos reales (tareas, fechas, estados, indicaciones) y "
    "para ejecutar acciones; nunca inventes ids, fechas, calificaciones ni resultados. Si "
    "falta información para usar una herramienta, pregunta al usuario. Para entregar una "
    "tarea SIEMPRE llama a entregar_tarea; la app mostrará la confirmación al usuario. "
    "Nunca pidas confirmación en texto. Los ids de tarea son exactos y no se adivinan: "
    "obtenlos siempre con buscar_tareas antes de usar ver_tarea, agregar_indicaciones o "
    "entregar_tarea. Para explicar o dar detalles de una tarea llama a ver_tarea. Si el "
    "usuario cuenta una indicación del profesor sobre una tarea, guárdala de inmediato con "
    "agregar_indicaciones sin pedir permiso. Si el usuario no menciona la materia, no "
    "inventes una: busca solo "
    "por número o palabras del título. Las acciones sincronizar, revisar_entregas y "
    "generar_tarea solo se usan cuando el usuario las pide explícitamente; para entregar "
    "NO generes nada antes. "
    "En buscar_tareas, materia es el nombre de la materia y texto son palabras del título "
    "de la tarea; no mezcles ambos. Fecha y hora actual (Monterrey): {ahora}.{sufijo}"
)


def es_instruct(modelo: str) -> bool:
    return "instruct" in modelo.lower()


def herramienta_requerida(mensajes: list[dict]) -> tuple[str, str] | None:
    ultimo = next((m for m in reversed(mensajes) if m.get("rol") == "user"), None)
    texto = ultimo.get("contenido", "") if ultimo else ""
    for herramienta, patron, recordatorio in INTENCIONES:
        if patron.search(texto):
            return herramienta, recordatorio
    return None


def pide_entregar(mensajes: list[dict]) -> bool:
    requerida = herramienta_requerida(mensajes)
    return bool(requerida and requerida[0] == "entregar_tarea")


def accion_permitida(nombre: str, mensajes: list[dict]) -> bool:
    patron = ACCIONES_SOLO_SI_SE_PIDEN.get(nombre)
    if patron is None:
        return True
    ultimo = next((m for m in reversed(mensajes) if m.get("rol") == "user"), None)
    return bool(ultimo and patron.search(ultimo.get("contenido", "")))


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


def _llamo(conversacion: list[dict], herramienta: str) -> bool:
    return any(
        (c.get("function") or {}).get("name") == herramienta
        for m in conversacion
        for c in (m.get("tool_calls") or [])
    )


def _recortar(texto: str) -> str:
    return texto if len(texto) <= LIMITE_RESULTADO else texto[:LIMITE_RESULTADO] + "…"


async def conversar(
    state: AppState, mensajes: list[dict], tarea_id: str | None = None
) -> AsyncIterator[dict]:
    ajustes = state.storage.get_settings()
    modelo = ajustes["asistente_modelo"]
    keep_alive = f"{ajustes['asistente_keep_alive_s']}s"
    sistema = PROMPT_SISTEMA.format(
        ahora=services.ahora_monterrey().strftime("%Y-%m-%d %H:%M"),
        sufijo="" if es_instruct(modelo) else " /no_think",
    )
    if tarea_id:
        sistema += "\n\n" + await contexto_tarea(state, tarea_id)
    historial = recortar_historial(_mensajes_ollama(mensajes))
    conversacion = [{"role": "system", "content": sistema.strip()}, *historial]
    esquemas = h.esquemas()

    try:
        with contextlib.suppress(OllamaError):
            if modelo not in await state.ollama.cargados():
                yield estado_evento("cargando", "Cargando modelo…")
        requerida = herramienta_requerida(mensajes)
        retener = requerida is not None
        for _ in range(MAX_VUELTAS):
            texto, llamadas, retenidos = "", [], []
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
                        if retener:
                            retenidos.append({"type": "token", "text": visible})
                        else:
                            yield {"type": "token", "text": visible}
                llamadas.extend(mensaje.get("tool_calls") or [])
            resto = filtro.finalizar()
            if resto:
                texto += resto
                if retener:
                    retenidos.append({"type": "token", "text": resto})
                else:
                    yield {"type": "token", "text": resto}
            if not llamadas and retener:
                retener = False
                if _llamo(conversacion, requerida[0]):
                    for evento in retenidos:
                        yield evento
                    yield {"type": "fin"}
                    return
                conversacion.append({"role": "assistant", "content": texto})
                conversacion.append({"role": "user", "content": requerida[1]})
                continue
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
                    if accion_permitida(nombre, mensajes):
                        resultado = await h.ejecutar(state, nombre, args)
                    else:
                        resultado = {
                            "error": f"El usuario no pidió {nombre}; no la uses sin que lo pida."
                        }
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
