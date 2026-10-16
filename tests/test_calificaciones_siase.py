import asyncio
from pathlib import Path

import pytest

from backend import services
from backend.core import selectors as S
from backend.core import siase

from .asgi_client import MiniClient

DATOS = Path(__file__).parent / "html_reales"
HTML = (DATOS / "siase_evaluacion.html").read_text(encoding="utf-8")
KARDEX_HTML = (DATOS / "siase_kardex.html").read_text(encoding="utf-8")
KARDEX = siase.parse_kardex(KARDEX_HTML)


def por_clave(materias):
    return {m["clave"]: m for m in materias}


def test_parser_lee_las_diez_materias_del_html_real():
    materias = siase.parse_evaluacion(HTML)
    assert [m["clave"] for m in materias] == [
        "015",
        "019",
        "026",
        "030",
        "033",
        "095",
        "644",
        "645",
        "646",
        "672",
    ]
    assert materias[0]["nombre"] == "Introducción a las Ciencias Sociales"
    assert materias[0]["grupo"] == "5V1"


def test_parser_respeta_el_orden_de_columnas_del_encabezado():
    sociales = por_clave(siase.parse_evaluacion(HTML))["015"]["notas"]
    assert sociales["par1"] == {"cal": 100.0, "pts": 10.0}
    assert sociales["par2"] == {"cal": None, "pts": None}
    assert sociales["portafolio"] == {"cal": 35.0, "pts": 14.0}
    assert sociales["emt"] == {"cal": 92.0, "pts": 13.8}
    assert sociales["eg"] == {"cal": None, "pts": None}


def test_parser_calidad_es_carrera_y_vocacional_esta_vacia():
    materias = por_clave(siase.parse_evaluacion(HTML))
    assert materias["095"]["notas"]["portafolio"] == {"cal": 39.0, "pts": 19.5}
    assert materias["095"]["total"] == 43.0
    assert all(n == {"cal": None, "pts": None} for n in materias["019"]["notas"].values())
    assert materias["019"]["total"] == 0.0


def test_parser_sin_tabla_devuelve_vacio():
    assert siase.parse_evaluacion("<div>Sin datos</div>") == []
    assert siase.parse_evaluacion("") == []


class Loc:
    def __init__(self, frame, selector):
        self.frame = frame
        self.selector = selector

    first = property(lambda self: self)

    async def count(self):
        return 1 if self.selector in self.frame.presentes() else 0

    async def evaluate(self, script):
        if "options" in script:
            return ["0", "0x3b9471", "0x3b9999"][: self.frame.opciones]
        return None

    async def wait_for(self, **kw):
        return None

    async def select_option(self, valor):
        self.frame.eventos.append(("select", valor))

    async def click(self, **kw):
        self.frame.eventos.append(("click", self.selector))
        siguiente = self.frame.flujo.get(self.selector)
        if siguiente:
            self.frame.etapa = siguiente

    async def dispatch_event(self, nombre):
        raise AssertionError("el clic real debia funcionar")


class Frame:
    def __init__(self, opciones=2):
        self.etapa = "inicio"
        self.eventos = []
        self.opciones = opciones
        self.flujo = {
            S.SIASE_CARRERA_LINK: "menu",
            S.SIASE_MENU_EVALUACION: "periodo",
            S.SIASE_EVAL_ACEPTAR: "tabla",
            S.SIASE_MENU_KARDEX: "kardex",
        }

    def presentes(self):
        return {
            "inicio": {S.SIASE_NEXUS_LOGO, S.SIASE_CARRERA_LINK},
            "menu": {S.SIASE_MENU_EVALUACION},
            "periodo": {S.SIASE_PERIODO_SELECT, S.SIASE_EVAL_ACEPTAR},
            "tabla": {S.SIASE_EVAL_TABLA, S.SIASE_MENU_KARDEX},
            "kardex": {S.SIASE_KARDEX_TABLA, S.SIASE_MENU_KARDEX},
        }[self.etapa]

    def locator(self, selector):
        return Loc(self, selector)

    async def content(self):
        return KARDEX_HTML if self.etapa == "kardex" else HTML


