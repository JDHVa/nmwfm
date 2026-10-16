import asyncio
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from .. import services
from ..services import ApiError, AppState

LIMITE_RESULTADOS = 20
LIMITE_TEXTO = 600


class ConfirmacionRequerida(Exception):
    def __init__(self, accion: str, args: dict):
        super().__init__(f"La acción {accion} requiere confirmación del usuario.")
        self.accion = accion
        self.argumentos = args


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    parametros: dict
    funcion: Callable[[AppState, dict], Awaitable[dict | list]]
    peligrosa: bool = False
    requeridos: list[str] = field(default_factory=list)

    def esquema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.nombre,
                "description": self.descripcion,
                "parameters": {
                    "type": "object",
                    "properties": self.parametros,
                    "required": self.requeridos,
                },
            },
        }


def _plano(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def _recortar(texto: str | None) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= LIMITE_TEXTO else texto[:LIMITE_TEXTO] + "… (recortado)"


def _resumen_tarea(tarea: dict, materia: str) -> dict:
    publica = services.con_vencida(tarea)
    return {
        "id": tarea["id"],
        "materia": materia,
        "numero": tarea["numero"],
        "titulo": tarea["titulo"],
        "tipo": tarea["tipo"],
        "estado": tarea["estado"],
        "hasta": tarea.get("hasta"),
        "vencida": publica["vencida"],
    }


def _necesita_tarea(state: AppState, tarea_id: str) -> dict:
    tarea = state.storage.get_tarea(str(tarea_id))
    if tarea is None:
        raise ApiError(404, "tarea_no_encontrada", f"No existe la tarea {tarea_id}.")
    return tarea


async def buscar_tareas(state: AppState, args: dict) -> list[dict]:
    texto = _plano(args.get("texto", ""))
    materia_buscada = _plano(args.get("materia", ""))
    estado = args.get("estado")
    resultados = []
    for materia in state.storage.list_materias():
        if materia_buscada and materia_buscada not in _plano(materia["nombre"]):
            continue
        for etapa in state.storage.list_etapas(materia["id"]):
            for tarea in etapa["tareas"]:
                if estado and tarea["estado"] != estado:
                    continue
                if args.get("tipo") and tarea["tipo"] != args["tipo"]:
                    continue
                if texto and texto not in _plano(f"{tarea['titulo']} {tarea['numero']}"):
                    continue
                resultados.append(_resumen_tarea(tarea, materia["nombre"]))
    return resultados[:LIMITE_RESULTADOS]


async def ver_tarea(state: AppState, args: dict) -> dict:
    tarea = _necesita_tarea(state, args.get("tarea_id", ""))
    materia = state.storage.get_materia(tarea["materia_id"]) or {}
    detalle = state.storage.get_detalle(tarea["id"]) or {}
    rubrica = detalle.get("rubrica")
    criterios = [c["criterio"] for c in (rubrica or {}).get("criterios", [])]
    return {
        **_resumen_tarea(tarea, materia.get("nombre", "")),
        "profesor": materia.get("profesor"),
        "desde": tarea.get("desde"),
        "puntos": tarea.get("puntos"),
        "entregada_en": tarea.get("entregada_en"),
        "actividades": _recortar(detalle.get("actividades")),
        "contenido": _recortar(detalle.get("contenido")),
        "criterios_desempeno": _recortar(detalle.get("criterios_desempeno")),
        "criterios_rubrica": criterios,
        "indicaciones": state.storage.get_indicaciones(tarea["id"]),
        "tiene_generacion": state.storage.get_generacion(tarea["id"]) is not None,
    }


async def proximas_entregas(state: AppState, args: dict) -> list[dict]:
    ahora = services.ahora_monterrey()
    limite = ahora + timedelta(days=int(args["dias"])) if args.get("dias") else None
    salida = []
    for tarea in services.tareas_proximas(state, ahora):
        if tarea["vencida"] and not args.get("incluir_vencidas"):
            continue
        if limite and tarea.get("hasta") and tarea["hasta"] > limite.isoformat(timespec="minutes"):
            continue
        salida.append(_resumen_tarea(tarea, tarea["materia_nombre"]))
    return salida[: int(args.get("limite") or LIMITE_RESULTADOS)]


def _guardar_indicaciones(state: AppState, tarea_id: str, texto: str) -> dict:
    tarea = _necesita_tarea(state, tarea_id)
    state.storage.set_indicaciones(tarea["id"], texto.strip())
    return {"tarea_id": tarea["id"], "indicaciones": state.storage.get_indicaciones(tarea["id"])}


async def agregar_indicaciones(state: AppState, args: dict) -> dict:
    tarea = _necesita_tarea(state, args.get("tarea_id", ""))
    actuales = state.storage.get_indicaciones(tarea["id"])
    nuevo = f"{actuales}\n{args['texto'].strip()}".strip() if actuales else args["texto"]
    return _guardar_indicaciones(state, tarea["id"], nuevo)


async def reemplazar_indicaciones(state: AppState, args: dict) -> dict:
    return _guardar_indicaciones(state, args.get("tarea_id", ""), args["texto"])


async def crear_pdf_imagenes(state: AppState, args: dict) -> dict:
    rutas = [Path(r) for r in args.get("rutas", [])]
    pdf = await asyncio.to_thread(
        services.crear_pdf_imagenes,
        state,
        rutas,
        bool(args.get("recortar", True)),
        _datos_portada(args["portada"]) if isinstance(args.get("portada"), dict) else None,
    )
    return {"pdf_url": state.file_url(pdf), "ruta": str(pdf)}


CAMPOS_PORTADA = {
    "profesor": {"type": "string", "description": "Por defecto, el de la materia."},
    "aula": {"type": "string", "description": "Por defecto, la de los ajustes."},
    "grupo": {"type": "string", "description": "Por defecto, el de los ajustes."},
    "turno": {"type": "string", "description": "Por defecto, el de los ajustes."},
    "especialidad": {"type": "string", "description": "Por defecto, la de los ajustes."},
}


def _datos_portada(args: dict) -> dict:
    return {k: args[k] for k in CAMPOS_PORTADA if isinstance(args.get(k), str)}


async def generar_portada(state: AppState, args: dict) -> dict:
    resultado = await asyncio.to_thread(
        services.generar_portada_suelta,
        state,
        _datos_portada(args),
    )
    carpeta = state.paths.data / resultado["pdf_url"].removeprefix("/files/")
    return {**resultado, "ruta_pdf": str(carpeta)}


CAMPOS_TABLA = (
    "portafolio_pts",
    "portafolio_max",
    "examenes_pts",
    "examenes_max",
    "total_pts",
    "evaluado_pts",
    "pct_evaluado",
)


async def ver_calificaciones(state: AppState, args: dict) -> dict:
    resumen = services.resumen_calificaciones(state)
    buscada = _plano(args.get("materia", ""))
    if buscada:
        resumen["materias"] = [m for m in resumen["materias"] if buscada in _plano(m["nombre"])]
    else:
        resumen["materias"] = [
            {
                **{
                    k: v
                    for k, v in m.items()
                    if k not in ("componentes", "portafolio", "pendientes")
                },
                "tabla": {k: m[k] for k in CAMPOS_TABLA},
            }
            for m in resumen["materias"]
        ]
        for m in resumen["materias"]:
            for k in CAMPOS_TABLA:
                del m[k]
    return resumen


def _iniciar_job(state: AppState, tipo: str, fabrica) -> dict:
    activo = state.jobs.activo(tipo)
    job = activo or state.jobs.start(tipo, fabrica)
    return {
        "job_id": job.id,
        "tipo": job.tipo,
        "estado": job.estado,
        "ya_estaba_corriendo": bool(activo),
    }


async def sincronizar(state: AppState, args: dict) -> dict:
    services.require_credentials(state)
    modo = args.get("modo", "auto")
    return _iniciar_job(state, "sync", lambda ctx: services.run_sync(state, ctx, modo))


async def revisar_entregas(state: AppState, args: dict) -> dict:
    services.require_credentials(state)
    return _iniciar_job(
        state, "revisar_entregas", lambda ctx: services.run_revisar_entregas(state, ctx)
    )


async def generar_tarea(state: AppState, args: dict) -> dict:
    tarea = _necesita_tarea(state, args.get("tarea_id", ""))
    extra = args.get("instrucciones_extra")
    portada = _datos_portada(args["portada"]) if isinstance(args.get("portada"), dict) else None
    overrides = {}
    if isinstance(args.get("instrucciones"), dict):
        overrides = {k: v for k, v in args["instrucciones"].items() if isinstance(v, bool)}
    if args.get("sin_referencias") is True:
        overrides["referencias_apa7"] = False
    return _iniciar_job(
        state,
        "generar",
        lambda ctx: services.run_generar(
            state, ctx, tarea["id"], extra, portada, overrides or None
        ),
    )


async def entregar_tarea(state: AppState, args: dict) -> dict:
    tarea = _necesita_tarea(state, args.get("tarea_id", ""))
    if state.storage.get_generacion(tarea["id"]) is None:
        raise ApiError(400, "sin_generacion", "Genera el documento antes de entregar.")
    return _iniciar_job(
        state, "entregar", lambda ctx: services.run_entregar(state, ctx, tarea["id"])
    )


TAREA_ID = {"type": "string", "description": "Identificador de la tarea (por ejemplo 746214-1.2)."}

HERRAMIENTAS: dict[str, Herramienta] = {
    h.nombre: h
    for h in (
        Herramienta(
            "buscar_tareas",
            "Busca tareas guardadas por texto del título, materia, estado o tipo. Devuelve "
            "hasta 20 coincidencias con su id.",
            {
                "texto": {"type": "string", "description": "Palabras del título o número."},
                "materia": {"type": "string", "description": "Parte del nombre de la materia."},
                "estado": {"type": "string", "enum": ["pendiente", "generada", "entregada"]},
                "tipo": {"type": "string", "enum": ["dimension", "evidencia", "examen", "pia"]},
            },
            buscar_tareas,
        ),
        Herramienta(
            "ver_tarea",
            "Muestra el detalle de una tarea: fechas, actividades, contenido, criterios, "
            "indicaciones del profesor y estado.",
            {"tarea_id": TAREA_ID},
            ver_tarea,
            requeridos=["tarea_id"],
        ),
        Herramienta(
            "proximas_entregas",
            "Lista las tareas no entregadas ordenadas por fecha de entrega, de todas las materias.",
            {
                "dias": {"type": "integer", "description": "Solo las que vencen en estos días."},
                "limite": {"type": "integer", "description": "Máximo de resultados."},
                "incluir_vencidas": {"type": "boolean", "description": "Incluir las vencidas."},
            },
            proximas_entregas,
        ),
        Herramienta(
            "agregar_indicaciones",
            "Agrega una nota del profesor (pizarrón, indicaciones orales) a una tarea, "
            "conservando las anteriores.",
            {"tarea_id": TAREA_ID, "texto": {"type": "string", "description": "Nota a agregar."}},
            agregar_indicaciones,
            requeridos=["tarea_id", "texto"],
        ),
        Herramienta(
            "reemplazar_indicaciones",
            "Reemplaza por completo las indicaciones del profesor de una tarea.",
            {"tarea_id": TAREA_ID, "texto": {"type": "string", "description": "Texto nuevo."}},
            reemplazar_indicaciones,
            requeridos=["tarea_id", "texto"],
        ),
        Herramienta(
            "crear_pdf_imagenes",
            "Convierte imágenes del equipo en un solo PDF (una página por imagen, en orden), "
            "recortando la hoja de cada foto y con portada opcional como primera página.",
            {
                "rutas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Rutas absolutas de las imágenes en este equipo.",
                },
                "recortar": {
                    "type": "boolean",
                    "description": "Recortar la hoja (por defecto sí).",
                },
                "portada": {
                    "type": "object",
                    "description": "Si viene, la portada va como primera página del PDF.",
                    "properties": CAMPOS_PORTADA,
                    "required": ["profesor"],
                },
            },
            crear_pdf_imagenes,
            requeridos=["rutas"],
        ),
        Herramienta(
            "generar_portada",
            "Genera una portada suelta (Word y PDF) con la fecha de hoy; aula, grupo, turno y "
            "especialidad salen de los ajustes si se omiten.",
            CAMPOS_PORTADA,
            generar_portada,
            requeridos=["profesor"],
        ),
        Herramienta(
            "ver_calificaciones",
            "Muestra las calificaciones de SIASE y NEXUS con la predicción del semestre: "
            "puntos asegurados, proyección, probabilidad de aprobar y lo que falta sacar. Sin "
            "materia devuelve un resumen compacto; con materia, el detalle de esa materia.",
            {"materia": {"type": "string", "description": "Parte del nombre de la materia."}},
            ver_calificaciones,
        ),
        Herramienta(
            "sincronizar",
            "Sincroniza materias, tareas y detalles desde NEXUS (corre en segundo plano).",
            {"modo": {"type": "string", "enum": ["auto", "completo", "incremental"]}},
            sincronizar,
        ),
        Herramienta(
            "revisar_entregas",
            "Revisa en NEXUS cuáles tareas pendientes ya fueron entregadas (segundo plano).",
            {},
            revisar_entregas,
        ),
        Herramienta(
            "generar_tarea",
            "Genera con Gemini el Word y PDF (con portada) de una tarea, en segundo plano. Solo "
            "si el usuario lo pide explícitamente.",
            {
                "tarea_id": TAREA_ID,
                "instrucciones_extra": {"type": "string", "description": "Indicaciones extra."},
                "sin_referencias": {
                    "type": "boolean",
                    "description": "Si es true, no pide la sección de Referencias APA 7.",
                },
                "instrucciones": {
                    "type": "object",
                    "description": "Activa o desactiva instrucciones fijas por id solo para esta "
                    'generación, p. ej. {"referencias_apa7": false}.',
                    "additionalProperties": {"type": "boolean"},
                },
                "portada": {
                    "type": "object",
                    "description": "Datos de portada a cambiar; los omitidos usan los ajustes.",
                    "properties": CAMPOS_PORTADA,
                },
            },
            generar_tarea,
            requeridos=["tarea_id"],
        ),
        Herramienta(
            "entregar_tarea",
            "Entrega en NEXUS el PDF generado de una tarea. Para entregar, SIEMPRE llama a esta "
            "herramienta; la app mostrará la confirmación al usuario. Nunca pidas confirmación "
            "en texto.",
            {"tarea_id": TAREA_ID},
            entregar_tarea,
            peligrosa=True,
            requeridos=["tarea_id"],
        ),
    )
}


def esquemas() -> list[dict]:
    return [h.esquema() for h in HERRAMIENTAS.values()]


async def ejecutar(
    state: AppState, nombre: str, args: dict | None, *, confirmado: bool = False
) -> dict | list:
    herramienta = HERRAMIENTAS.get(nombre)
    args = args or {}
    if herramienta is None:
        return {"error": f"No existe la herramienta {nombre}."}
    faltan = [r for r in herramienta.requeridos if args.get(r) in (None, "", [])]
    if faltan:
        return {"error": f"Faltan argumentos: {', '.join(faltan)}."}
    if herramienta.peligrosa and not confirmado:
        raise ConfirmacionRequerida(nombre, args)
    try:
        return await herramienta.funcion(state, args)
    except ApiError as exc:
        return {"error": exc.message}
    except (ValueError, KeyError, TypeError) as exc:
        return {"error": f"Argumentos inválidos: {exc}"}
