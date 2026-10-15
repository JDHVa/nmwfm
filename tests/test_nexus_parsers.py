from backend.core import nexus
from backend.core.htmlq import css_to_xpath, html_to_markdown

from . import fixtures


def test_materias():
    materias = nexus.parse_materias(fixtures.cards_html())
    assert len(materias) == 10
    assert materias[0].nombre == "Algoritmos Bio Inspirados"
    assert materias[0].id == "746214"
    assert len({m.id for m in materias}) == len(materias)
    assert "Lógica" in [m.nombre for m in materias]


def test_portada():
    portada = nexus.parse_portada(fixtures.portada_html())
    assert portada.profesor == "CAVAZOS MARTÍNEZ RAFAEL ALFREDO"
    assert portada.periodo == "Del 03/AGOSTO/2026 al 18/DICIEMBRE/2026"


def test_estructura():
    etapas = nexus.parse_estructura(fixtures.estructura_html())
    assert [e.nombre for e in etapas[:2]] == [
        "Etapa 1: Algoritmos Evolutivos",
        "Etapa 2: Algoritmos Genéticos",
    ]
    assert etapas[0].descripcion.startswith("Identifica los algoritmos evolutivos")
    assert len(etapas) == 5
    assert etapas[4].tareas[0].numero == "PIA"
    primera = etapas[0].tareas
    assert [t.numero for t in primera] == ["1.1", "1.2", "1.3", "1.4"]
    assert primera[1].titulo == "Dimensión 2 - Comprensión - Ficha Técnica"
    assert primera[1].tipo == "dimension"
    assert primera[1].puntos == 2.5
    assert primera[3].tipo == "evidencia"
    assert primera[3].modalidad == "Individual"
    assert etapas[2].tareas[3].modalidad == "En Equipo"


def test_detalle_dimension():
    d = nexus.parse_detalle(fixtures.detalle_html())
    assert d.numero == "1.2"
    assert d.titulo == "Dimensión 2 - Comprensión - Ficha Técnica"
    assert d.desde == "2026-08-10T00:00"
    assert d.hasta == "2026-09-21T23:59"
    assert d.puntos == 2.5
    assert d.modalidad == "Individual"
    assert "**ficha técnica**" in d.actividades
    assert "**Contenido Conceptual:**" in d.contenido
    assert "- Introducción a Algoritmos Evolutivos\n  - Historia" in d.contenido
    assert d.criterios_desempeno.startswith("- Identifica los fundamentos evolutivos")
    assert d.rubrica is None


def test_rubrica():
    r = nexus.parse_rubrica(fixtures.rubrica_html())
    assert r is not None
    assert len(r.criterios) == 3
    assert r.niveles == [
        "Evidencia Completa",
        "Evidencia Suficiente",
        "Evidencia Débil",
        "Sin Evidencia",
    ]
    assert all(len(c.niveles) == 4 for c in r.criterios)
    assert [n.puntos for n in r.criterios[1].niveles] == [5, 4, 3, 0]
    assert "responsabilidad" in r.criterios[2].criterio
    assert nexus.Rubrica.from_dict(r.to_dict()) == r


def test_html_to_markdown_basico():
    md = html_to_markdown("<p>Hola <strong>mundo</strong></p><ol><li>uno</li><li>dos</li></ol>")
    assert md == "Hola **mundo**\n\n1. uno\n2. dos"


def test_css_to_xpath():
    xp = css_to_xpath("a.menu-option > div[id^='x'], #y")
    assert "menu-option" in xp and "starts-with" in xp and " | " in xp


def _tabs(*nombres, attr="routerlink"):
    links = "".join(f'<a class="mat-tab-link" {attr}="{n}" href="#/x/{n}">{n}</a>' for n in nombres)
    return f'<nav class="mat-tab-nav-bar"><div class="mat-tab-links">{links}</div></nav>'


TABS_EVIDENCIA = _tabs("Contenidos", "Recursos", "Rubrica", "Entregas")


def test_pestanas_evidencia_con_rubrica():
    assert nexus.parse_pestanas(TABS_EVIDENCIA) == ["contenidos", "recursos", "rubrica", "entregas"]
    assert nexus.tiene_pestana_rubrica(TABS_EVIDENCIA)


def test_pestanas_dimension_sin_rubrica():
    assert nexus.parse_pestanas(fixtures.detalle_html()) == ["contenidos", "recursos", "entregas"]
    assert not nexus.tiene_pestana_rubrica(fixtures.detalle_html())


def test_pestana_rubrica_por_ng_reflect_y_texto():
    reflect = _tabs("Contenidos", "Rubrica", attr="ng-reflect-router-link")
    assert nexus.tiene_pestana_rubrica(reflect)
    solo_texto = '<nav class="mat-tab-nav-bar"><div class="mat-tab-links">'
    solo_texto += '<a class="mat-tab-link">Rúbrica</a></div></nav>'
    assert nexus.tiene_pestana_rubrica(solo_texto)