class Page:
    def __init__(self, frame):
        self.frames = [frame]
        self.cerrada = False
        self.visitada = None

    async def goto(self, url, **kw):
        self.visitada = url

    async def close(self):
        self.cerrada = True


class Ctx:
    def __init__(self, frame):
        self.frame = frame
        self.pagina = None

    async def new_page(self):
        self.pagina = Page(self.frame)
        return self.pagina


def test_flujo_carrera_evaluacion_periodo_aceptar_y_tabla():
    frame = Frame()
    ctx = Ctx(frame)
    materias, kardex = asyncio.run(siase.leer_calificaciones(ctx, "c", "p"))
    assert len(materias) == 10 and len(kardex) == 5
    assert [e for e in frame.eventos if e[0] == "click"] == [
        ("click", S.SIASE_CARRERA_LINK),
        ("click", S.SIASE_MENU_EVALUACION),
        ("click", S.SIASE_EVAL_ACEPTAR),
        ("click", S.SIASE_MENU_KARDEX),
    ]
    assert ("select", "0x3b9471") in frame.eventos
    assert ctx.pagina.cerrada


def test_flujo_sin_periodos_falla_y_cierra_la_pagina():
    frame = Frame(opciones=1)
    ctx = Ctx(frame)
    with pytest.raises(siase.SiaseError, match="periodos"):
        asyncio.run(siase.leer_calificaciones(ctx, "c", "p"))
    assert ctx.pagina.cerrada


def test_el_selector_de_periodo_y_la_tabla_estan_centralizados():
    assert S.SIASE_PERIODO_SELECT == "select[name='HTMLPeriodo']"
    assert "econeva01" in S.SIASE_MENU_EVALUACION
    assert set(S.SIASE_EVAL_COLUMNAS.values()) == {"par1", "par2", "portafolio", "emt", "eg"}


def correr(state):
    async def escenario():
        job = state.jobs.start(
            "calificaciones_siase", lambda ctx: services.run_calificaciones_siase(state, ctx)
        )
        for _ in range(200):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    return asyncio.run(escenario())


def preparar(state, monkeypatch, materias=None, error=None, kardex=None):
    state.storage.set_settings({"cuenta": "123"})
    state.credentials.set("123", "pw")
    llamadas = []

    async def contexto():
        return object()

    async def leer(ctx, cuenta, password, hooks=None):
        llamadas.append((cuenta, password))
        if error:
            raise error
        return materias, KARDEX if kardex is None else kardex

    monkeypatch.setattr(state.browser, "context", contexto)
    monkeypatch.setattr(siase, "leer_calificaciones", leer)
    return llamadas


def test_job_guarda_la_tabla(state, monkeypatch):
    llamadas = preparar(state, monkeypatch, siase.parse_evaluacion(HTML))
    job = correr(state)
    assert job.estado == "ok" and job.resultado == {"materias": 10, "kardex": 5}
    assert llamadas == [("123", "pw")]
    guardado = state.storage.get_siase_calificaciones()
    assert len(guardado["materias"]) == 10 and guardado["leida_en"]


def test_job_espera_el_lock_del_navegador(state, monkeypatch):
    llamadas = preparar(state, monkeypatch, siase.parse_evaluacion(HTML))

    async def escenario():
        async with state.browser.lock:
            job = state.jobs.start(
                "calificaciones_siase", lambda ctx: services.run_calificaciones_siase(state, ctx)
            )
            await asyncio.sleep(0.2)
            assert job.estado == "corriendo" and llamadas == []
        for _ in range(250):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    job = asyncio.run(escenario())
    assert job.estado == "ok" and len(llamadas) == 1


def test_job_sin_materias_es_error(state, monkeypatch):
    preparar(state, monkeypatch, [])
    job = correr(state)
    assert job.estado == "error" and "materias" in job.mensaje
    assert state.storage.get_siase_calificaciones() is None


def test_job_propaga_errores_de_siase(state, monkeypatch):
    preparar(state, monkeypatch, error=siase.SiaseError("SIASE no mostro la tabla"))
    job = correr(state)
    assert job.estado == "error" and job.mensaje == "SIASE no mostro la tabla"


