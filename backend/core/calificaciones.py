import math
import re
import unicodedata
import zlib

import numpy as np

APROBATORIA = 70.0
MUESTRAS = 5000
SEMILLA = 20260101
TOLERANCIA_SUMA = 4.0
TOLERANCIA_RAZON = 0.05
CAL_MINIMA_RAZON = 10.0
PESO_PRIOR = 3
PESO_PRIOR_GRUPO = 2
DESV_MINIMA = 5.0
MEDIA_SIN_DATOS = 80.0
DESV_SIN_DATOS = 15.0

ORDEN = ("par1", "emt", "par2", "eg", "portafolio")
NOMBRES = {
    "par1": "Parcial 1",
    "emt": "Medio término",
    "par2": "Parcial 2",
    "eg": "Examen global",
    "portafolio": "Portafolio",
}
PESOS = {
    "bachillerato": {"par1": 10, "emt": 15, "par2": 10, "eg": 25, "portafolio": 40},
    "carrera": {"par1": 10, "emt": 15, "par2": 10, "eg": 15, "portafolio": 50},
    "portafolio": {"portafolio": 100},
}
TIPOS = tuple(PESOS)
SUMA_POR_TIPO = {"bachillerato": 40, "carrera": 50, "portafolio": 100}
RAZON_POR_TIPO = {"bachillerato": 0.4, "carrera": 0.5, "portafolio": 1.0}
EXAMENES = ("par1", "emt", "par2", "eg")
CAMPO_HISTORIAL = {
    "par1": "par1",
    "par2": "par2",
    "emt": "emt",
    "eg": "eg",
    "portafolio": "port",
    "total": "total",
}
MIN_OBSERVACIONES_HISTORIAL = 3
SESGO = 0.5
UMBRAL_BAJO_HISTORICO = 5.0
UMBRAL_EXAMEN_BAJO = 80.0
PERDIDOS_SIN_HISTORIAL = 6.0
PROB_MINIMA = 0.5 / MUESTRAS


def normalizar(texto: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sin_acentos.lower()).strip()


def nombre_materia(texto: str) -> str:
    return re.sub(r"^\d+\s+", "", normalizar(texto))


def mismo_nombre(a: str, b: str, minimo: int = 6) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    corto, largo = sorted((a, b), key=len)
    return len(corto) >= minimo and corto in largo


def numero(texto: str | None) -> float | None:
    if texto is None:
        return None
    encontrado = re.fullmatch(r"\s*(-?\d+(?:[.,]\d+)?)\s*", texto)
    return float(encontrado.group(1).replace(",", ".")) if encontrado else None


def es_diagnostico(titulo: str) -> bool:
    plano = normalizar(titulo)
    return "diagnostic" in plano or "diagnostico" in plano


def _indice(columnas: list[str], prefijo: str) -> int | None:
    for i, columna in enumerate(columnas):
        if normalizar(columna).startswith(prefijo):
            return i
    return None


def elementos_portafolio(datos: dict | None) -> list[dict]:
    if not datos:
        return []
    columnas = datos.get("columnas") or []
    i_titulo = _indice(columnas, "elemento")
    i_cal = _indice(columnas, "calificacion")
    i_valor = _indice(columnas, "valor")
    i_puntos = _indice(columnas, "puntos")
    elementos = []
    for fila in datos.get("filas") or []:
        if None in (i_cal, i_valor, i_puntos) or max(i_cal, i_valor, i_puntos) >= len(fila):
            if len(fila) < 4:
                continue
            c_cal, c_valor, c_puntos = fila[-3], fila[-2], fila[-1]
        else:
            c_cal, c_valor, c_puntos = fila[i_cal], fila[i_valor], fila[i_puntos]
        if i_titulo is not None and i_titulo < len(fila):
            titulo = fila[i_titulo]
        else:
            titulo = next((c for c in fila[:-3] if c), "")
        valor = numero(c_valor)
        if not titulo or valor is None or es_diagnostico(titulo):
            continue
        cal = numero(c_cal)
        puntos = None
        if cal is not None:
            puntos = numero(c_puntos)
            if puntos is None:
                puntos = cal * valor / 100
        elementos.append({"titulo": titulo, "valor": valor, "calificacion": cal, "puntos": puntos})
    return elementos


