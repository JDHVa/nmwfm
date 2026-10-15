import pytest

from backend.api import create_app
from backend.core.storage import Credentials
from backend.core.types import EtapaItem, TareaItem
from backend.services import AppState

from .asgi_client import MiniClient


class MemoryCredentials(Credentials):
    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, cuenta):
        return self.store.get(cuenta)

    def set(self, cuenta, password):
        self.store[cuenta] = password

    def delete(self, cuenta):
        self.store.pop(cuenta, None)


@pytest.fixture
def state(tmp_path):
    st = AppState(tmp_path / "data", "dev", dev=True, credentials=MemoryCredentials())
    yield st
    st.storage.close()


@pytest.fixture
def app(state):
    return create_app(state=state)


@pytest.fixture
def client(app):
    return MiniClient(app, headers={"X-Token": "dev"})


@pytest.fixture
def seeded(state):
    state.storage.upsert_materia("100", "Lógica", 0)
    state.storage.set_portada("100", "PROFE UNO", "Del 03/AGOSTO/2026 al 18/DICIEMBRE/2026")
    state.storage.replace_estructura(
        "100",
        [
            EtapaItem(
                "Etapa 1: Uno",
                "Desc",
                0,
                [TareaItem("1.1", "Dimensión 1 - Algo", "dimension", 0.0, "Individual", 0)],
            )
        ],
    )
    return state
