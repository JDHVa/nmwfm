import asyncio
from datetime import datetime, timedelta

from backend import scheduler, services
from backend.core import nexus
from backend.core.types import DetalleTarea, EtapaItem, MateriaCard, Portada, TareaItem

from .asgi_client import MiniClient

AHORA = datetime(2026, 10, 15, 12, 0)


def test_debe_sincronizar():
    assert not scheduler.debe_sincronizar(0, None, AHORA)
    assert scheduler.debe_sincronizar(2, None, AHORA)
    assert not scheduler.debe_sincronizar(2, AHORA - timedelta(hours=1), AHORA)
    assert scheduler.debe_sincronizar(2, AHORA - timedelta(hours=2), AHORA)


def preparar(state, horas=1, ultima=None):
    state.storage.set_settings({"cuenta": "1", "sync_cada_horas": horas})
    state.credentials.set("1", "pw")
    if ultima:
        state.storage.set_settings({"ultima_sync": ultima.isoformat()})


def test_programador_lanza_sync_cuando_toca(state, monkeypatch):
    llamadas = []

    async def falso(st, ctx, modo="auto"):
        llamadas.append(modo)
        return {}

    monkeypatch.setattr(scheduler, "run_sync", falso)
    preparar(state, 1, AHORA - timedelta(hours=3))
    prog = scheduler.Programador(state, reloj=lambda: AHORA)

    async def escenario():
        job = await prog.revisar()
        assert job is not None and job.tipo == "sync"
        await asyncio.sleep(0.05)
        segundo = await prog.revisar()
        return segundo

    assert asyncio.run(escenario()) is None
    assert llamadas == ["auto"]


def test_programador_no_corre_apagado_reciente_ni_sin_credenciales(state, monkeypatch):
    async def falso(st, ctx, modo="auto"):
        return {}

    monkeypatch.setattr(scheduler, "run_sync", falso)

    async def revisar(prog):
        return await prog.revisar()

    prog = scheduler.Programador(state, reloj=lambda: AHORA)
    preparar(state, 0, AHORA - timedelta(hours=9))
    assert asyncio.run(revisar(prog)) is None
    preparar(state, 2, AHORA - timedelta(minutes=30))
    assert asyncio.run(revisar(prog)) is None
    state.storage.set_settings(
        {"cuenta": "", "ultima_sync": (AHORA - timedelta(hours=9)).isoformat()}
    )
    assert asyncio.run(revisar(prog)) is None


def test_programador_respeta_sync_en_curso(state, monkeypatch):
    preparar(state, 1, AHORA - timedelta(hours=9))

    async def lento(ctx):
        await asyncio.sleep(0.3)

    async def escenario():
        state.jobs.start("sync", lento)
        await asyncio.sleep(0.02)
        return await scheduler.Programador(state, reloj=lambda: AHORA).revisar()

    assert asyncio.run(escenario()) is None


def test_settings_sync_cada_horas_validacion(client):
    assert client.put("/settings", json={"sync_cada_horas": 6}).json()["sync_cada_horas"] == 6
    for malo in (-1, "2", 1.5, True):
        assert client.put("/settings", json={"sync_cada_horas": malo}).status_code == 422


class Nexus:
    def __init__(self, monkeypatch):
        self.titulo = "Dimensión 1 - Ficha"
        self.extra = False
        self.hasta = "2026-11-01T00:00"
        self.contenido = "contenido v1"

        async def ensure(st, hooks, **kw):
            return _Pagina()

        async def leer(page):
            return [MateriaCard("100", "Lógica", 0)]

        async def abrir_materia(page, i, nombre=None):
            return Portada("PROFE", "p", None)

        async def abrir_estructura(page):
            tareas = [TareaItem("1.1", self.titulo, "dimension", 2.0, None, 0)]
            if self.extra:
                tareas.append(TareaItem("1.2", "Dimensión 2 - Mapa", "dimension", 2.0, None, 1))
            return [EtapaItem("E1", "d", 0, tareas)]

        async def abrir_tarea(page, e, t, numero=None, **kw):
            return DetalleTarea(
                "T", numero, None, self.hasta, 2.0, None, "act", self.contenido, "crit", None
            )

        async def nada(page):
            return None

        monkeypatch.setattr(services, "ensure_nexus", ensure)
        monkeypatch.setattr(nexus, "leer_materias", leer)
        monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
        monkeypatch.setattr(nexus, "abrir_estructura", abrir_estructura)
        monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
        monkeypatch.setattr(nexus, "volver_a_estructura", nada)
        monkeypatch.setattr(nexus, "volver_a_lista", nada)