def detectar_tipo(suma_valor: float | None, port_cal: float | None, port_pts: float | None):
    if suma_valor:
        for tipo, objetivo in SUMA_POR_TIPO.items():
            if abs(suma_valor - objetivo) <= TOLERANCIA_SUMA:
                return tipo
    if port_cal and port_pts is not None and port_cal >= CAL_MINIMA_RAZON:
        razon = port_pts / port_cal
        for tipo, objetivo in RAZON_POR_TIPO.items():
            if abs(razon - objetivo) <= TOLERANCIA_RAZON:
                return tipo
    return None


def _redondear(valor: float | None, decimales: int = 2) -> float | None:
    return None if valor is None else round(float(valor), decimales)


def _preparar(entrada: dict, tipo_manual: str | None) -> dict:
    notas = entrada.get("notas") or {}
    elementos = entrada.get("portafolio") or None
    port_siase = notas.get("portafolio") or {}
    suma_valor = sum(e["valor"] for e in elementos) if elementos else None
    tipo_auto = detectar_tipo(suma_valor, port_siase.get("cal"), port_siase.get("pts"))
    tipo = tipo_manual if tipo_manual in PESOS else tipo_auto
    pesos = PESOS.get(tipo, {})

    componentes = []
    obs_examen: list[float] = []
    obs_tarea: list[float] = []
    pendientes = []
    for clave in ORDEN:
        if clave not in pesos and not (tipo is None and notas.get(clave)):
            continue
        peso = pesos.get(clave, 0)
        nota = notas.get(clave) or {}
        cal, pts = nota.get("cal"), nota.get("pts")
        if clave == "portafolio" and elementos:
            calificados = [e for e in elementos if e["calificacion"] is not None]
            pts = sum(e["puntos"] for e in calificados) if calificados else None
            if cal is None and calificados:
                base = sum(e["valor"] for e in calificados)
                cal = pts / base * 100 if base else None
        elif cal is not None and pts is None:
            pts = cal * peso / 100
        componentes.append(
            {
                "clave": clave,
                "nombre": NOMBRES[clave],
                "peso": peso,
                "calificacion": _redondear(cal),
                "puntos": _redondear(pts),
            }
        )
        if clave != "portafolio":
            if cal is not None:
                obs_examen.append(cal)
            elif peso:
                pendientes.append({"clave": clave, "titulo": NOMBRES[clave], "peso": peso})
        elif elementos:
            for e in elementos:
                if e["calificacion"] is not None:
                    obs_tarea.append(e["calificacion"])
                else:
                    pendientes.append(
                        {"clave": "portafolio", "titulo": e["titulo"], "peso": e["valor"]}
                    )
        elif peso:
            restante = peso - (pts or 0)
            if restante > 1e-9:
                pendientes.append(
                    {"clave": "portafolio", "titulo": "Resto del portafolio", "peso": restante}
                )

    asegurados = sum(c["puntos"] for c in componentes if c["puntos"] is not None)
    evaluado = sum(
        c["peso"]
        for c in componentes
        if c["clave"] != "portafolio" and c["calificacion"] is not None
    )
    comp_port = next((c for c in componentes if c["clave"] == "portafolio"), None)
    if elementos:
        evaluado += sum(e["valor"] for e in elementos if e["calificacion"] is not None)
    elif comp_port and comp_port["puntos"] is not None:
        evaluado += comp_port["puntos"]
    hay_datos = bool(obs_examen or obs_tarea) or any(c["puntos"] is not None for c in componentes)
    return {
        "entrada": entrada,
        "tipo": tipo,
        "tipo_manual": tipo_manual in PESOS,
        "componentes": componentes,
        "portafolio": [
            {
                "titulo": e["titulo"],
                "valor": e["valor"],
                "puntos": _redondear(e["puntos"]),
                "perdida": bool(e.get("perdida")),
            }
            for e in (elementos or [])
        ],
        "pendientes": pendientes,
        "asegurados": asegurados,
        "evaluado": evaluado,
        "obs_examen": obs_examen,
        "obs_tarea": obs_tarea,
        "hay_datos": hay_datos,
    }


def _estadisticas_globales(preparadas: list[dict]) -> tuple[float, float]:
    todas = [x for p in preparadas for x in p["obs_examen"] + p["obs_tarea"]]
    if not todas:
        return MEDIA_SIN_DATOS, DESV_SIN_DATOS
    return float(np.mean(todas)), max(float(np.std(todas)), DESV_MINIMA)


def _mezclar(n: int, media: float, prior: float, peso_prior: float) -> float:
    return (n * media + peso_prior * prior) / (n + peso_prior)


