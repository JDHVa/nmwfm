import asyncio
import contextlib
import re
import unicodedata
from typing import TYPE_CHECKING

from . import selectors as S
from .browser import clic_robusto as _clic
from .htmlq import has_class, html_to_markdown, parse, select, select_one, text_of
from .types import (
    DetalleTarea,
    DialogoEntrega,
    EtapaItem,
    Hooks,
    MateriaCard,
    Portada,
    Rubrica,
    RubricaCriterio,
    RubricaNivel,
    Snackbar,
    TareaItem,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

_MESES = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}
_FECHA_RE = re.compile(
    r"(\d{4})/([A-Za-z]{3})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*([AaPp])\.?\s*[Mm]\.?"
)
_PUNTOS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*pts?", re.IGNORECASE)
_NUMERO_RE = re.compile(r"^(\d+(?:\.\d+)+)\s*[-.]?\s*(.*)$")


def _norm(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower().strip()


def _float(text: str) -> float | None:
    m = _PUNTOS_RE.search(text)
    if m:
        return float(m.group(1))
    try:
        return float(text.strip())
    except ValueError:
        return None


def parse_materias(markup: str) -> list[MateriaCard]:
    root = parse(markup)
    cards = []
    for i, card in enumerate(select(root, S.NX_CARD)):
        name_el = select_one(card, S.NX_CARD_NAME)
        nombre = text_of(name_el) or text_of(card)
        button = select_one(card.getparent(), S.NX_CARD_ID_BUTTON)
        digits = re.sub(r"\D", "", button.get("id", "")) if button is not None else ""
        cards.append(MateriaCard(id=digits or f"m{i + 1}", nombre=nombre, orden=i))
    return cards


def parse_portada(markup: str) -> Portada:
    root = parse(markup)
    profesor = periodo = modalidad = None
    for tr in select(root, "table tr"):
        tds = tr.xpath("./td")
        if len(tds) < 2:
            continue
        icons = [i for i in tr.iter("i")]
        classes = " ".join(i.get("class", "") for i in icons).split()
        value = text_of(tds[1])
        if S.NX_ICON_PROFESOR in classes:
            profesor = value or None
        elif S.NX_ICON_PERIODO in classes:
            periodo = value or None
        elif S.NX_ICON_MODALIDAD in classes:
            modalidad = value or None
    return Portada(profesor=profesor, periodo=periodo, modalidad=modalidad)


def parse_estructura(markup: str) -> list[EtapaItem]:
    root = parse(markup)
    panels = select(root, S.NX_PANEL) or select(root, "mat-expansion-panel")
    etapas = []
    for idx, panel in enumerate(panels):
        nombre = text_of(select_one(panel, S.NX_PANEL_TITLE))
        descripcion = text_of(select_one(panel, S.NX_PANEL_DESC))
        etapa = EtapaItem(nombre=nombre, descripcion=descripcion, orden=idx)
        for j, item in enumerate(select(panel, S.NX_PANEL_ITEM)):
            tarea = _parse_item(item, j)
            if tarea:
                etapa.tareas.append(tarea)
        etapas.append(etapa)
    return etapas


def _parse_item(item, orden: int) -> TareaItem | None:
    anchor = select_one(item, "a")
    if anchor is None:
        return None
    spans = [text_of(s) for s in anchor.iter("span") if text_of(s)]
    if not spans:
        return None
    if len(spans) >= 2 and re.fullmatch(r"\d+(?:\.\d+)*", spans[0]):
        numero, titulo = spans[0], " ".join(spans[1:])
    else:
        full = " ".join(spans)
        m = _NUMERO_RE.match(full)
        if m:
            numero, titulo = m.group(1), m.group(2).strip()
        else:
            numero, titulo = ("PIA" if full.upper().startswith("PIA") else str(orden + 1)), full
    tipo = "dimension" if _norm(titulo).startswith("dimension") else "evidencia"
    right = " ".join(text_of(e) for e in item.iter("span") if _PUNTOS_RE.fullmatch(text_of(e)))
    puntos = _float(right) if right else None
    icon = select_one(item, S.NX_ITEM_MODALITY_ICON)
    modalidad = icon.get("mattooltip") if icon is not None else None
    return TareaItem(
        numero=numero, titulo=titulo, tipo=tipo, puntos=puntos, modalidad=modalidad, orden=orden
    )


def _fecha_iso(m: re.Match) -> str:
    year, mes, dia, hora, minuto, ampm = m.groups()
    h = int(hora) % 12 + (12 if ampm.lower() == "p" else 0)
    return f"{int(year):04d}-{_MESES.get(mes.upper(), 1):02d}-{int(dia):02d}T{h:02d}:{minuto}"


def parse_detalle(markup: str) -> DetalleTarea:
    root = parse(markup)
    header = select_one(root, S.NX_DETALLE_HEADER)
    scope = header if header is not None else root

    numero = None
    titulo = ""
    title_el = select_one(scope, S.NX_DETALLE_TITLE)
    if title_el is not None:
        spans = [text_of(s) for s in title_el.iter("span") if text_of(s)]
        if len(spans) >= 2:
            numero = spans[0].strip(" -") or None
            titulo = spans[-1]
        elif spans:
            titulo = spans[0]

    desde = hasta = puntos = modalidad = None
    for icon in scope.iter("i"):
        classes = icon.get("class", "").split()
        parent_text = text_of(icon.getparent())
        if S.NX_DETALLE_ICON_FECHA in classes:
            fechas = [_fecha_iso(m) for m in _FECHA_RE.finditer(parent_text)]
            if fechas:
                desde = fechas[0]
                hasta = fechas[1] if len(fechas) > 1 else None
        elif S.NX_DETALLE_ICON_PUNTOS in classes:
            puntos = _float(parent_text)
        elif any(c in classes for c in S.NX_DETALLE_ICON_MODALIDAD) and modalidad is None:
            modalidad = parent_text or None

    secciones = {"actividades": "", "contenido": "", "criterios": ""}
    for card in select(root, S.NX_DETALLE_CARD):
        title = _norm(text_of(select_one(card, S.NX_DETALLE_CARD_TITLE)))
        body = select_one(card, ".fr-view")
        if body is None:
            continue
        if title == S.NX_SECCION_ACTIVIDADES:
            secciones["actividades"] = html_to_markdown(body)
        elif title == S.NX_SECCION_CONTENIDO:
            secciones["contenido"] = html_to_markdown(body)
        elif title == S.NX_SECCION_CRITERIOS:
            secciones["criterios"] = html_to_markdown(body)

    return DetalleTarea(
        titulo=titulo,
        numero=numero,
        desde=desde,
        hasta=hasta,
        puntos=puntos,
        modalidad=modalidad,
        actividades=secciones["actividades"],
        contenido=secciones["contenido"],
        criterios_desempeno=secciones["criterios"],
        rubrica=parse_rubrica(root),
    )


def _tab_key(a) -> str:
    raw = (
        a.get("routerlink")
        or a.get("ng-reflect-router-link")
        or a.get("href", "").rsplit("/", 1)[-1]
    )
    return _norm(raw or text_of(a))


def parse_pestanas(markup: str) -> list[str]:
    root = parse(markup)
    return [_tab_key(a) for a in select(root, S.NX_TABS)]


def tiene_pestana_rubrica(markup: str) -> bool:
    return "rubrica" in parse_pestanas(markup)


def parse_rubrica(markup_or_el) -> Rubrica | None:
    root = parse(markup_or_el) if isinstance(markup_or_el, str) else markup_or_el
    table = select_one(root, S.NX_RUBRICA)
    if table is None:
        return None
    niveles: list[str] = []
    criterios: list[RubricaCriterio] = []
    for tr in table.xpath(".//tr"):
        tds = tr.xpath("./td")
        if not tds:
            continue
        if any(select_one(td, S.NX_RUBRICA_PUNTOS) is not None for td in tds):
            celdas = []
            for td in tds[1:]:
                p = select_one(td, S.NX_RUBRICA_PUNTOS)
                d = select_one(td, S.NX_RUBRICA_DESC)
                puntos = _float(text_of(p)) if p is not None else None
                celdas.append(RubricaNivel(puntos=puntos or 0.0, descripcion=text_of(d)))
            criterios.append(RubricaCriterio(criterio=text_of(tds[0]), niveles=celdas))
        elif len(tds) > 1 and not text_of(tds[0]):
            niveles = [text_of(td) for td in tds[1:]]
    if not criterios:
        return None
    return Rubrica(niveles=niveles, criterios=criterios)


async def _pausa(minimo: float = 0.3, maximo: float = 0.9) -> None:
    from .browser import pausa

    await pausa(minimo, maximo)


async def _html(locator) -> str:
    return await locator.evaluate("e => e.outerHTML")


async def esperar_lista(page: "Page", timeout: float = 30000) -> None:
    await page.wait_for_selector(S.NX_CARD, timeout=timeout)


async def leer_materias(page: "Page") -> list[MateriaCard]:
    await esperar_lista(page)
    return parse_materias(await _html(page.locator(S.NX_CARDS_ROOT)))


async def abrir_materia(page: "Page", indice: int) -> Portada:
    await esperar_lista(page)
    card = page.locator(S.NX_CARD).nth(indice)
    await _pausa()
    enlace = card.locator(S.NX_CARD_CLICK).first
    await _clic(card.locator(S.NX_CARD_NAME), enlace)
    try:
        await page.wait_for_selector(S.NX_PORTADA, timeout=5000)
    except Exception:
        await enlace.dispatch_event("click")
        await page.wait_for_selector(S.NX_PORTADA, timeout=30000)
    await _pausa()
    return parse_portada(await _html(page.locator(S.NX_PORTADA)))


async def volver_a_estructura(page: "Page") -> None:
    await _pausa()
    await _clic(page.locator(S.NX_MENU_OPTION).filter(has_text=S.NX_MENU_ESTRUCTURA))
    await page.wait_for_selector(S.NX_PANEL, timeout=30000)
    await _pausa()


async def abrir_estructura(page: "Page") -> list[EtapaItem]:
    await volver_a_estructura(page)
    return parse_estructura(await _html(page.locator(S.NX_ESTRUCTURA)))


async def abrir_tarea(page: "Page", etapa_idx: int, tarea_idx: int) -> DetalleTarea:
    await _pausa()
    panel = page.locator(S.NX_PANEL).nth(etapa_idx)
    await _clic(panel.locator(S.NX_PANEL_ITEM_LINK).nth(tarea_idx))
    await page.wait_for_selector(S.NX_DETALLE_ROOT, timeout=30000)
    await _pausa()
    html = await _html(page.locator("mat-sidenav-content"))
    detalle = parse_detalle(html)
    if tiene_pestana_rubrica(html):
        detalle.rubrica = await _leer_rubrica_pestana(page)
    return detalle


async def _clic_pestana(page: "Page", css: str, texto: str) -> None:
    tab = page.locator(css)
    if not await tab.count():
        tab = page.locator(S.NX_TABS).filter(has_text=texto)
    await _clic(tab)


async def _leer_rubrica_pestana(page: "Page") -> Rubrica | None:
    await _pausa()
    await _clic_pestana(page, S.NX_TAB_RUBRICA_CSS, S.NX_TAB_RUBRICA_TEXT)
    try:
        await page.wait_for_selector(S.NX_RUBRICA, timeout=10000)
        rubrica = parse_rubrica(await _html(page.locator("mat-sidenav-content")))
    finally:
        await _pausa()
        with contextlib.suppress(Exception):
            await _clic_pestana(page, S.NX_TAB_CONTENIDOS_CSS, S.NX_TAB_CONTENIDOS_TEXT)
    return rubrica


async def volver_a_lista(page: "Page") -> None:
    link = page.locator(S.NX_LISTA_LINK)
    await _pausa()
    if await link.count():
        await _clic(link)
    else:
        # Workaround: no se conoce el enlace de retorno; se cambia el hash dentro de la SPA.
        await page.evaluate("location.hash = '#/App/UnidadesAprendizaje'")
    await esperar_lista(page)


class EntregaError(RuntimeError):
    pass


def parse_dialogo_entrega(markup: str) -> DialogoEntrega:
    root = parse(markup)
    tabs = select(root, S.NX_ENTREGA_TAB)
    activa = select_one(root, S.NX_ENTREGA_TAB_ACTIVA)
    return DialogoEntrega(
        pestanas=[text_of(t) for t in tabs],
        activa=text_of(activa) if activa is not None else None,
        tiene_input_file=select_one(root, S.NX_ENTREGA_INPUT) is not None,
        tiene_dropzone=select_one(root, S.NX_ENTREGA_DROPZONE) is not None,
    )


def parse_snackbar(markup: str) -> Snackbar | None:
    root = parse(markup)
    bar = select_one(root, S.NX_SNACKBAR)
    if bar is None:
        return None
    texto = text_of(select_one(bar, S.NX_SNACKBAR_TEXT)) or text_of(bar)
    exito = has_class(bar, S.NX_SNACKBAR_EXITO_CLASS) and S.NX_SNACKBAR_EXITO_TEXT in _norm(texto)
    return Snackbar(texto=texto, exito=exito)


async def _esperar_snackbar(page: "Page", timeout: float = 60.0) -> Snackbar:
    loop = asyncio.get_running_loop()
    limite = loop.time() + timeout
    while loop.time() < limite:
        bars = page.locator(S.NX_SNACKBAR)
        if await bars.count():
            snack = parse_snackbar(await _html(bars.last))
            if snack is not None and snack.texto:
                return snack
        await asyncio.sleep(0.5)
    raise EntregaError("NEXUS no confirmo la entrega en 60 segundos.")


async def _subir_archivo(page: "Page", pdf_path) -> None:
    try:
        await page.wait_for_selector(S.NX_ENTREGA_INPUT, state="attached", timeout=5000)
        await page.locator(S.NX_ENTREGA_INPUT).first.set_input_files(str(pdf_path))
        return
    except Exception:
        pass
    async with page.expect_file_chooser() as info:
        await page.locator(S.NX_ENTREGA_DROPZONE).click()
    chooser = await info.value
    await chooser.set_files(str(pdf_path))


async def _cerrar_dialogo(page: "Page") -> None:
    with contextlib.suppress(Exception):
        dialogo = page.locator(S.NX_ENTREGA_DIALOG).filter(has=page.locator(S.NX_ENTREGA_UPLOAD))
        if not await dialogo.count():
            return
        cerrar = dialogo.last.locator(S.NX_ENTREGA_CERRAR)
        if await cerrar.count():
            await cerrar.first.click(timeout=3000)
        else:
            await page.keyboard.press("Escape")
        await page.wait_for_selector(S.NX_OVERLAY_BACKDROP, state="detached", timeout=10000)


async def entregar(page: "Page", pdf_path, hooks: Hooks | None = None) -> None:
    hooks = hooks or Hooks()
    await _pausa()
    boton = page.locator(S.NX_ENTREGAR_BUTTON).filter(has_text=S.NX_ENTREGAR_TEXT).first
    await _clic(boton)
    await page.wait_for_selector(S.NX_ENTREGA_UPLOAD, timeout=30000)
    await _pausa()

    if not await page.locator(S.NX_ENTREGA_TAB_ACTIVA).filter(has_text=S.NX_ENTREGA_TAB_PC).count():
        tab_pc = page.locator(S.NX_ENTREGA_TAB).filter(has_text=re.compile(r"^\s*PC\s*$")).first
        await _clic(tab_pc)
        await _pausa()

    await hooks.log("Subiendo el PDF a NEXUS")
    await _subir_archivo(page, pdf_path)
    await _pausa()

    dialogo = page.locator(S.NX_ENTREGA_DIALOG).filter(has=page.locator(S.NX_ENTREGA_UPLOAD))
    if await dialogo.count():
        confirmar = dialogo.last.locator(S.NX_ENTREGA_CONFIRMAR)
    else:
        confirmar = page.locator(S.NX_ENTREGA_CONFIRMAR_FALLBACK)
    confirmar = confirmar.filter(has_text=S.NX_ENTREGAR_TEXT).last
    try:
        await confirmar.wait_for(state="visible", timeout=60000)
    except Exception as exc:
        raise EntregaError("El boton de confirmar no se habilito tras cargar el PDF.") from exc
    await _pausa()
    await _clic(confirmar)

    snack = await _esperar_snackbar(page)
    await _pausa(0.6, 1.2)
    with contextlib.suppress(Exception):
        await page.locator(S.NX_SNACKBAR_CLOSE).last.click(timeout=3000)
    await _cerrar_dialogo(page)
    if not snack.exito:
        raise EntregaError(f"NEXUS rechazo la entrega: {snack.texto}")
    await hooks.log(snack.texto)


__all__ = [
    "abrir_estructura",
    "abrir_materia",
    "abrir_tarea",
    "volver_a_estructura",
    "entregar",
    "EntregaError",
    "parse_dialogo_entrega",
    "parse_snackbar",
    "esperar_lista",
    "leer_materias",
    "parse_detalle",
    "parse_estructura",
    "parse_materias",
    "parse_pestanas",
    "tiene_pestana_rubrica",
    "parse_portada",
    "parse_rubrica",
    "volver_a_lista",
]
