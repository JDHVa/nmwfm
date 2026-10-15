import asyncio
import contextlib
import json
import sys
import time
from collections.abc import Awaitable, Callable

from . import config, services
from .core import nexus
from .core import selectors as S

SELECTORES = {
    "lista": [S.NX_CARDS_ROOT, S.NX_CARD, S.NX_CARD_NOMBRES],
    "portada": [S.NX_PORTADA, S.NX_MENU_OPTION],
    "estructura": [S.NX_ESTRUCTURA, S.NX_PANEL, S.NX_PANEL_TITLE, S.NX_PANEL_ITEM_LINK],
    "tarea": [S.NX_CONTENIDO_MATERIA, S.NX_DETALLE_ENCABEZADO, S.NX_DETALLE_CARDS, S.NX_TABS],
}


async def _faltantes(page, selectores: list[str]) -> list[str]:
    faltan = []
    for selector in selectores:
        try:
            if await page.locator(selector).count() == 0:
                faltan.append(selector)
        except Exception:
            faltan.append(selector)
    return faltan


async def _paso(pasos: list[dict], nombre: str, accion: Callable[[], Awaitable[str]]) -> bool:
    inicio = time.perf_counter()
    paso = {"nombre": nombre, "ok": True, "ms": 0, "detalle": "", "selectores_faltantes": []}
    try:
        paso["detalle"] = await accion() or ""
    except Exception as exc:
        paso["ok"] = False
        texto = str(exc).strip()
        paso["detalle"] = texto.splitlines()[0] if texto else type(exc).__name__
    paso["ms"] = round((time.perf_counter() - inicio) * 1000)
    pasos.append(paso)
    return paso["ok"]


def _ultimo(pasos: list[dict]) -> dict:
    return pasos[-1]


async def _verificar(page, pasos: list[dict], clave: str) -> None:
    faltan = await _faltantes(page, SELECTORES[clave])
    if faltan:
        _ultimo(pasos)["selectores_faltantes"] = faltan
        _ultimo(pasos)["ok"] = False
        if not _ultimo(pasos)["detalle"]:
            _ultimo(pasos)["detalle"] = "Faltan selectores"


def _tarea_de_prueba(etapas) -> tuple[int, int, str] | None:
    for e_idx, etapa in enumerate(etapas):
        for tarea in etapa.tareas:
            if tarea.tipo in ("dimension", "evidencia"):
                return e_idx, tarea.orden, tarea.numero
    return None


async def ejecutar(state, headless: bool = True) -> dict:
    pasos: list[dict] = []
    estado: dict = {}

    async def login() -> str:
        estado["page"] = await services.ensure_nexus(state, services.Hooks(), headless=headless)
        return "Sesión de NEXUS abierta"

    if not await _paso(pasos, "login", login):
        return _reporte(pasos)
    page = estado["page"]

    async def lista() -> str:
        await services._en_lista(page)
        materias = await nexus.leer_materias(page)
        if not materias:
            raise RuntimeError("No se encontraron materias")
        estado["materias"] = materias
        return f"{len(materias)} materias"

    await _paso(pasos, "lista de materias", lista)
    await _verificar(page, pasos, "lista")
    if not pasos[-1]["ok"] or "materias" not in estado:
        return _reporte(pasos)

    async def portada() -> str:
        primera = estado["materias"][0]
        datos = await nexus.abrir_materia(page, primera.orden, primera.nombre)
        return f"{primera.nombre}: profesor {datos.profesor or 'sin dato'}"

    await _paso(pasos, "portada de la materia", portada)
    await _verificar(page, pasos, "portada")
    if not pasos[-1]["ok"]:
        return _reporte(pasos)

    async def estructura() -> str:
        etapas = await nexus.abrir_estructura(page)
        if not etapas:
            raise RuntimeError("La estructura no tiene etapas")
        estado["etapas"] = etapas
        return f"{len(etapas)} etapas, {sum(len(e.tareas) for e in etapas)} tareas"

    await _paso(pasos, "estructura", estructura)
    await _verificar(page, pasos, "estructura")
    prueba = _tarea_de_prueba(estado.get("etapas", []))
    if not pasos[-1]["ok"] or prueba is None:
        if prueba is None and pasos[-1]["ok"]:
            await _paso(pasos, "tarea de prueba", _sin_tarea)
        return _reporte(pasos)

    async def tarea() -> str:
        e_idx, t_idx, numero = prueba
        detalle = await nexus.abrir_tarea(page, e_idx, t_idx, numero, entregas=True)
        estado["detalle"] = detalle
        if not detalle.titulo:
            raise RuntimeError("El detalle no trae título")
        return f"{numero} · {detalle.titulo}"

    await _paso(pasos, "detalle de la tarea", tarea)
    await _verificar(page, pasos, "tarea")

    detalle = estado.get("detalle")
    if detalle is not None:
        await _paso(pasos, "rúbrica", _informativo(detalle.rubrica is not None, "rúbrica leída"))
        await _paso(
            pasos, "entregas", _informativo(detalle.entregas is not None, "pestaña Entregas leída")
        )

    async def calificaciones() -> str:
        html = await nexus.abrir_calificaciones(page)
        if nexus.parse_calificaciones(html) is None:
            raise RuntimeError("Formato de calificaciones no reconocido")
        return "Tabla de calificaciones leída"

    await _paso(pasos, "calificaciones", calificaciones)
    with contextlib.suppress(Exception):
        await nexus.volver_a_lista(page)
    return _reporte(pasos)


async def _sin_tarea() -> str:
    raise RuntimeError("No hay una dimensión o evidencia para probar")


def _informativo(valor: bool, texto: str) -> Callable[[], Awaitable[str]]:
    async def accion() -> str:
        if not valor:
            raise RuntimeError("No disponible en esta tarea (puede no aplicar)")
        return texto

    return accion


def _reporte(pasos: list[dict]) -> dict:
    return {"ok": all(p["ok"] for p in pasos), "pasos": pasos}


def formatear(reporte: dict) -> str:
    lineas = []
    for paso in reporte["pasos"]:
        marca = "OK " if paso["ok"] else "FALLA"
        lineas.append(f"[{marca}] {paso['nombre']} ({paso['ms']} ms) {paso['detalle']}")
        lineas.extend(f"        selector sin resultados: {s}" for s in paso["selectores_faltantes"])
    lineas.append("RESULTADO: " + ("todo bien" if reporte["ok"] else "hay pasos con falla"))
    return "\n".join(lineas)


async def run_diagnostico(state, ctx) -> dict:
    async with state.browser.lock:
        return await ejecutar(state)


async def _principal(como_json: bool) -> int:
    state = services.AppState(config.DATA_DIR, "check", dev=config.DEV)
    try:
        async with state.browser.lock:
            reporte = await ejecutar(state)
    finally:
        await state.close()
    print(json.dumps(reporte, ensure_ascii=False, indent=2) if como_json else formatear(reporte))
    return 0 if reporte["ok"] else 1


def main() -> None:
    sys.exit(asyncio.run(_principal("--json" in sys.argv)))


if __name__ == "__main__":
    main()