def _estadisticas(valores: list[float]) -> dict:
    if not valores:
        return {"media": 0.0, "desv": 0.0, "n": 0, "prob_100": 0.0}
    arreglo = np.array(valores, dtype=float)
    return {
        "media": float(arreglo.mean()),
        "desv": float(arreglo.std()),
        "n": len(valores),
        "prob_100": float(np.mean(arreglo >= 100 - 1e-9)),
    }


def _contexto_historial(historial: list[dict] | None) -> dict | None:
    if not historial:
        return None
    valores: dict[str, list[float]] = {clave: [] for clave in CAMPO_HISTORIAL}
    for materia in historial:
        for clave, campo in CAMPO_HISTORIAL.items():
            if materia.get(campo) is not None:
                valores[clave].append(float(materia[campo]))
    if not any(valores.values()):
        return None
    return {
        "valores": valores,
        "stats": {clave: _estadisticas(v) for clave, v in valores.items()},
        "examenes": _estadisticas([x for clave in EXAMENES for x in valores[clave]]),
        "tareas": _estadisticas(valores["portafolio"]),
        "min_total": min(valores["total"]) if valores["total"] else None,
    }


def resumen_historial(historial: list[dict] | None) -> dict:
    contexto = _contexto_historial(historial)
    resumen = {}
    for clave in CAMPO_HISTORIAL:
        e = contexto["stats"][clave] if contexto else _estadisticas([])
        resumen[clave] = {
            "media": _redondear(e["media"]),
            "desv": _redondear(e["desv"]),
            "n": e["n"],
            "prob_100": _redondear(e["prob_100"], 3),
        }
    return resumen


def numero_semestre(periodo: str) -> int | None:
    plano = normalizar(periodo)
    encontrado = re.fullmatch(r"semestre (\d+)", plano) or re.fullmatch(
        r"(\d+) ?(?:er|ro|do|to|vo|mo|no|o|a)? semestre", plano
    )
    return int(encontrado.group(1)) if encontrado else None


def fusionar_kardex(semestres: list[dict]) -> list[dict]:
    propios = [{**s, "materias": [m for m in s["materias"] if "clave" not in m]} for s in semestres]
    sin_nombre = {
        numero_semestre(s["periodo"])
        for s in propios
        if s["materias"] and all(not m.get("nombre") for m in s["materias"])
    }
    por_nombre = {
        normalizar(m["nombre"]): m for s in propios for m in s["materias"] if m.get("nombre")
    }
    nuevos = []
    for s in semestres:
        agregadas = []
        for m in s["materias"]:
            if "clave" not in m:
                continue
            existente = por_nombre.get(normalizar(m.get("nombre") or ""))
            if existente is not None:
                existente["total"] = m["total"]
            elif numero_semestre(s["periodo"]) not in sin_nombre:
                agregadas.append({k: v for k, v in m.items() if k != "clave"})
        if agregadas:
            nuevos.append({"periodo": s["periodo"], "materias": agregadas})
    return [s for s in propios if s["materias"]] + nuevos


def _remuestreo(valores: list[float], rng: np.random.Generator) -> np.ndarray:
    arreglo = np.array(valores, dtype=float)
    n = len(arreglo)
    ancho = max(1.0, 1.06 * float(arreglo.std()) * n**-0.2)
    elegidos = arreglo[rng.integers(0, n, size=MUESTRAS)]
    ruido = rng.normal(size=MUESTRAS) * ancho
    suavizados = np.where(elegidos >= 100 - 1e-9, elegidos, elegidos + ruido)
    return np.where(suavizados > 100, 200 - suavizados, suavizados)