class _Cuenta:
    def __init__(self, sel):
        self.sel = sel

    async def count(self):
        return 0 if "sesi" in self.sel else 1


class _Pagina:
    url = "https://plataformanexus.uanl.mx/#/App"

    def is_closed(self):
        return False

    def locator(self, sel):
        return _Cuenta(sel)

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


def sync(state, modo):
    async def escenario():
        job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, modo))
        for _ in range(300):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    job = asyncio.run(escenario())
    assert job.estado == "ok", job.mensaje
    return job


def test_primer_sync_no_genera_novedades_y_los_siguientes_si(state, monkeypatch):
    fake = Nexus(monkeypatch)
    sync(state, "auto")
    assert state.storage.list_novedades() == []

    fake.titulo = "Dimensión 1 - Ficha técnica"
    fake.extra = True
    sync(state, "incremental")
    novedades = state.storage.list_novedades()
    tipos = {(n["numero"], n["tipo"]) for n in novedades}
    assert tipos == {("1.1", "modificada"), ("1.2", "nueva")}
    titulo = next(n for n in novedades if n["numero"] == "1.1")
    assert "Ficha →" in titulo["detalle"] and titulo["materia_nombre"] == "Lógica"

    sync(state, "incremental")
    assert len(state.storage.list_novedades()) == 2


def test_cambios_de_fecha_y_contenido_se_detectan(state, monkeypatch):
    fake = Nexus(monkeypatch)
    sync(state, "auto")
    fake.hasta = "2026-11-05T00:00"
    fake.contenido = "contenido v2"
    sync(state, "completo")
    nov = [n for n in state.storage.list_novedades() if n["numero"] == "1.1"]
    assert len(nov) == 1
    assert "Fecha de entrega: 2026-11-01T00:00 → 2026-11-05T00:00" in nov[0]["detalle"]
    assert "Contenido actualizado" in nov[0]["detalle"]


def test_api_novedades_y_marcar_leidas(app, state, monkeypatch):
    fake = Nexus(monkeypatch)
    sync(state, "auto")
    fake.extra = True
    sync(state, "incremental")
    fake.titulo = "Otro título"
    sync(state, "incremental")
    client = MiniClient(app, headers={"X-Token": "dev"})
    lista = client.get("/novedades").json()
    assert len(lista) == 2 and all(n["leida"] is False for n in lista)
    r = client.post("/novedades/leidas", json={"ids": [lista[0]["id"]]})
    assert r.json() == {"marcadas": 1}
    assert len(client.get("/novedades?no_leidas=1").json()) == 1
    assert client.post("/novedades/leidas").json() == {"marcadas": 1}
    assert client.get("/novedades?no_leidas=1").json() == []


def test_alertas_hoy_y_manana(state, seeded):
    st = state.storage
    st.replace_estructura(
        "100",
        [
            EtapaItem(
                "E",
                "d",
                0,
                [TareaItem(f"1.{k}", f"T{k}", "evidencia", 1.0, None, k) for k in range(1, 6)],
            )
        ],
    )
    for tid, hasta, estado in (
        ("100-1.1", "2026-10-15T23:59", "pendiente"),
        ("100-1.2", "2026-10-16T08:00", "pendiente"),
        ("100-1.3", "2026-10-17T08:00", "pendiente"),
        ("100-1.4", "2026-10-15T09:00", "pendiente"),
        ("100-1.5", "2026-10-15T20:00", "entregada"),
    ):
        st._run("UPDATE tareas SET hasta = ?, estado = ? WHERE id = ?", (hasta, estado, tid))
    alertas = services.tareas_alertas(state, AHORA)
    assert [(a["id"], a["dias"]) for a in alertas] == [("100-1.1", 0), ("100-1.2", 1)]
    assert all(a["materia_nombre"] == "Lógica" and a["vencida"] is False for a in alertas)


def test_api_alertas(app, seeded):
    client = MiniClient(app, headers={"X-Token": "dev"})
    assert client.get("/alertas").status_code == 200
