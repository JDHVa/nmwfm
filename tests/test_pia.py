import asyncio

from backend import services
from backend.core import nexus
from backend.core import selectors as S
from backend.core.types import DetalleTarea, EtapaItem, MateriaCard, Portada, TareaItem

from . import fixtures


def test_pestanas_del_pia_incluyen_rubrica_y_entregas():
    claves = nexus.parse_pestanas(fixtures.pia_pestanas_html())
    assert claves == ["contenidos", "recursos", "rubrica", "equipo/documentos", "entregas"]
    assert nexus.tiene_pestana_rubrica(fixtures.pia_pestanas_html())


def test_datos_del_pia_se_leen_como_una_evidencia():
    detalle = nexus.parse_detalle(fixtures.pia_datos_html())
    assert "Informe de Programa con Algoritmos Bioinspirados" in detalle.actividades
    assert "- Introducción" in detalle.actividades and "- Marco Teórico" in detalle.actividades
    assert "Futuras Aplicaciones y Recomendaciones" in detalle.actividades


def test_rubrica_del_pia():
    rubrica = nexus.parse_rubrica(fixtures.pia_rubrica_html())
    assert rubrica is not None
    assert rubrica.niveles == [
        "Evidencia Completa",
        "Evidencia Suficiente",
        "Evidencia Débil",
        "Sin Evidencia",
    ]
    assert len(rubrica.criterios) == 3
    assert [n.puntos for n in rubrica.criterios[0].niveles] == [3, 2, 1, 0]
    assert [n.puntos for n in rubrica.criterios[1].niveles] == [5, 4, 3, 0]
    assert rubrica.criterios[0].criterio.startswith("Fundamenta la técnica")
    assert rubrica.criterios[0].niveles[0].descripcion.startswith("El informe integra")


def test_item_del_pia_en_la_estructura():
    item_html = f"<mat-list-item>{fixtures.pia_item_html()}</mat-list-item>"
    panel = (
        "<mat-expansion-panel><mat-expansion-panel-header>"
        '<span class="bold-500">Producto Integrador de Aprendizaje</span>'
        f"</mat-expansion-panel-header>{item_html}</mat-expansion-panel>"
    )
    etapas = nexus.parse_estructura(panel)
    tarea = etapas[0].tareas[0]
    assert (tarea.numero, tarea.titulo, tarea.tipo) == ("PIA", "PIA - Informe", "pia")


def test_pia_sin_prefijo_en_el_titulo_tambien_se_llama_pia():
    panel = (
        "<mat-expansion-panel><mat-expansion-panel-header>"
        '<span class="bold-500">Producto Integrador de Aprendizaje</span>'
        "</mat-expansion-panel-header><mat-list-item><a><div>"
        "<span>ILP: Video</span></div></a></mat-list-item></mat-expansion-panel>"
    )
    tarea = nexus.parse_estructura(panel)[0].tareas[0]
    assert (tarea.numero, tarea.titulo, tarea.tipo) == ("PIA", "ILP: Video", "pia")


class _Cuenta:
    def __init__(self, sel, textos):
        self.sel, self.textos = sel, textos

    async def all_inner_texts(self):
        return self.textos(self.sel)


class _Pagina:
    def __init__(self, url, tarjetas):
        self.url, self.tarjetas = url, tarjetas

    def locator(self, sel):
        return _Cuenta(sel, lambda s: self.tarjetas if s == S.NX_DETALLE_CARDS else [])


def test_espera_del_pia_usa_la_ruta_y_no_el_numero():
    lista = lambda url, tarjetas: nexus._detalle_lista(  # noqa: E731
        _Pagina(url, tarjetas), "PIA", pia=True
    )
    base = "https://plataformanexus.uanl.mx/#/App/UnidadesAprendizaje/UA/Estructura/"
    assert asyncio.run(lista(base + "ProductoIntegrador/Contenidos", ["Actividades"])())
    assert not asyncio.run(lista(base + "Evidencia/Contenidos", ["Actividades"])())
    assert not asyncio.run(lista(base + "ProductoIntegrador/Contenidos", ["  "])())


class _PaginaSync:
    url = "https://plataformanexus.uanl.mx/#/App"

    def is_closed(self):
        return False

    def locator(self, sel):
        class C:
            async def count(self_inner):
                return 0 if "sesi" in sel else 1

        return C()

    async def content(self):
        return "<html/>"

    async def screenshot(self, path, **kw):
        return None


def test_sync_lee_el_pia_sin_marcarlo_pendiente_de_soporte(state, monkeypatch):
    kwargs = []

    async def ensure(st, hooks, **kw):
        return _PaginaSync()

    async def leer(page):
        return [MateriaCard("100", "Lógica", 0)]

    async def abrir_materia(page, i, nombre=None):
        return Portada("PROFE", "p", None)

    async def abrir_estructura(page):
        return [
            EtapaItem(
                "Producto Integrador de Aprendizaje",
                "d",
                0,
                [TareaItem("PIA", "PIA - Informe", "pia", 10.0, None, 0)],
            )
        ]

    async def abrir_tarea(page, e, t, numero=None, **kw):
        kwargs.append((numero, kw))
        return DetalleTarea("PIA", "PIA", None, None, 10.0, None, "act", "c", "k", None, [])

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
    assert kwargs == [("PIA", {"entregas": True, "pia": True})]
    assert job.resultado["errores"] == [] and job.resultado["detalles_leidos"] == 1
    assert state.storage.get_detalle("100-PIA") is not None
    assert state.storage.get_tarea("100-PIA")["estado"] == "pendiente"
    mensajes = []
    while not cola.empty():
        mensajes.append(cola.get_nowait())
    assert not any("pendiente de soporte" in m.get("message", "") for m in mensajes)
