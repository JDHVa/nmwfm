import hashlib
import sys
import urllib.request
from pathlib import Path

from .. import config


class ModeloError(Exception):
    pass


def ruta_modelo(carpeta: Path) -> Path:
    return carpeta / config.MODELO_RECORTE_ARCHIVO


def modelo_disponible(carpeta: Path) -> bool:
    return ruta_modelo(carpeta).is_file()


def _sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def descargar_modelo(
    carpeta: Path, url: str | None = None, sha256: str | None = None, forzar: bool = False
) -> Path:
    destino = ruta_modelo(carpeta)
    if destino.is_file() and not forzar:
        return destino
    url = url or config.MODELO_RECORTE_URL
    esperado = (config.MODELO_RECORTE_SHA256 if sha256 is None else sha256).lower()
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as respuesta, open(temporal, "wb") as salida:
            while bloque := respuesta.read(1 << 20):
                salida.write(bloque)
        if esperado and _sha256(temporal) != esperado:
            raise ModeloError("El hash del modelo descargado no coincide.")
        temporal.replace(destino)
    except Exception:
        temporal.unlink(missing_ok=True)
        raise
    return destino


def main() -> None:
    destino = descargar_modelo(config.DATA_DIR / "models", forzar="--forzar" in sys.argv)
    print(f"Modelo listo en {destino}")


if __name__ == "__main__":
    main()
