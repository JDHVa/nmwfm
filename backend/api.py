import asyncio
import contextlib
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import check, config, respaldo, services
from .asistente import chat as asistente
from .asistente.ollama import OllamaError
from .core import images
from .scheduler import Programador
from .services import ApiError, AppState

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
PUBLIC_DIRS = ("insumos", "generaciones", "herramientas", "respaldos")


class TextoBody(BaseModel):
    texto: str


class PatchInsumoBody(BaseModel):
    orden: int | None = None
    rotacion: Literal[0, 90, 180, 270] | None = None
    usar_recorte: bool | None = None
    texto: str | None = None
    ocr_texto: str | None = None


class PortadaSueltaBody(BaseModel):
    profesor: str
    materia: str | None = None
    titulo: str | None = None
    fecha: str | None = None


class MensajeChat(BaseModel):
    rol: Literal["user", "assistant", "tool"]
    contenido: str = ""
    herramienta: str | None = None


class ChatBody(BaseModel):
    mensajes: list[MensajeChat]
    tarea_id: str | None = None


class ConfirmarBody(BaseModel):
    id: str
    aceptar: bool


class IndicacionesBody(BaseModel):
    indicaciones: str


class PortadaBody(BaseModel):
    profesor: str | None = None
    titulo: str | None = None


class GenerarBody(BaseModel):
    instrucciones_extra: str | None = None
    portada: PortadaBody | None = None


class SyncBody(BaseModel):
    modo: Literal["auto", "completo", "incremental"] = "auto"


class RestaurarBody(BaseModel):
    nombre: str


class LeidasBody(BaseModel):
    ids: list[int] | None = None


class EntregarBody(BaseModel):
    confirmar: bool = False


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def parse_campos(content_type: str, body: bytes) -> dict[str, str]:
    raw = b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + body
    message = BytesParser(policy=policy.HTTP).parsebytes(raw)
    campos = {}
    if message.is_multipart():
        for part in message.iter_parts():
            if not part.get_filename():
                nombre = part.get_param("name", header="content-disposition") or ""
                campos[str(nombre)] = (part.get_payload(decode=True) or b"").decode("utf-8")
    return campos


def parse_multipart(content_type: str, body: bytes) -> list[tuple[str, str, bytes]]:
    raw = b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + body
    message = BytesParser(policy=policy.HTTP).parsebytes(raw)
    if not message.is_multipart():
        return []
    parts = []
    for part in message.iter_parts():
        filename = part.get_filename()
        if filename:
            name = part.get_param("name", header="content-disposition") or ""
            parts.append((str(name), filename, part.get_payload(decode=True) or b""))
    return parts