def test_endpoint_crea_el_job_una_sola_vez(client, state, monkeypatch):
    preparar(state, monkeypatch, siase.parse_evaluacion(HTML))

    async def lento(ctx, cuenta, password, hooks=None):
        await asyncio.sleep(0.3)
        return siase.parse_evaluacion(HTML), KARDEX

    monkeypatch.setattr(siase, "leer_calificaciones", lento)

    async def escenario():
        a = (await client.arequest("POST", "/siase/calificaciones")).json()
        b = (await client.arequest("POST", "/siase/calificaciones")).json()
        assert a["tipo"] == "calificaciones_siase" and a["id"] == b["id"]
        for _ in range(100):
            job = (await client.arequest("GET", f"/jobs/{a['id']}")).json()
            if job["estado"] in ("ok", "error"):
                return job
            await asyncio.sleep(0.05)

    job = asyncio.run(escenario())
    assert job["estado"] == "ok" and job["resultado"] == {"materias": 10, "kardex": 5}


def test_endpoint_sin_credenciales_es_400(client):
    r = client.post("/siase/calificaciones")
    assert r.status_code == 400 and r.json()["error"]["code"] == "sin_credenciales"


def test_endpoint_requiere_token(app):
    assert MiniClient(app).post("/siase/calificaciones").status_code in (401, 403)


class Manager:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.cierres = 0

    async def close(self):
        self.cierres += 1


def test_cancelar_no_cierra_el_navegador_compartido(state, client):
    state.browser = Manager()

    async def escenario():
        dentro = asyncio.Event()

        async def largo(ctx):
            dentro.set()
            await asyncio.sleep(60)

        job = state.jobs.start("calificaciones_siase", largo)
        await dentro.wait()
        return (await client.arequest("POST", f"/jobs/{job.id}/cancelar")).json()

    datos = asyncio.run(escenario())
    assert datos["estado"] == "error" and datos["resultado"] == {"cancelado": True}
    assert state.browser.cierres == 0


def test_parser_kardex_toma_la_ultima_oportunidad_e_ignora_filas_sin_calificacion():
    assert [(f["semestre"], f["clave"], f["calificacion"], f["oportunidad"]) for f in KARDEX] == [
        (1, "001", 100.0, 1),
        (1, "002", 85.0, 2),
        (1, "003", 95.0, 1),
        (2, "004", 90.0, 1),
        (2, "005", 80.0, 3),
    ]
    assert KARDEX[0]["nombre"] == "Algebra Inventada"


def test_job_guarda_el_kardex_en_el_historial(state, monkeypatch):
    preparar(state, monkeypatch, siase.parse_evaluacion(HTML))
    assert correr(state).estado == "ok"
    filas = state.storage.get_historial_calificaciones()
    assert [s["periodo"] for s in filas] == ["Semestre 1", "Semestre 2"]
    assert filas[0]["materias"][1] == {
        "nombre": "Lectura Ficticia",
        "clave": "002",
        "tipo": None,
        "total": 85.0,
    }
    preparar(state, monkeypatch, siase.parse_evaluacion(HTML), kardex=KARDEX[:1])
    assert correr(state).estado == "ok"
    assert len(state.storage.get_historial_calificaciones()[0]["materias"]) == 1


def test_kardex_fusiona_con_el_historial_importado(state, monkeypatch):
    state.storage.set_historial_calificaciones(
        [
            {
                "periodo": "Agosto-Diciembre 2025",
                "materias": [
                    {"nombre": "Álgebra inventada", "tipo": "carrera", "emt": 80, "total": 90}
                ],
            },
            {
                "periodo": "2do semestre",
                "materias": [{"nombre": None, "tipo": "carrera", "total": 77}],
            },
        ]
    )
    preparar(state, monkeypatch, siase.parse_evaluacion(HTML))
    assert correr(state).estado == "ok"
    semestres = services.historial_semestres(state)
    todas = [m for s in semestres for m in s["materias"]]
    algebra = next(m for m in todas if m["nombre"] == "Álgebra inventada")
    assert algebra["total"] == 100.0 and algebra["emt"] == 80
    assert not any(m["nombre"] == "Algebra Inventada" for m in todas)
    assert not any(m["nombre"] == "Fisica Inventada" for m in todas)
    assert sorted(m["total"] for m in todas if m["nombre"] != "Álgebra inventada") == [
        77,
        85.0,
        95.0,
    ]
