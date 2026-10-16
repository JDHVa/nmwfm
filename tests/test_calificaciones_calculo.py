from pathlib import Path

import pytest

from backend.core import calificaciones as c
from backend.core import nexus, siase

DATOS = Path(__file__).parent / "html_reales"
MATERIAS = {
    m["clave"]: m
    for m in siase.parse_evaluacion((DATOS / "siase_evaluacion.html").read_text(encoding="utf-8"))
}
NEXUS = nexus.parse_calificaciones((DATOS / "nexus_calificaciones.html").read_text("utf-8"))


def entrada(clave, portafolio=None):
    return {**MATERIAS[clave], "materia_id": None, "portafolio": portafolio}


def una(clave, portafolio=None, **kw):
    return c.calcular([entrada(clave, portafolio)], **kw)["materias"][0]


def elemento(titulo, valor, cal=None, perdida=False):
    puntos = None if cal is None else cal * valor / 100
    return {
        "titulo": titulo,
        "valor": valor,
        "calificacion": cal,
        "puntos": puntos,
        "perdida": perdida,
    }


def test_elementos_del_html_real_ignoran_diagnosticos_y_la_fila_de_totales():
    elementos = c.elementos_portafolio(NEXUS)
    assert [e["titulo"] for e in elementos] == [
        "Learning Evidence 1: Timeline",
        "Learning Evidence 2: Comic strip",
        "Learning Evidence 3: Electronic presentation",
        "Learning Evidence 4: Written report",
        "PIA - ILP: Video",
    ]
    assert [e["calificacion"] for e in elementos] == [100.0, 100.0, None, None, None]
    assert [e["puntos"] for e in elementos] == [8.0, 8.0, None, None, None]
    assert sum(e["valor"] for e in elementos) == 40


def test_guion_es_sin_calificar_no_cero_y_cero_real_cuenta():
    datos = {
        "columnas": ["Trabajo", "Elemento Evaluable", "", "Calificacion", "Valor", "Puntos"],
        "filas": [
            ["", "A", "", "-", "10", "0"],
            ["", "B", "", "0", "10", "0"],
            ["", "Diagnóstico inicial", "", "50", "0", "0"],
            ["", "", "", "", "20", "0"],
        ],
    }
    a, b = c.elementos_portafolio(datos)
    assert a["calificacion"] is None and a["puntos"] is None
    assert b["calificacion"] == 0.0 and b["puntos"] == 0.0


def test_elementos_sin_tabla_o_sin_encabezado():
    assert c.elementos_portafolio(None) == []
    sin_encabezado = {"columnas": [], "filas": [["", "T", "", "80", "10", "8"]]}
    assert c.elementos_portafolio(sin_encabezado)[0]["puntos"] == 8.0


def test_detectar_tipo_por_suma_y_por_razon():
    assert c.detectar_tipo(40, None, None) == "bachillerato"
    assert c.detectar_tipo(50, None, None) == "carrera"
    assert c.detectar_tipo(100, None, None) == "portafolio"
    assert c.detectar_tipo(None, 39, 19.5) == "carrera"
    assert c.detectar_tipo(None, 35, 14) == "bachillerato"
    assert c.detectar_tipo(None, 80, 80) == "portafolio"
    assert c.detectar_tipo(70, None, None) is None
    assert c.detectar_tipo(None, 5, 2) is None
    assert c.detectar_tipo(None, None, None) is None


def test_sistemas_de_calidad_es_carrera():
    m = una("095")
    assert m["tipo"] == "carrera" and not m["tipo_manual"]
    pesos = {x["clave"]: x["peso"] for x in m["componentes"]}
    assert pesos == {"par1": 10, "emt": 15, "par2": 10, "eg": 15, "portafolio": 50}
    port = next(x for x in m["componentes"] if x["clave"] == "portafolio")
    assert port["calificacion"] == 39 and port["puntos"] == 19.5
    assert m["asegurados"] == pytest.approx(42.8)
    assert {(p["clave"], p["peso"]) for p in m["pendientes"]} == {
        ("par2", 10),
        ("eg", 15),
        ("portafolio", 30.5),
    }
    assert m["maximo_posible"] == pytest.approx(98.3)


def test_ciencias_sociales_es_bachillerato():
    m = una("015")
    assert m["tipo"] == "bachillerato"
    pesos = {x["clave"]: x["peso"] for x in m["componentes"]}
    assert pesos == {"par1": 10, "emt": 15, "par2": 10, "eg": 25, "portafolio": 40}
    port = next(x for x in m["componentes"] if x["clave"] == "portafolio")
    assert port["puntos"] == 14
    assert m["asegurados"] == pytest.approx(37.8)
    assert m["maximo_posible"] == pytest.approx(37.8 + 10 + 25 + 26)