def _notas(p: dict, media_global: float, desv_global: float, hist: dict | None) -> np.ndarray:
    pendientes = p["pendientes"]
    rng = np.random.default_rng(SEMILLA + zlib.crc32(p["entrada"]["clave"].encode()))
    todas = p["obs_examen"] + p["obs_tarea"]
    n = len(todas)
    media = float(np.mean(todas)) if n else media_global
    varianza = float(np.var(todas)) if n else 0.0
    mu = _mezclar(n, media, media_global, PESO_PRIOR)
    desv = max(
        math.sqrt(_mezclar(n, varianza, desv_global**2, PESO_PRIOR)),
        DESV_MINIMA,
    )
    medias = []
    for pendiente in pendientes:
        grupo = p["obs_tarea"] if pendiente["clave"] == "portafolio" else p["obs_examen"]
        medias.append(
            _mezclar(len(grupo), float(np.mean(grupo)), mu, PESO_PRIOR_GRUPO) if grupo else mu
        )
    ruido = rng.normal(size=(MUESTRAS, len(pendientes))) * desv
    aleatorio = rng.normal(size=(MUESTRAS, 1))
    notas = np.array(medias) + aleatorio * desv / math.sqrt(n + PESO_PRIOR) + ruido
    if hist is not None:
        factor = np.exp(SESGO * aleatorio[:, 0] / math.sqrt(n + PESO_PRIOR))
        for j, pendiente in enumerate(pendientes):
            valores = hist["valores"][pendiente["clave"]]
            if len(valores) < MIN_OBSERVACIONES_HISTORIAL:
                continue
            tarea = pendiente["clave"] == "portafolio"
            obs = p["obs_tarea"] if tarea else p["obs_examen"]
            referencia = hist["tareas" if tarea else "examenes"]["media"]
            desplazamiento = (
                (float(np.mean(obs)) - referencia) * len(obs) / (len(obs) + PESO_PRIOR)
                if obs
                else 0.0
            )
            muestra = _remuestreo(valores, rng)
            base = 100 - (100 - muestra) * factor
            notas[:, j] = np.where(
                (desplazamiento < 0) & (muestra >= 100 - 1e-9), base, base + desplazamiento
            )
    return np.clip(notas, 0, 100)


def _simular(p: dict, media_global: float, desv_global: float, hist: dict | None) -> np.ndarray:
    pendientes = p["pendientes"]
    if not pendientes:
        return np.full(MUESTRAS, min(100.0, p["asegurados"]))
    pesos = np.array([x["peso"] for x in pendientes], dtype=float)
    notas = _notas(p, media_global, desv_global, hist)
    return np.clip(p["asegurados"] + notas @ pesos / 100, 0, 100)


def _necesario(objetivo: float | None, asegurados: float, peso_pendiente: float) -> float | None:
    if objetivo is None or peso_pendiente <= 0:
        return None
    return max(0.0, 100 * (objetivo - asegurados) / peso_pendiente)


def _probabilidad(muestras: np.ndarray, umbral: float, alcanzable: bool) -> float:
    if not alcanzable:
        return 0.0
    prob = float(np.mean(muestras >= umbral - 1e-9))
    return max(prob, PROB_MINIMA)


def _redondear_prob(prob: float | None) -> float | None:
    if prob is None:
        return None
    return round(prob, 6) if 0 < prob < 0.005 else round(prob, 3)


def _alertas(p: dict, hist: dict | None) -> list[dict]:
    alertas = []
    componentes = {c["clave"]: c for c in p["componentes"]}
    if hist is not None:
        revisados = [
            (c["nombre"], c["clave"], c["calificacion"])
            for c in p["componentes"]
            if c["calificacion"] is not None and (c["clave"] != "portafolio" or p["obs_tarea"])
        ]
        if len(p["obs_examen"]) > 1:
            revisados.append(("Promedio de exámenes", "examenes", float(np.mean(p["obs_examen"]))))
        for nombre, clave, cal in revisados:
            referencia = hist["examenes"] if clave == "examenes" else hist["stats"][clave]
            if referencia["n"] and cal < referencia["media"] - UMBRAL_BAJO_HISTORICO:
                alertas.append(
                    {
                        "tipo": "bajo_historico",
                        "detalle": f"{nombre}: {cal:.0f}, tu media histórica es "
                        f"{referencia['media']:.0f}",
                    }
                )
    for clave in EXAMENES:
        c = componentes.get(clave)
        if c and c["calificacion"] is not None and c["calificacion"] <= UMBRAL_EXAMEN_BAJO + 1e-9:
            alertas.append(
                {"tipo": "examen_bajo", "detalle": f"{c['nombre']}: {c['calificacion']:.0f}"}
            )
    perdidos = p["evaluado"] - p["asegurados"]
    limite = (
        100 - hist["min_total"]
        if hist is not None and hist["min_total"] is not None
        else PERDIDOS_SIN_HISTORIAL
    )
    if perdidos > limite + 1e-9:
        alertas.append(
            {
                "tipo": "puntos_perdidos",
                "detalle": f"Perdiste {perdidos:.1f} puntos de lo evaluado (límite {limite:.1f})",
            }
        )
    unicas = {(a["tipo"], a["detalle"]): a for a in alertas}
    return list(unicas.values())


