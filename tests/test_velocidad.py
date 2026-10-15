import asyncio
import json
import time

from backend import services
from backend.core import metricas, nexus
from backend.core.apicatalog import Catalogo, forma, plantilla_url
from backend.core.types import DetalleTarea, EtapaItem, MateriaCard, Portada, TareaItem


def test_plantilla_url_sin_tokens_ni_ids():
    url = "https://plataformanexus.uanl.mx/api/cursos/746214/tareas/abcdef0123456789abcd?token=SECRETO&x=1"
    plantilla = plantilla_url(url)
    assert "SECRETO" not in plantilla and "746214" not in plantilla
    assert plantilla.endswith("/api/cursos/{id}/tareas/{id}?token&x")


def test_forma_trunca_y_resume():
    dato = {"a": 1, "b": [{"c": "x", "d": [1, 2]}, {"c": "y"}], "e": {"f": {"g": {"h": {"i": 1}}}}}
    resumen = forma(dato)
    assert resumen["a"] == "int"
    assert resumen["b"][1] == "len=2" and resumen["b"][0]["c"] == "str"
    assert "{...}" in json.dumps(resumen)


class _Peticion:
    def __init__(self, tipo, metodo="GET"):
        self.resource_type = tipo
        self.method = metodo


class _Respuesta:
    def __init__(self, url, cuerpo, tipo="xhr", status=200):
        self.url = url
        self.status = status
        self.request = _Peticion(tipo)
        self._cuerpo = cuerpo

    async def json(self):
        if self._cuerpo is None:
            raise ValueError("no json")
        return self._cuerpo


NEXUS = "https://plataformanexus.uanl.mx/api/tareas/123456?auth=t"


def test_catalogo_registra_solo_xhr_fetch_de_nexus_y_guarda_en_dev(tmp_path):
    catalogo = Catalogo(tmp_path / "api")

    async def escenario():
        await catalogo.procesar(_Respuesta(NEXUS, {"titulo": "x", "items": [{"id": 1}]}))
        await catalogo.procesar(_Respuesta(NEXUS, {"titulo": "y"}, tipo="fetch"))
        await catalogo.procesar(_Respuesta(NEXUS, {"a": 1}, tipo="image"))
        await catalogo.procesar(_Respuesta("https://otro.com/api/x", {"a": 1}))
        await catalogo.procesar(_Respuesta(NEXUS + "&z=1", None))

    asyncio.run(escenario())
    assert len(catalogo.endpoints) == 2
    ruta = catalogo.guardar()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert {d["forma"] if isinstance(d["forma"], str) else "dict" for d in datos} == {
        "dict",
        "no-json",
    }
    assert all("auth=t" not in json.dumps(d) for d in datos)


def test_catalogo_sin_directorio_no_escribe():
    catalogo = Catalogo(None)
    asyncio.run(catalogo.procesar(_Respuesta(NEXUS, {"a": 1})))
    assert catalogo.guardar() is None


def test_esperar_json_devuelve_la_respuesta_posterior():
    catalogo = Catalogo(None)

    async def escenario():
        await catalogo.procesar(_Respuesta(NEXUS, {"version": "vieja"}))
        await asyncio.sleep(0.05)
        desde = time.monotonic()

        async def llega():
            await asyncio.sleep(0.1)
            await catalogo.procesar(_Respuesta(NEXUS, {"version": "nueva"}))

        tarea = asyncio.create_task(llega())
        cuerpo = await catalogo.esperar_json(r"/api/tareas/", desde, timeout=2)
        await tarea
        return cuerpo, await catalogo.esperar_json(r"/api/otra/", desde, timeout=0.1)

    cuerpo, ausente = asyncio.run(escenario())
    assert cuerpo == {"version": "nueva"} and ausente is None


def test_metricas_resumen():
    m = metricas.Metricas()
    m.registrar("tarea", 2.0)
    m.registrar("tarea", 4.0)
    assert m.resumen()["tarea"] == {"n": 2, "total_s": 6.0, "media_s": 3.0}
    assert "tarea: 2x" in m.texto()


def test_medir_sin_contexto_no_falla():
    async def escenario():
        async with metricas.medir("x"):
            return 1

    assert asyncio.run(escenario()) == 1


class _Cuenta:
    def __init__(self, n=1):
        self.n = n

    async def count(self):
        return self.n


class _Pagina:
    url = "https://plataformanexus.uanl.mx/#/App"

    def __init__(self, paneles=True):
        self.paneles = paneles

    def is_closed(self):
        return False

    def on(self, evento, manejador):
        return None

    def locator(self, sel):
        if "sesi" in sel:
            return _Cuenta(0)
        return _Cuenta(1 if self.paneles else 0)

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


def test_no_vuelve_a_estructura_si_el_panel_sigue_visible(monkeypatch):
    llamadas = []

    async def volver(page):
        llamadas.append(1)

    monkeypatch.setattr(nexus, "volver_a_estructura", volver)
    asyncio.run(services._a_estructura(_Pagina(True), 0, "M"))
    assert llamadas == []
    asyncio.run(services._a_estructura(_Pagina(False), 0, "M"))
    assert llamadas == [1]


def test_sync_reporta_tiempos_por_fase(state, monkeypatch):
    async def ensure(st, hooks, **kw):
        return _Pagina()

    async def leer(page):
        return [MateriaCard("100", "Lógica", 0)]

    async def abrir_materia(page, i, nombre=None):
        return Portada("P", "p", None)

    async def abrir_estructura(page):
        return [
            EtapaItem("E", "d", 0, [TareaItem("1.1", "Dimensión 1", "dimension", 1.0, None, 0)])
        ]

    async def abrir_tarea(page, e, t, numero=None, **kw):
        async with metricas.medir("rubrica"):
            pass
        return DetalleTarea("T", "1.1", None, None, 1.0, None, "a", "c", "k", None)

    async def nada(page):
        return None

    monkeypatch.setattr(services, "ensure_nexus", ensure)
    monkeypatch.setattr(nexus, "leer_materias", leer)
    monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
    monkeypatch.setattr(nexus, "abrir_estructura", abrir_estructura)
    monkeypatch.setattr(nexus, "abrir_tarea", abrir_tarea)
    monkeypatch.setattr(nexus, "volver_a_estructura", nada)
    monkeypatch.setattr(nexus, "volver_a_lista", nada)
    cola = state.jobs.subscribe()

    async def escenario():
        job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, "completo"))
        for _ in range(300):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    job = asyncio.run(escenario())
    assert job.estado == "ok", job.mensaje
    tiempos = job.resultado["tiempos"]
    assert {"login", "materia", "tarea", "rubrica"} <= set(tiempos)
    assert tiempos["tarea"]["n"] == 1
    mensajes = []
    while not cola.empty():
        mensajes.append(cola.get_nowait())
    assert any(m.get("type") == "log" and m["message"].startswith("Tiempos ·") for m in mensajes)
