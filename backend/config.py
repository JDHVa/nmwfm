import os
import sys
from pathlib import Path

from . import __version__

VERSION = __version__
DEV = os.environ.get("NMWFM_DEV", "1").lower() not in ("0", "false", "no")

if getattr(sys, "frozen", False):
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = ROOT

DATA_DIR = Path(os.environ.get("NMWFM_DATA_DIR", ROOT / "data"))
PORTADA_TEMPLATE = RESOURCE_DIR / "portada_word.docx"
PROMPTS_RELATIVO = Path("backend") / "core" / "prompts"


def directorio_prompts() -> Path:
    return RESOURCE_DIR / PROMPTS_RELATIVO


DEV_PORT = 8765
DEV_TOKEN = "dev"
KEYRING_SERVICE = "nmwfm"

CORS_ORIGINS = [
    "http://localhost:1420",
    "tauri://localhost",
    "http://tauri.localhost",
]

MODELO_RECORTE_ARCHIVO = "u2netp.onnx"
MODELO_RECORTE_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
MODELO_RECORTE_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"

SIASE_URL = "https://www.uanl.mx/enlinea/"
NEXUS_URL_FRAGMENT = "plataformanexus.uanl.mx/#/App/UnidadesAprendizaje"
NEXUS_LISTA_URL = "https://" + NEXUS_URL_FRAGMENT
GEMINI_URL = "https://gemini.google.com/app"

GEMINI_RESPONSE_TIMEOUT_S = 300
USER_WAIT_TIMEOUT_S = 900


class Paths:
    def __init__(self, data_dir: Path):
        self.data = Path(data_dir)
        self.db = self.data / "nmwfm.db"
        self.browser_profile = self.data / "browser_profile"
        self.insumos = self.data / "insumos"
        self.generaciones = self.data / "generaciones"
        self.debug = self.data / "debug"
        self.models = self.data / "models"

    def ensure(self) -> None:
        for p in (self.data, self.insumos, self.generaciones, self.debug, self.models):
            p.mkdir(parents=True, exist_ok=True)