def _estado(p: dict, prob_aprobar: float, prob_objetivo: float | None, alertas: list) -> str:
    if not p["hay_datos"]:
        return "sin_datos"
    peso_pendiente = sum(x["peso"] for x in p["pendientes"])
    if peso_pendiente > 0:
        necesario_aprobar = max(0.0, 100 * (APROBATORIA - p["asegurados"]) / peso_pendiente)
    else:
        necesario_aprobar = 0.0 if p["asegurados"] >= APROBATORIA else math.inf
    if prob_aprobar < 0.6 or necesario_aprobar > 90:
        return "riesgo"
    if alertas or (prob_objetivo is not None and prob_objetivo < 0.5):
        return "atento"
    return "bien"


def _tabla(p: dict) -> dict:
    comp_port = next((c for c in p["componentes"] if c["clave"] == "portafolio"), None)
    examenes = [c for c in p["componentes"] if c["clave"] != "portafolio"]
    total = p["asegurados"]
    evaluado = p["evaluado"]
    return {
        "portafolio_pts": _redondear((comp_port["puntos"] or 0.0) if comp_port else 0.0),
        "portafolio_max": _redondear(comp_port["peso"] if comp_port else 0.0),
        "examenes_pts": _redondear(sum(c["puntos"] or 0.0 for c in examenes)),
        "examenes_max": _redondear(sum(c["peso"] for c in examenes)),
        "total_pts": _redondear(total),
        "evaluado_pts": _redondear(evaluado),
        "pct_evaluado": _redondear(total / evaluado * 100) if evaluado > 0 else None,
    }


def _materia(p: dict, muestras: np.ndarray, objetivo: float | None, hist: dict | None) -> dict:
    entrada = p["entrada"]
    peso_pendiente = sum(x["peso"] for x in p["pendientes"])
    maximo = p["asegurados"] + peso_pendiente
    necesario = _necesario(objetivo, p["asegurados"], peso_pendiente)
    alcanzable = objetivo is None or maximo >= objetivo - 1e-9
    prob_objetivo = None if objetivo is None else _probabilidad(muestras, objetivo, alcanzable)
    prob_aprobar = float(np.mean(muestras >= APROBATORIA - 1e-9))
    bajo, alto = np.percentile(muestras, [10, 90])
    alertas = _alertas(p, hist)
    return {
        "clave": entrada["clave"],
        "nombre": entrada["nombre"],
        "materia_id": entrada.get("materia_id"),
        "tipo": p["tipo"],
        "tipo_manual": p["tipo_manual"],
        "componentes": p["componentes"],
        "portafolio": p["portafolio"],
        "pendientes": [{**x, "peso": _redondear(x["peso"])} for x in p["pendientes"]],
        "asegurados": _redondear(p["asegurados"]),
        "maximo_posible": _redondear(maximo),
        "proyectada": _redondear(np.mean(muestras)),
        "rango": [_redondear(bajo), _redondear(alto)],
        "objetivo": objetivo,
        "necesario": _redondear(necesario, 1),
        "alcanzable": alcanzable,
        "prob_objetivo": _redondear_prob(prob_objetivo),
        "prob_aprobar": _redondear(prob_aprobar, 3),
        "estado": _estado(p, prob_aprobar, prob_objetivo, alertas),
        "alertas": alertas,
        "en_cuidado": bool(alertas),
        **_tabla(p),
    }


def calcular(
    entradas: list[dict],
    tipos_manuales: dict[str, str] | None = None,
    objetivos: dict[str, float] | None = None,
    objetivo_semestre: float | None = None,
    siase_leida_en: str | None = None,
    historial: list[dict] | None = None,
    nexus_leido_en: str | None = None,
) -> dict:
    tipos_manuales = tipos_manuales or {}
    objetivos = objetivos or {}
    hist = _contexto_historial(historial)
    preparadas = [_preparar(e, tipos_manuales.get(e["clave"])) for e in entradas]
    media_global, desv_global = _estadisticas_globales(preparadas)
    muestras = [_simular(p, media_global, desv_global, hist) for p in preparadas]
    materias = [
        _materia(p, m, objetivos.get(p["entrada"]["clave"]), hist)
        for p, m in zip(preparadas, muestras, strict=True)
    ]

    cantidad = len(preparadas)
    if cantidad:
        promedio = np.mean(np.vstack(muestras), axis=0)
        actual = sum(p["asegurados"] for p in preparadas) / cantidad
        pendiente_total = sum(x["peso"] for p in preparadas for x in p["pendientes"])
        necesario = None
        if objetivo_semestre is not None and pendiente_total > 0:
            necesario = max(0.0, 100 * (objetivo_semestre - actual) * cantidad / pendiente_total)
        bajo, alto = np.percentile(promedio, [10, 90])
        maximo_semestre = actual + pendiente_total / cantidad
        prob_objetivo = (
            None
            if objetivo_semestre is None
            else _probabilidad(
                promedio, objetivo_semestre, maximo_semestre >= objetivo_semestre - 1e-9
            )
        )
        semestre = {
            "actual": _redondear(actual),
            "proyectada": _redondear(np.mean(promedio)),
            "rango": [_redondear(bajo), _redondear(alto)],
            "objetivo": objetivo_semestre,
            "prob_objetivo": _redondear_prob(prob_objetivo),
            "necesario_promedio": _redondear(necesario, 1),
        }
    else:
        semestre = {
            "actual": 0.0,
            "proyectada": 0.0,
            "rango": [0.0, 0.0],
            "objetivo": objetivo_semestre,
            "prob_objetivo": None,
            "necesario_promedio": None,
        }
    return {
        "materias": materias,
        "semestre": semestre,
        "siase_leida_en": siase_leida_en,
        "nexus_leido_en": nexus_leido_en,
    }