def test_eleccion_vocacional_con_portafolio_de_nexus_es_solo_portafolio():
    elementos = [elemento(f"Tarea {i}", 10) for i in range(10)]
    m = una("019", elementos)
    assert m["tipo"] == "portafolio"
    assert [x["clave"] for x in m["componentes"]] == ["portafolio"]
    assert m["componentes"][0]["peso"] == 100
    assert m["estado"] == "sin_datos"
    assert m["maximo_posible"] == 100 and m["asegurados"] == 0
    assert len(m["pendientes"]) == 10


def test_eleccion_vocacional_sin_nexus_no_tiene_tipo():
    m = una("019")
    assert m["tipo"] is None and not m["tipo_manual"]
    assert m["estado"] == "sin_datos" and m["pendientes"] == []


def test_portafolio_de_nexus_reemplaza_al_port_de_siase():
    elementos = c.elementos_portafolio(NEXUS)
    m = una("095", elementos)
    assert m["tipo"] == "bachillerato"
    port = next(x for x in m["componentes"] if x["clave"] == "portafolio")
    assert port["puntos"] == 16
    assert m["asegurados"] == pytest.approx(9.5 + 13.8 + 16)
    titulos = [p["titulo"] for p in m["pendientes"] if p["clave"] == "portafolio"]
    assert len(titulos) == 3 and "PIA - ILP: Video" in titulos
    assert m["portafolio"][0] == {
        "titulo": "Learning Evidence 1: Timeline",
        "valor": 8.0,
        "puntos": 8.0,
        "perdida": False,
    }


def test_tarea_perdida_cuenta_cero_pero_no_es_asegurada_ni_pendiente():
    base = c.elementos_portafolio(NEXUS)
    perdida = [dict(e, perdida=e["titulo"].endswith("report")) for e in base]
    sin = una("095", base)
    con = una("095", perdida)
    assert con["asegurados"] == sin["asegurados"]
    assert con["maximo_posible"] == sin["maximo_posible"] - 8
    assert len(con["pendientes"]) == len(sin["pendientes"]) - 1
    assert next(p for p in con["portafolio"] if p["perdida"])["titulo"].endswith("report")
    assert con["proyectada"] < sin["proyectada"]


def test_necesario_y_alcanzable():
    m = una("095", objetivos={"095": 90})
    assert m["objetivo"] == 90
    assert m["necesario"] == pytest.approx(85.0)
    assert m["alcanzable"] is True
    imposible = una("095", objetivos={"095": 100})
    assert imposible["necesario"] == pytest.approx(103.1, abs=0.05)
    assert imposible["alcanzable"] is False
    ya = una("095", objetivos={"095": 40})
    assert ya["necesario"] == 0 and ya["alcanzable"] is True


def test_sin_objetivo_o_sin_pendientes_no_hay_necesario():
    assert una("095")["necesario"] is None and una("095")["prob_objetivo"] is None
    cerrada = [elemento("T", 40, 90)]
    notas = {
        k: {"cal": 100.0, "pts": float(p)}
        for k, p in (("par1", 10), ("emt", 15), ("par2", 10), ("eg", 25), ("portafolio", 36))
    }
    entrada_cerrada = {
        "clave": "X",
        "nombre": "Cerrada",
        "notas": notas,
        "portafolio": cerrada,
        "materia_id": None,
    }
    m = c.calcular([entrada_cerrada], objetivos={"X": 95})["materias"][0]
    assert m["pendientes"] == [] and m["necesario"] is None
    assert m["asegurados"] == 96 and m["proyectada"] == 96
    assert m["rango"] == [96, 96] and m["prob_objetivo"] == 1 and m["prob_aprobar"] == 1
    assert m["estado"] == "bien"


def test_simulacion_es_reproducible_y_acotada():
    a = c.calcular([entrada(k) for k in MATERIAS], objetivo_semestre=85)
    b = c.calcular([entrada(k) for k in MATERIAS], objetivo_semestre=85)
    assert a == b
    for m in a["materias"]:
        assert 0 <= m["rango"][0] <= m["proyectada"] <= m["rango"][1] <= 100
        assert m["asegurados"] <= m["proyectada"] + 1e-9 or m["estado"] == "sin_datos"
        assert 0 <= m["prob_aprobar"] <= 1


