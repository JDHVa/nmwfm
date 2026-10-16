import asyncio
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from .services import ApiError, AppState

BASE_DATOS = "nmwfm.db"
EXCLUIDOS = ("browser_profile", "gemini_profile", "respaldos", "debug")
JOBS_ACTIVOS = ("en_cola", "corriendo", "esperando_usuario")


def carpeta(state: AppState) -> Path:
    destino = state.paths.data / "respaldos"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _publico(state: AppState, ruta: Path) -> dict:
    return {
        "nombre": ruta.name,
        "url": state.file_url(ruta),
        "bytes": ruta.stat().st_size,
        "creado_en": datetime.fromtimestamp(ruta.stat().st_mtime).isoformat(timespec="seconds"),
    }


def listar(state: AppState) -> list[dict]:
    zips = sorted(carpeta(state).glob("*.zip"), key=lambda r: r.stat().st_mtime, reverse=True)
    return [_publico(state, ruta) for ruta in zips]


def _crear(state: AppState, prefijo: str) -> Path:
    destino = carpeta(state) / f"{prefijo}-{datetime.now():%Y%m%d-%H%M%S}.zip"
    raiz = state.paths.data
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / BASE_DATOS
        state.storage.copiar_a(copia)
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(copia, BASE_DATOS)
            for ruta in sorted(raiz.rglob("*")):
                relativa = ruta.relative_to(raiz)
                if not ruta.is_file() or relativa.parts[0] in EXCLUIDOS:
                    continue
                if relativa.name.startswith(BASE_DATOS):
                    continue
                zf.write(ruta, relativa.as_posix())
    return destino


async def crear(state: AppState, prefijo: str = "nmwfm") -> dict:
    return _publico(state, await asyncio.to_thread(_crear, state, prefijo))


def _miembros_seguros(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    miembros = []
    for info in zf.infolist():
        ruta = PurePosixPath(info.filename.replace("\\", "/"))
        if info.is_dir():
            continue
        if ruta.is_absolute() or ".." in ruta.parts or (ruta.parts and ":" in ruta.parts[0]):
            raise ApiError(400, "respaldo_invalido", "El zip contiene rutas no permitidas.")
        if ruta.parts and ruta.parts[0] in EXCLUIDOS:
            continue
        miembros.append(info)
    if not any(m.filename == BASE_DATOS for m in miembros):
        raise ApiError(400, "respaldo_invalido", "El zip no contiene la base de datos.")
    return miembros


def _restaurar(state: AppState, origen: Path) -> int:
    try:
        zf = zipfile.ZipFile(origen)
    except zipfile.BadZipFile as exc:
        raise ApiError(400, "respaldo_invalido", "El archivo no es un zip válido.") from exc
    with zf:
        miembros = _miembros_seguros(zf)
        raiz = state.paths.data
        state.storage.close()
        try:
            for info in miembros:
                destino = raiz / info.filename
                destino.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as fuente, open(destino, "wb") as salida:
                    shutil.copyfileobj(fuente, salida)
        finally:
            state.storage.reabrir()
    return len(miembros)


def _validar(origen: Path) -> None:
    if not zipfile.is_zipfile(origen):
        raise ApiError(400, "respaldo_invalido", "El archivo no es un zip válido.")
    with zipfile.ZipFile(origen) as zf:
        _miembros_seguros(zf)


async def restaurar(state: AppState, origen: Path) -> dict:
    if any(job.estado in JOBS_ACTIVOS for job in state.jobs.jobs.values()):
        raise ApiError(409, "jobs_en_curso", "Espera a que terminen los trabajos en curso.")
    origen = Path(origen)
    _validar(origen)
    previo = await crear(state, "pre-restauracion")
    cantidad = await asyncio.to_thread(_restaurar, state, origen)
    return {"restaurados": cantidad, "respaldo_previo": previo["nombre"]}
