import asyncio
import json

import numpy as np

from backend import services
from backend.core import calificaciones as c
from backend.core import nexus
from backend.core.types import MateriaCard, Portada
from backend.services import AppState

from .conftest import MemoryCredentials


def historial_alto():
    materias = []
    for i in range(40):
        eg = 100 if i % 20 < 13 else 92
        materias.append(
            {
                "tipo": "carrera",
                "par1": 100,
                "par2": 98,
                "emt": 97,
                "eg": eg,
                "port": 100,
                "total": 98,
            }
        )
    materias.append({"tipo": "carrera", "par1": 90, "port": 95, "total": 90})
    return materias


def nota(cal, peso):
    return {"cal": cal, "pts": cal * peso / 100}


def materia(clave, notas, nombre=None):
    return {
        "clave": clave,
        "nombre": nombre or f"Materia {clave}",
        "materia_id": None,
        "portafolio": None,
        "notas": notas,
    }


def carrera(clave, **cals):
    pesos = {"par1": 10, "emt": 15, "par2": 10, "eg": 15}
    return materia(clave, {k: nota(v, pesos[k]) for k, v in cals.items()})


def calcular(entradas, **kw):
    return c.calcular(entradas, {e["clave"]: "carrera" for e in entradas}, **kw)


def test_importa_el_historial_una_sola_vez(tmp_path):
    datos = tmp_path / "data"
    datos.mkdir()
    (datos / "historial_semestres.json").write_text(
        json.dumps(
            {
                "fuente": "inventado",
                "semestres": [
                    {
                        "periodo": "Periodo X",
                        "materias": [
                            {
                                "nombre": "Una",
                                "tipo": "carrera",
                                "par1": 90,
                                "port": 100,
                                "total": 95,
                            },
                            {"nombre": None, "tipo": "portafolio", "port": 100, "total": 100},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    st = AppState(datos, "dev", dev=True, credentials=MemoryCredentials())
    try:
        semestres = st.storage.get_historial_calificaciones()
        assert len(semestres) == 1 and len(semestres[0]["materias"]) == 2
        assert semestres[0]["materias"][0]["par1"] == 90
        st.storage.set_historial_calificaciones([])
        services.importar_historial(st)
        assert st.storage.get_historial_calificaciones() == []
    finally:
        st.storage.close()


def test_sin_archivo_no_hay_historial(state):
    assert state.storage.get_historial_calificaciones() == []


def test_historial_get_put_y_resumen(client):
    cuerpo = {
        "semestres": [
            {
                "periodo": "S1",
                "materias": [
                    {"nombre": "A", "tipo": "carrera", "eg": 100, "total": 100},
                    {"nombre": None, "tipo": "bachillerato", "eg": 90, "total": 94},
                ],
            }
        ]
    }
    r = client.put("/calificaciones/historial", json=cuerpo).json()
    assert r["resumen"]["eg"] == {"media": 95.0, "desv": 5.0, "n": 2, "prob_100": 0.5}
    assert r["resumen"]["par1"]["n"] == 0
    assert client.get("/calificaciones/historial").json() == r
    malo = client.put(
        "/calificaciones/historial",
        json={"semestres": [{"periodo": "S", "materias": [{"tipo": "carrera", "total": 120}]}]},
    )
    assert malo.status_code == 422


def test_distribucion_respeta_prob_100_y_no_da_100_siempre():
    p = c._preparar(carrera("X", par1=95), "carrera")
    hist = c._contexto_historial(historial_alto())
    notas = c._notas(p, 80.0, 15.0, hist)
    j = [x["clave"] for x in p["pendientes"]].index("eg")
    eg = notas[:, j]
    esperada = hist["stats"]["eg"]["prob_100"]
    frecuencia = float(np.mean(eg >= 100 - 1e-9))
    assert 0.5 < esperada < 0.8
    assert abs(frecuencia - esperada) < 0.12
    assert eg.min() < 100 and eg.min() >= 0


def test_objetivo_alcanzable_con_historial_alto_no_tiene_probabilidad_cero():
    m = calcular([carrera("X", par1=100)], historial=historial_alto(), objetivo_semestre=None)
    r = c.calcular(
        [carrera("X", par1=100)],
        {"X": "carrera"},
        {"X": 98},
        historial=historial_alto(),
    )["materias"][0]
    assert r["alcanzable"] and r["prob_objetivo"] > 0
    assert r["proyectada"] > 90
    assert m["materias"][0]["prob_aprobar"] > 0.99


def test_objetivo_inalcanzable_es_cero():
    r = c.calcular(
        [carrera("X", par1=60, emt=60, par2=60)],
        {"X": "carrera"},
        {"X": 99},
        historial=historial_alto(),
    )["materias"][0]
    assert not r["alcanzable"] and r["prob_objetivo"] == 0


def test_probabilidad_pequena_se_reporta_tal_cual():
    assert c._redondear_prob(0.0004) == 0.0004
    assert c._redondear_prob(0.01234) == 0.012
    assert c._redondear_prob(None) is None


def test_el_desplazamiento_sigue_como_vas_este_semestre():
    hist = historial_alto()
    bien = c.calcular([carrera("B", par1=100, emt=100)], {"B": "carrera"}, historial=hist)
    mal = c.calcular([carrera("M", par1=82, emt=82)], {"M": "carrera"}, historial=hist)
    assert bien["materias"][0]["proyectada"] > mal["materias"][0]["proyectada"] + 3


def test_sin_historial_usa_el_modelo_anterior():
    r = c.calcular([carrera("X", par1=90)], {"X": "carrera"})["materias"][0]
    assert r["alertas"] == [] or all(a["tipo"] != "bajo_historico" for a in r["alertas"])
    assert 0 < r["proyectada"] <= 100


def test_alerta_bajo_historico():
    r = calcular([carrera("X", par1=100, emt=88)], historial=historial_alto())["materias"][0]
    tipos = [a["tipo"] for a in r["alertas"]]
    assert "bajo_historico" in tipos and "examen_bajo" not in tipos
    assert r["en_cuidado"] and r["estado"] == "atento"
    sin = calcular([carrera("X", par1=100, emt=96)], historial=historial_alto())["materias"][0]
    assert not any(a["tipo"] == "bajo_historico" for a in sin["alertas"])


def test_alerta_examen_bajo_incluye_par1():
    r = calcular([carrera("X", par1=80)], historial=historial_alto())["materias"][0]
    assert [a["tipo"] for a in r["alertas"] if a["tipo"] == "examen_bajo"] == ["examen_bajo"]
    ok = calcular([carrera("X", par1=81)], historial=historial_alto())["materias"][0]
    assert not any(a["tipo"] == "examen_bajo" for a in ok["alertas"])


def test_alerta_puntos_perdidos_con_y_sin_historial():
    entrada = carrera("X", par1=94, emt=94)
    perdidos = 10 * 0.06 + 15 * 0.06
    assert perdidos < 6
    sin = calcular([entrada])["materias"][0]
    assert not any(a["tipo"] == "puntos_perdidos" for a in sin["alertas"])
    fuerte = carrera("Y", par1=94, emt=94, par2=94, eg=94)
    r = calcular([fuerte])["materias"][0]
    assert r["evaluado_pts"] == 50 and r["total_pts"] == 47
    assert not any(a["tipo"] == "puntos_perdidos" for a in r["alertas"])
    peor = carrera("Z", par1=85, emt=85, par2=85, eg=85)
    r = calcular([peor])["materias"][0]
    assert any(a["tipo"] == "puntos_perdidos" for a in r["alertas"])
    con_hist = calcular([carrera("W", par1=75, emt=75, par2=75, eg=75)], historial=historial_alto())
    assert any(a["tipo"] == "puntos_perdidos" for a in con_hist["materias"][0]["alertas"])
    tolerante = historial_alto() + [{"tipo": "carrera", "total": 60}]
    r = calcular([carrera("V", par1=75, emt=75, par2=75, eg=75)], historial=tolerante)
    assert not any(a["tipo"] == "puntos_perdidos" for a in r["materias"][0]["alertas"])


def test_tareas_perdidas_cuentan_como_puntos_perdidos():
    elementos = [
        {"titulo": "Hecha", "valor": 20, "calificacion": 100, "puntos": 20, "perdida": False},
        {"titulo": "Vencida", "valor": 20, "calificacion": None, "puntos": None, "perdida": True},
    ]
    entrada = {**materia("P", {}), "portafolio": elementos}
    r = c.calcular([entrada], {"P": "carrera"})["materias"][0]
    assert r["evaluado_pts"] == 40 and r["total_pts"] == 20
    assert any(a["tipo"] == "puntos_perdidos" for a in r["alertas"])


def test_campos_de_la_tabla():
    elementos = [
        {"titulo": "Hecha", "valor": 20, "calificacion": 90, "puntos": 18, "perdida": False},
        {"titulo": "Futura", "valor": 30, "calificacion": None, "puntos": None, "perdida": False},
    ]
    entrada = {**carrera("T", par1=90), "portafolio": elementos}
    r = c.calcular([entrada], {"T": "carrera"})["materias"][0]
    assert r["portafolio_pts"] == 18 and r["portafolio_max"] == 50
    assert r["examenes_pts"] == 9 and r["examenes_max"] == 50
    assert r["total_pts"] == 27 and r["evaluado_pts"] == 30
    assert r["pct_evaluado"] == 90
    vacia = c.calcular([materia("N", {})], {"N": "carrera"})["materias"][0]
    assert vacia["pct_evaluado"] is None


def escenario(preset, entradas, historial=None, **kw):
    return c.calcular_escenario(
        entradas,
        {"preset": preset, **kw},
        {e["clave"]: "carrera" for e in entradas},
        historial,
    )


def test_preset_optimista_es_100_salvo_materias_con_alerta():
    sana = carrera("S", par1=96, emt=96)
    alerta = carrera("A", par1=78)
    r = escenario("optimista", [sana, alerta], historial_alto())
    por = {m["clave"]: m for m in r["materias"]}
    assert all(p["nota"] == 100 for p in por["S"]["pendientes"])
    assert por["S"]["final"] == 100 - (4 * 10 + 4 * 15) / 100 - 0 or por["S"]["final"] > 96
    exam_a = [p for p in por["A"]["pendientes"] if p["clave"] != "portafolio"]
    assert exam_a and all(p["nota"] == 78 for p in exam_a)
    esfuerzo = escenario(
        "optimista", [sana, alerta], historial_alto(), materias={"A": {"esfuerzo": True}}
    )
    assert all(p["nota"] == 100 for p in esfuerzo["materias"][1]["pendientes"])
    assert esfuerzo["materias"][1]["final"] > por["A"]["final"]


def test_preset_pesimista_resta_una_desviacion():
    entrada = carrera("X", par1=100, emt=100)
    hist = c._contexto_historial(historial_alto())
    r = escenario("pesimista", [entrada], historial_alto())
    nota_esperada = min(100, hist["examenes"]["media"]) - hist["examenes"]["desv"]
    examenes = [p for p in r["materias"][0]["pendientes"] if p["clave"] != "portafolio"]
    assert all(abs(p["nota"] - nota_esperada) < 0.01 for p in examenes)
    peor = escenario("pesimista", [carrera("Y", par1=70)], historial_alto())
    assert all(p["nota"] < 70 for p in peor["materias"][0]["pendientes"][:3])


def test_preset_realista_y_mio_comparten_modelo_y_mio_iguala_a_proyectada():
    entrada = carrera("X", par1=95, emt=92)
    hist = historial_alto()
    resumen = c.calcular([entrada], {"X": "carrera"}, historial=hist)["materias"][0]
    realista = escenario("realista", [entrada], hist)["materias"][0]
    mio = escenario("mio", [entrada], hist)["materias"][0]
    assert mio["final"] == resumen["proyectada"]
    assert abs(realista["final"] - mio["final"]) < 0.5
    assert all(0 <= p["nota"] <= 100 for p in realista["pendientes"])


def test_overrides_globales_por_materia_y_por_pendiente():
    a, b = carrera("A", par1=90), carrera("B", par1=90)
    r = escenario(
        "personalizado",
        [a, b],
        historial_alto(),
        examenes=70,
        tareas=70,
        materias={"B": {"examenes": 100, "pendientes": {0: 50}}},
    )
    notas_a = [p["nota"] for p in r["materias"][0]["pendientes"]]
    notas_b = [p["nota"] for p in r["materias"][1]["pendientes"]]
    assert notas_a == [70, 70, 70, 70]
    assert notas_b == [50, 100, 100, 70]
    final_a = 9 + (15 + 10 + 15 + 50) * 0.7
    assert r["materias"][0]["final"] == round(final_a, 2)
    assert r["semestre"] == round((r["materias"][0]["final"] + r["materias"][1]["final"]) / 2, 2)


def test_personalizado_sin_valores_usa_realista():
    entrada = carrera("X", par1=95)
    p = escenario("personalizado", [entrada], historial_alto())
    r = escenario("realista", [entrada], historial_alto())
    assert p == r


def test_override_en_mio_recalcula_lineal():
    entrada = carrera("X", par1=100)
    r = escenario("mio", [entrada], historial_alto(), examenes=100, tareas=100)["materias"][0]
    assert r["final"] == 100


def test_endpoint_escenario(client, state):
    from .test_calificaciones_resumen import SIASE

    state.storage.set_siase_calificaciones(SIASE)
    r = client.post("/calificaciones/escenario", json={"preset": "optimista"})
    assert r.status_code == 200 and len(r.json()["materias"]) == 10
    assert client.post("/calificaciones/escenario", json={"preset": "x"}).status_code == 422
    assert (
        client.post(
            "/calificaciones/escenario", json={"preset": "mio", "examenes": 120}
        ).status_code
        == 422
    )
    desconocida = client.post(
        "/calificaciones/escenario", json={"preset": "mio", "materias": {"999": {"examenes": 90}}}
    )
    assert desconocida.status_code == 404
    ok = client.post(
        "/calificaciones/escenario",
        json={"preset": "personalizado", "materias": {"095": {"pendientes": {"0": 80}}}},
    )
    assert ok.status_code == 200


def test_resumen_incluye_alertas_tabla_e_historial(client, state):
    from .test_calificaciones_resumen import NEXUS, SIASE

    state.storage.set_siase_calificaciones(SIASE)
    state.storage.upsert_materia("100", "Lógica", 0)
    state.storage.set_calificaciones("100", NEXUS)
    client.put(
        "/calificaciones/historial",
        json={"semestres": [{"periodo": "S", "materias": [{"tipo": "carrera", "total": 99}]}]},
    )
    r = client.get("/calificaciones").json()
    assert r["nexus_leido_en"]
    m = next(x for x in r["materias"] if x["clave"] == "033")
    assert {"alertas", "en_cuidado", "total_pts", "pct_evaluado"} <= set(m)


class FakeNexus:
    def __init__(self, monkeypatch, state, falla=False):
        self.eventos = []
        self.materias = [MateriaCard("100", "Lógica", 0), MateriaCard("200", "Física", 1)]
        self.falla = falla
        self.sesiones_simultaneas = 0
        self.bloqueada_durante = []

        class Pagina:
            url = "https://plataformanexus.uanl.mx/#/App"

            def is_closed(self):
                return False

            def locator(self, sel):
                class L:
                    async def count(self_inner):
                        return 0 if "cerrada" in sel else 1

                return L()

            async def content(self):
                return ""

            async def screenshot(self, **kw):
                return None

        pagina = Pagina()

        async def ensure(st, hooks, **kw):
            return pagina

        async def leer(page):
            return self.materias

        async def abrir_materia(page, i, nombre=None):
            self.eventos.append(("materia", nombre))
            self.bloqueada_durante.append(state.browser.lock.locked())
            await asyncio.sleep(0.02)
            return Portada("PROFE", "periodo", None)

        async def abrir_calificaciones(page):
            self.eventos.append(("calificaciones",))
            return "<html/>"

        def parse(html):
            if self.falla and self.eventos[-2][1] == "Física":
                return None
            return {"columnas": ["Elemento", "Calificacion", "Valor", "Puntos"], "filas": []}

        async def nada(page):
            self.eventos.append(("lista",))

        async def sin_tareas(*a, **k):
            raise AssertionError("no debe abrir tareas ni la estructura")

        monkeypatch.setattr(services, "ensure_nexus", ensure)
        monkeypatch.setattr(nexus, "leer_materias", leer)
        monkeypatch.setattr(nexus, "abrir_materia", abrir_materia)
        monkeypatch.setattr(nexus, "abrir_calificaciones", abrir_calificaciones)
        monkeypatch.setattr(nexus, "parse_calificaciones", parse)
        monkeypatch.setattr(nexus, "volver_a_lista", nada)
        monkeypatch.setattr(nexus, "abrir_estructura", sin_tareas)
        monkeypatch.setattr(nexus, "abrir_tarea", sin_tareas)


def correr_portafolio(state):
    async def escenario():
        job = state.jobs.start(
            "portafolio_nexus", lambda ctx: services.run_portafolio_nexus(state, ctx)
        )
        for _ in range(300):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    return asyncio.run(escenario())


def test_job_portafolio_nexus_guarda_solo_calificaciones(state, monkeypatch):
    fake = FakeNexus(monkeypatch, state)
    job = correr_portafolio(state)
    assert job.estado == "ok" and job.resultado == {"materias": 2, "errores": []}
    assert state.storage.get_calificaciones("100") and state.storage.get_calificaciones("200")
    assert [e[0] for e in fake.eventos if e[0] != "lista"] == [
        "materia",
        "calificaciones",
        "materia",
        "calificaciones",
    ]
    assert all(fake.bloqueada_durante)
    assert not state.browser.lock.locked()


def test_job_portafolio_nexus_reporta_errores_por_materia(state, monkeypatch):
    FakeNexus(monkeypatch, state, falla=True)
    job = correr_portafolio(state)
    assert job.estado == "ok" and job.resultado["materias"] == 2
    assert len(job.resultado["errores"]) == 1 and "Física" in job.resultado["errores"][0]
    assert state.storage.get_calificaciones("100") and not state.storage.get_calificaciones("200")


def test_job_portafolio_nexus_espera_el_lock(state, monkeypatch):
    FakeNexus(monkeypatch, state)

    async def escenario():
        async with state.browser.lock:
            job = state.jobs.start(
                "portafolio_nexus", lambda ctx: services.run_portafolio_nexus(state, ctx)
            )
            await asyncio.sleep(0.2)
            assert job.estado == "corriendo" and state.storage.get_calificaciones("100") is None
        for _ in range(300):
            if job.estado in ("ok", "error"):
                break
            await asyncio.sleep(0.02)
        return job

    assert asyncio.run(escenario()).estado == "ok"


def test_job_portafolio_nexus_cancelable_libera_el_lock(state, monkeypatch):
    FakeNexus(monkeypatch, state)

    async def lento(page, i, nombre=None):
        await asyncio.sleep(30)

    monkeypatch.setattr(nexus, "abrir_materia", lento)

    async def escenario():
        job = state.jobs.start(
            "portafolio_nexus", lambda ctx: services.run_portafolio_nexus(state, ctx)
        )
        for _ in range(100):
            if state.browser.lock.locked():
                break
            await asyncio.sleep(0.02)
        await state.jobs.cancelar(job.id)
        return job

    job = asyncio.run(escenario())
    assert job.estado == "error" and job.resultado == {"cancelado": True}
    assert not state.browser.lock.locked()


def test_endpoint_portafolio_nexus(client, state, monkeypatch):
    FakeNexus(monkeypatch, state)
    sin = client.post("/nexus/portafolio")
    assert sin.status_code == 400
    state.storage.set_settings({"cuenta": "123"})
    state.credentials.set("123", "pw")

    async def escenario():
        a = (await client.arequest("POST", "/nexus/portafolio")).json()
        b = (await client.arequest("POST", "/nexus/portafolio")).json()
        assert a["tipo"] == "portafolio_nexus" and a["id"] == b["id"]
        for _ in range(100):
            job = (await client.arequest("GET", f"/jobs/{a['id']}")).json()
            if job["estado"] in ("ok", "error"):
                return job
            await asyncio.sleep(0.05)

    job = asyncio.run(escenario())
    assert job["estado"] == "ok" and job["resultado"]["materias"] == 2