def test_mas_datos_buenos_suben_la_proyeccion():
    malo = {
        "clave": "M",
        "nombre": "Mala",
        "materia_id": None,
        "portafolio": None,
        "notas": {"par1": {"cal": 60.0, "pts": 6.0}, "emt": {"cal": 60.0, "pts": 9.0}},
    }
    bueno = {
        **malo,
        "clave": "B",
        "notas": {"par1": {"cal": 100.0, "pts": 10.0}, "emt": {"cal": 100.0, "pts": 15.0}},
    }
    r = c.calcular([malo, bueno], tipos_manuales={"M": "bachillerato", "B": "bachillerato"})
    mala, buena = r["materias"]
    assert mala["tipo_manual"] and buena["tipo_manual"]
    assert buena["proyectada"] > mala["proyectada"] + 10
    assert buena["prob_aprobar"] > mala["prob_aprobar"]


def test_estados():
    riesgo = {
        "clave": "R",
        "nombre": "Riesgo",
        "materia_id": None,
        "portafolio": None,
        "notas": {"par1": {"cal": 30.0, "pts": 3.0}, "emt": {"cal": 30.0, "pts": 4.5}},
    }
    r = c.calcular([riesgo], tipos_manuales={"R": "bachillerato"})["materias"][0]
    assert r["estado"] == "riesgo" and r["prob_aprobar"] < 0.6

    atento = c.calcular([entrada("015")], objetivos={"015": 100})["materias"][0]
    assert atento["estado"] == "atento" and atento["prob_objetivo"] < 0.5

    bien = c.calcular([entrada("015")], objetivos={"015": 70})["materias"][0]
    assert bien["estado"] == "bien" and bien["prob_objetivo"] >= 0.5

    sin = c.calcular([entrada("019")])["materias"][0]
    assert sin["estado"] == "sin_datos"


def test_riesgo_cuando_aprobar_exige_mas_de_90_en_lo_pendiente():
    notas = {
        "par1": {"cal": 30.0, "pts": 3.0},
        "emt": {"cal": 27.0, "pts": 4.0},
        "par2": {"cal": 30.0, "pts": 3.0},
        "eg": {"cal": 27.0, "pts": 4.0},
    }
    m = {"clave": "N", "nombre": "Necesita", "materia_id": None, "portafolio": None, "notas": notas}
    r = c.calcular([m], tipos_manuales={"N": "carrera"})["materias"][0]
    assert r["asegurados"] == 14
    assert [p["peso"] for p in r["pendientes"]] == [50]
    assert r["estado"] == "riesgo"


def test_tipo_manual_gana_sobre_la_deteccion():
    m = una("095", tipos_manuales={"095": "bachillerato"})
    assert m["tipo"] == "bachillerato" and m["tipo_manual"] is True
    assert next(x for x in m["componentes"] if x["clave"] == "eg")["peso"] == 25
    invalido = una("095", tipos_manuales={"095": "otro"})
    assert invalido["tipo"] == "carrera" and not invalido["tipo_manual"]


def test_semestre():
    r = c.calcular(
        [entrada(k) for k in MATERIAS], objetivo_semestre=85, siase_leida_en="2026-10-16T10:00:00"
    )
    s = r["semestre"]
    esperado = sum(m["asegurados"] for m in r["materias"]) / len(r["materias"])
    assert s["actual"] == pytest.approx(esperado, abs=0.01)
    assert s["objetivo"] == 85
    assert s["proyectada"] >= s["actual"]
    assert s["rango"][0] <= s["proyectada"] <= s["rango"][1]
    assert 0 <= s["prob_objetivo"] <= 1
    pendiente = sum(p["peso"] for m in r["materias"] for p in m["pendientes"])
    n = len(r["materias"])
    assert s["necesario_promedio"] == pytest.approx(
        100 * (85 - s["actual"]) * n / pendiente, abs=0.2
    )
    assert r["siase_leida_en"] == "2026-10-16T10:00:00"


def test_semestre_sin_objetivo_y_sin_materias():
    s = c.calcular([entrada("015")])["semestre"]
    assert s["objetivo"] is None and s["prob_objetivo"] is None
    assert s["necesario_promedio"] is None
    vacio = c.calcular([])
    assert vacio["materias"] == [] and vacio["semestre"]["actual"] == 0
    assert vacio["siase_leida_en"] is None


def test_nombres_y_coincidencias():
    assert c.nombre_materia("015 Introducción a las Ciencias Sociales") == (
        "introduccion a las ciencias sociales"
    )
    assert c.mismo_nombre("logica", "logica")
    assert c.mismo_nombre("introduccion a las ciencias sociales", "ciencias sociales")
    assert not c.mismo_nombre("logica", "redes neuronales")
    assert not c.mismo_nombre("", "x")
    assert c.numero("-") is None and c.numero("") is None and c.numero("92,5") == 92.5