def _nota_preset(
    preset: str,
    p: dict,
    tarea: bool,
    hist: dict | None,
    alertas: list,
    esfuerzo: bool,
    media_mio: float,
    media_global: float,
    desv_global: float,
) -> float:
    observadas = p["obs_tarea"] if tarea else p["obs_examen"]
    obs = float(np.mean(observadas)) if observadas else None
    if preset == "pesimista":
        grupo = hist["tareas" if tarea else "examenes"] if hist else None
        if grupo is not None and grupo["n"]:
            base = grupo["media"] if obs is None else min(obs, grupo["media"])
            return base - grupo["desv"]
        return (media_global if obs is None else obs) - desv_global
    if preset == "optimista":
        if alertas and not esfuerzo and obs is not None:
            return max(obs, media_mio)
        return 100.0
    return media_mio


def _acotar(valor: float) -> float:
    return float(min(100.0, max(0.0, valor)))


def calcular_escenario(
    entradas: list[dict],
    escenario: dict,
    tipos_manuales: dict[str, str] | None = None,
    historial: list[dict] | None = None,
) -> dict:
    tipos_manuales = tipos_manuales or {}
    hist = _contexto_historial(historial)
    preparadas = [_preparar(e, tipos_manuales.get(e["clave"])) for e in entradas]
    media_global, desv_global = _estadisticas_globales(preparadas)
    preset = escenario["preset"]
    globales = {"examenes": escenario.get("examenes"), "tareas": escenario.get("tareas")}
    por_materia = escenario.get("materias") or {}
    resultado = []
    for p in preparadas:
        clave = p["entrada"]["clave"]
        pendientes = p["pendientes"]
        propios = por_materia.get(clave) or {}
        por_pendiente = {int(k): v for k, v in (propios.get("pendientes") or {}).items()}
        alertas = _alertas(p, hist)
        medias = (
            _notas(p, media_global, desv_global, hist).mean(axis=0) if pendientes else np.array([])
        )
        notas = []
        con_ajuste = False
        for j, pendiente in enumerate(pendientes):
            tarea = pendiente["clave"] == "portafolio"
            grupo = "tareas" if tarea else "examenes"
            nota = _nota_preset(
                preset,
                p,
                tarea,
                hist,
                alertas,
                bool(propios.get("esfuerzo")),
                float(medias[j]),
                media_global,
                desv_global,
            )
            for fijo in (globales[grupo], propios.get(grupo), por_pendiente.get(j)):
                if fijo is not None:
                    nota = fijo
                    con_ajuste = True
            notas.append(_acotar(nota))
        if preset == "mio" and not con_ajuste:
            final = float(np.mean(_simular(p, media_global, desv_global, hist)))
        else:
            final = p["asegurados"] + sum(
                n * x["peso"] / 100 for n, x in zip(notas, pendientes, strict=True)
            )
        resultado.append(
            {
                "clave": clave,
                "final": _redondear(_acotar(final)),
                "pendientes": [
                    {
                        "clave": x["clave"],
                        "titulo": x["titulo"],
                        "peso": _redondear(x["peso"]),
                        "nota": _redondear(n),
                    }
                    for x, n in zip(pendientes, notas, strict=True)
                ],
            }
        )
    semestre = sum(m["final"] for m in resultado) / len(resultado) if resultado else 0.0
    return {"materias": resultado, "semestre": _redondear(semestre)}
