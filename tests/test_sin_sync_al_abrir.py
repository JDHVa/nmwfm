import asyncio

from backend.api import create_app


def test_abrir_la_app_no_lanza_ningun_sync(state):
    state.storage.set_settings({"cuenta": "1"})
    state.credentials.set("1", "pw")
    assert state.storage.get_settings()["sync_inicial_hecha"] is False
    app = create_app(state=state)

    async def escenario():
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.15)
            return list(state.jobs.jobs.values())

    assert asyncio.run(escenario()) == []


def test_el_programador_esta_apagado_por_defecto(state):
    assert state.storage.get_settings()["sync_cada_horas"] == 0