def create_app(
    token: str = config.DEV_TOKEN,
    data_dir: Path | None = None,
    state: AppState | None = None,
) -> FastAPI:
    state = state or AppState(data_dir or config.DATA_DIR, token, dev=config.DEV)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        programador = Programador(state)
        programador.iniciar()
        yield
        await programador.detener()
        with contextlib.suppress(Exception):
            await asistente.liberar(state)
        await state.close()

    app = FastAPI(title="nmwfm", version=config.VERSION, lifespan=lifespan)
    app.state.nm = state
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return error_response(exc.status_code, f"http_{exc.status_code}", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return error_response(422, "validacion", detail)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return error_response(500, "error_interno", str(exc) or exc.__class__.__name__)

    async def auth(request: Request) -> None:
        supplied = request.headers.get("x-token")
        if supplied is None and request.url.path.startswith("/files/"):
            supplied = request.query_params.get("token")
        if not supplied or not secrets.compare_digest(supplied, state.token):
            raise ApiError(401, "no_autorizado", "Token inválido o ausente.")

    router = APIRouter(dependencies=[Depends(auth)])

    def need_tarea(tarea_id: str) -> dict:
        tarea = state.storage.get_tarea(tarea_id)
        if tarea is None:
            raise ApiError(404, "tarea_no_encontrada", "La tarea no existe.")
        return tarea

    def need_insumo(insumo_id: str) -> dict:
        row = state.storage.get_insumo(insumo_id)
        if row is None:
            raise ApiError(404, "insumo_no_encontrado", "El insumo no existe.")
        return row

    @app.get("/health")
    async def health():
        return {"ok": True, "version": config.VERSION}

    @router.get("/settings")
    async def get_settings():
        return state.settings_public()

    @router.put("/settings")
    async def put_settings(body: dict):
        password = body.pop("password", None)
        values = {}
        for key in ("cuenta", "nombre", "matricula"):
            if key in body:
                if not isinstance(body[key], str):
                    raise ApiError(422, "validacion", f"{key} debe ser texto.")
                values[key] = body[key].strip()
        for key in ("entregar_sin_revisar", "reducir_animaciones"):
            if key in body:
                if not isinstance(body[key], bool):
                    raise ApiError(422, "validacion", f"{key} debe ser booleano.")
                values[key] = body[key]
        if "asistente_modelo" in body:
            modelo = body["asistente_modelo"]
            if not isinstance(modelo, str) or not modelo.strip():
                raise ApiError(422, "validacion", "asistente_modelo debe ser texto.")
            values["asistente_modelo"] = modelo.strip()
        if "asistente_keep_alive_s" in body:
            segundos = body["asistente_keep_alive_s"]
            if isinstance(segundos, bool) or not isinstance(segundos, int) or segundos < 1:
                raise ApiError(422, "validacion", "asistente_keep_alive_s debe ser un entero >= 1.")
            values["asistente_keep_alive_s"] = segundos
        if "recorte_modelo" in body:
            if body["recorte_modelo"] not in ("auto", "opencv"):
                raise ApiError(422, "validacion", "recorte_modelo debe ser 'auto' u 'opencv'.")
            values["recorte_modelo"] = body["recorte_modelo"]
        if "sync_cada_horas" in body:
            horas = body["sync_cada_horas"]
            if isinstance(horas, bool) or not isinstance(horas, int) or horas < 0:
                raise ApiError(422, "validacion", "sync_cada_horas debe ser un entero >= 0.")
            values["sync_cada_horas"] = horas
        state.storage.set_settings(values)
        if password:
            cuenta = state.storage.get_settings()["cuenta"]
            if not cuenta:
                raise ApiError(
                    400, "sin_cuenta", "Indica la cuenta antes de guardar la contraseña."
                )
            state.credentials.set(cuenta, str(password))
        return state.settings_public()

    @router.post("/siase/validar")
    async def siase_validar():
        return state.jobs.start(
            "validar_siase", lambda ctx: services.run_validar_siase(state, ctx)
        ).to_dict()

    @router.post("/diagnostico")
    async def diagnostico():
        activo = state.jobs.activo("diagnostico")
        if activo is not None:
            return activo.to_dict()
        services.require_credentials(state)
        return state.jobs.start(
            "diagnostico", lambda ctx: check.run_diagnostico(state, ctx)
        ).to_dict()

    @router.get("/respaldo")
    async def listar_respaldos():
        return respaldo.listar(state)

    @router.post("/respaldo")
    async def crear_respaldo():
        return await respaldo.crear(state)

    @router.post("/respaldo/restaurar")
    async def restaurar_respaldo(request: Request):
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            partes = parse_multipart(content_type, await request.body())
            if not partes:
                raise ApiError(400, "sin_archivos", "No se recibió ningún zip.")
            _, nombre, datos = partes[0]
            origen = respaldo.carpeta(state) / f"subido-{uuid.uuid4().hex[:8]}-{Path(nombre).name}"
            origen.write_bytes(datos)
        else:
            cuerpo = RestaurarBody(**(await request.json()))
            origen = respaldo.carpeta(state) / Path(cuerpo.nombre).name
            if not origen.is_file():
                raise ApiError(404, "respaldo_no_encontrado", "Ese respaldo no existe.")
        return await respaldo.restaurar(state, origen)

    @router.post("/herramientas/pdf")
    async def herramienta_pdf(request: Request, recortar: bool | None = None):
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            raise ApiError(
                400, "multipart_requerido", "Envía las imágenes como multipart/form-data."
            )
        cuerpo = await request.body()
        partes = parse_multipart(content_type, cuerpo)
        if recortar is None:
            valor = parse_campos(content_type, cuerpo).get("recortar", "true")
            recortar = valor.strip().lower() not in ("false", "0", "no")
        carpeta = state.paths.herramientas / f"subida-{uuid.uuid4().hex[:10]}"
        carpeta.mkdir(parents=True, exist_ok=True)
        rutas = []
        for i, (_, nombre, datos) in enumerate(partes):
            ruta = carpeta / f"{i}_{Path(nombre).name}"
            ruta.write_bytes(datos)
            rutas.append(ruta)
        pdf = await asyncio.to_thread(services.crear_pdf_imagenes, state, rutas, recortar)
        return {"pdf_url": state.file_url(pdf)}

    @router.post("/herramientas/portada")
    async def herramienta_portada(body: PortadaSueltaBody):
        return await asyncio.to_thread(
            services.generar_portada_suelta,
            state,
            body.profesor,
            body.materia,
            body.titulo,
            body.fecha,
        )

    @router.get("/asistente/estado")
    async def asistente_estado():
        return await asistente.estado(state)

    @router.post("/asistente/precalentar")
    async def asistente_precalentar():
        try:
            return await asistente.precalentar(state)
        except OllamaError as exc:
            raise ApiError(503, "ollama_no_disponible", str(exc)) from exc

    @router.post("/asistente/liberar")
    async def asistente_liberar():
        return await asistente.liberar(state)

    @router.post("/asistente/chat")
    async def asistente_chat(body: ChatBody):
        mensajes = [m.model_dump() for m in body.mensajes]

        async def eventos():
            async for evento in asistente.conversar(state, mensajes, body.tarea_id):
                yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            eventos(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/asistente/confirmar")
    async def asistente_confirmar(body: ConfirmarBody):
        resultado = await asistente.confirmar(state, body.id, body.aceptar)
        if resultado is None:
            raise ApiError(
                404, "confirmacion_no_encontrada", "La confirmación no existe o ya se usó."
            )
        return resultado

    @router.post("/gemini/login")
    async def gemini_login():
        return state.jobs.start(
            "login_gemini", lambda ctx: services.run_login_gemini(state, ctx)
        ).to_dict()

    @router.post("/sync")
    async def sync(body: SyncBody | None = None):
        activo = state.jobs.activo("sync")
        if activo is not None:
            return activo.to_dict()
        services.require_credentials(state)
        modo = body.modo if body else "auto"
        return state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, modo)).to_dict()

    @router.get("/novedades")
    async def novedades(no_leidas: int = 0):
        filas = state.storage.list_novedades(bool(no_leidas))
        return [{**f, "leida": bool(f["leida"])} for f in filas]

    @router.post("/novedades/leidas")
    async def novedades_leidas(body: LeidasBody | None = None):
        ids = body.ids if body else None
        return {"marcadas": state.storage.marcar_novedades_leidas(ids)}

    @router.get("/alertas")
    async def alertas():
        return services.tareas_alertas(state)

    @router.get("/materias")
    async def materias():
        return state.storage.list_materias()

    @router.get("/materias/{materia_id}/calificaciones")
    async def calificaciones(materia_id: str):
        if state.storage.get_materia(materia_id) is None:
            raise ApiError(404, "materia_no_encontrada", "La materia no existe.")
        return state.storage.get_calificaciones(materia_id)

    @router.get("/materias/{materia_id}/etapas")
    async def etapas(materia_id: str):
        if state.storage.get_materia(materia_id) is None:
            raise ApiError(404, "materia_no_encontrada", "La materia no existe.")
        etapas = state.storage.list_etapas(materia_id)
        for etapa in etapas:
            etapa["tareas"] = [services.con_vencida(t) for t in etapa["tareas"]]
        return etapas

    @router.post("/entregas/revisar")
    async def revisar_entregas():
        activo = state.jobs.activo("revisar_entregas")
        if activo is not None:
            return activo.to_dict()
        services.require_credentials(state)
        return state.jobs.start(
            "revisar_entregas", lambda ctx: services.run_revisar_entregas(state, ctx)
        ).to_dict()

    @router.get("/tareas/proximas")
    async def proximas():
        return services.tareas_proximas(state)

    @router.get("/tareas/{tarea_id}")
    async def tarea(tarea_id: str):
        need_tarea(tarea_id)
        detalle = state.storage.get_detalle(tarea_id)
        if detalle is None:
            detalle = await services.traer_detalle(state, tarea_id)
        return state.tarea_detalle_public(state.storage.get_tarea(tarea_id), detalle)

    @router.put("/tareas/{tarea_id}/indicaciones")
    async def put_indicaciones(tarea_id: str, body: IndicacionesBody):
        need_tarea(tarea_id)
        state.storage.set_indicaciones(tarea_id, body.indicaciones.strip())
        return state.tarea_detalle_public(
            state.storage.get_tarea(tarea_id), state.storage.get_detalle(tarea_id)
        )

    @router.get("/tareas/{tarea_id}/insumos")
    async def listar_insumos(tarea_id: str):
        need_tarea(tarea_id)
        return [state.insumo_public(r) for r in state.storage.list_insumos(tarea_id)]

    @router.post("/tareas/{tarea_id}/insumos")
    async def subir_insumos(tarea_id: str, request: Request):
        need_tarea(tarea_id)
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            raise ApiError(
                400, "multipart_requerido", "Envía las imágenes como multipart/form-data."
            )
        parts = parse_multipart(content_type, await request.body())
        if not parts:
            raise ApiError(400, "sin_archivos", "No se recibió ningún archivo.")
        creados = []
        for _, filename, data in parts:
            ext = Path(filename).suffix.lower()
            if ext not in IMAGE_EXTENSIONS:
                raise ApiError(400, "imagen_invalida", f"Formato no soportado: {filename}")
            insumo_id = uuid.uuid4().hex
            folder = state.paths.insumos / tarea_id
            folder.mkdir(parents=True, exist_ok=True)
            original = folder / f"{insumo_id}_orig{ext}"
            recortada = folder / f"{insumo_id}_crop.jpg"
            original.write_bytes(data)
            try:
                await asyncio.to_thread(
                    images.process_upload,
                    original,
                    recortada,
                    folder / f"{insumo_id}_thumb.jpg",
                    state.detector_recorte(),
                )
            except Exception as exc:
                original.unlink(missing_ok=True)
                raise ApiError(400, "imagen_invalida", f"No se pudo leer {filename}.") from exc
            row = state.storage.add_insumo(
                tarea_id,
                "imagen",
                id=insumo_id,
                original_path=str(original),
                recortada_path=str(recortada),
            )
            creados.append(state.insumo_public(row))
        return creados

    @router.post("/tareas/{tarea_id}/insumos/texto")
    async def insumo_texto(tarea_id: str, body: TextoBody):
        need_tarea(tarea_id)
        if not body.texto.strip():
            raise ApiError(422, "validacion", "El texto está vacío.")
        row = state.storage.add_insumo(tarea_id, "texto", texto=body.texto)
        return state.insumo_public(row)

    @router.patch("/insumos/{insumo_id}")
    async def patch_insumo(insumo_id: str, body: PatchInsumoBody):
        row = need_insumo(insumo_id)
        if body.texto is not None and row["tipo"] != "texto":
            raise ApiError(400, "no_es_texto", "Solo los insumos de texto tienen texto.")
        if body.ocr_texto is not None and row["tipo"] != "imagen":
            raise ApiError(400, "no_es_imagen", "Solo las imágenes tienen texto OCR.")
        state.storage.update_insumo(
            insumo_id,
            rotacion=body.rotacion,
            usar_recorte=body.usar_recorte,
            texto=body.texto,
            ocr_texto=body.ocr_texto,
        )
        if body.orden is not None:
            hermanos = [r["id"] for r in state.storage.list_insumos(row["tarea_id"])]
            hermanos.remove(insumo_id)
            hermanos.insert(max(0, min(body.orden, len(hermanos))), insumo_id)
            for i, hid in enumerate(hermanos):
                state.storage.update_insumo(hid, orden=i)
        return state.insumo_public(state.storage.get_insumo(insumo_id))

    @router.delete("/insumos/{insumo_id}", status_code=204)
    async def delete_insumo(insumo_id: str):
        row = need_insumo(insumo_id)
        state.storage.delete_insumo(insumo_id)
        if row["tipo"] == "imagen":
            crop = Path(row["recortada_path"])
            for path in (
                Path(row["original_path"]),
                crop,
                crop.with_name(f"{insumo_id}_thumb.jpg"),
            ):
                path.unlink(missing_ok=True)
        return Response(status_code=204)

    @router.post("/tareas/{tarea_id}/generar")
    async def generar(tarea_id: str, body: GenerarBody | None = None):
        need_tarea(tarea_id)
        extra = body.instrucciones_extra if body else None
        portada = body.portada.model_dump() if body and body.portada else None
        return state.jobs.start(
            "generar", lambda ctx: services.run_generar(state, ctx, tarea_id, extra, portada)
        ).to_dict()

    @router.get("/tareas/{tarea_id}/generacion")
    async def generacion(tarea_id: str):
        need_tarea(tarea_id)
        row = state.storage.get_generacion(tarea_id)
        return state.generacion_public(row) if row else None

    @router.get("/tareas/{tarea_id}/generaciones")
    async def generaciones(tarea_id: str):
        need_tarea(tarea_id)
        return services.listar_generaciones(state, tarea_id)

    @router.post("/generaciones/{hist_id}/restaurar")
    async def restaurar(hist_id: int):
        return services.restaurar_generacion(state, hist_id)

    @router.get("/tareas/{tarea_id}/portada-preview")
    async def portada_preview(
        tarea_id: str, profesor: str | None = None, titulo: str | None = None
    ):
        need_tarea(tarea_id)
        return await services.portada_preview(
            state, tarea_id, {"profesor": profesor, "titulo": titulo}
        )

    @router.post("/tareas/{tarea_id}/abrir-docx", status_code=204)
    async def abrir_docx(tarea_id: str):
        need_tarea(tarea_id)
        row = state.storage.get_generacion(tarea_id)
        if row is None or not Path(row["docx_path"]).exists():
            raise ApiError(404, "sin_generacion", "Esta tarea todavía no tiene documento.")
        os.startfile(row["docx_path"])  # type: ignore[attr-defined]
        return Response(status_code=204)

    @router.post("/tareas/{tarea_id}/reconstruir-pdf")
    async def reconstruir_pdf(tarea_id: str):
        need_tarea(tarea_id)
        return await services.reconstruir_pdf(state, tarea_id)

    @router.post("/tareas/{tarea_id}/entregar")
    async def entregar(tarea_id: str, body: EntregarBody):
        need_tarea(tarea_id)
        if not body.confirmar:
            raise ApiError(400, "sin_confirmacion", "Debes confirmar la entrega.")
        return state.jobs.start(
            "entregar", lambda ctx: services.run_entregar(state, ctx, tarea_id)
        ).to_dict()

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = state.jobs.get(job_id)
        if job is None:
            raise ApiError(404, "job_no_encontrado", "El job no existe.")
        return job.to_dict()

    @router.post("/jobs/{job_id}/continuar")
    async def continuar_job(job_id: str):
        job = state.jobs.resume(job_id)
        if job is None:
            raise ApiError(404, "job_no_encontrado", "El job no existe.")
        return job.to_dict()

    @router.get("/files/{path:path}")
    async def files(path: str):
        base = state.paths.data.resolve()
        target = (base / path).resolve()
        allowed = any(target.is_relative_to(base / d) for d in PUBLIC_DIRS)
        if not allowed or not target.is_file():
            raise ApiError(404, "archivo_no_encontrado", "El archivo no existe.")
        return FileResponse(target)

    app.include_router(router)

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        supplied = websocket.query_params.get("token", "")
        if not secrets.compare_digest(supplied, state.token):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        queue = state.jobs.subscribe()

        async def sender():
            while True:
                await websocket.send_json(await queue.get())

        async def receiver():
            while True:
                await websocket.receive_text()

        tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except WebSocketDisconnect:
            pass
        finally:
            for t in tasks:
                t.cancel()
            state.jobs.unsubscribe(queue)

    return app
