import pytest

from backend.core import producto
from backend.core.prompt_builder import PromptData, build_prompt


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        ("Dimensión 2 - Comprensión - Ficha Técnica", "ficha_tecnica"),
        ("Dimensión 3 - Análisis - Mapa mental", "mapa_mental"),
        ("Cuadro comparativo de especies", "cuadro_comparativo"),
        ("Cuadro Sinóptico", "cuadro_sinoptico"),
        ("Cuadro sinóptico de los tipos", "cuadro_sinoptico"),
        ("Línea del tiempo de la Revolución", "linea_tiempo"),
        ("Infografía de reciclaje", "infografia"),
        ("Artículo de Opinión", "articulo_opinion"),
        ("Ensayo argumentativo", "ensayo"),
        ("Presentación en equipo", "presentacion"),
        ("Diagrama de flujo", "diagrama"),
        ("Evidencia de Aprendizaje - Informe", "informe"),
        ("Reporte de caso práctico sobre la norma ISO 9001:2015", "reporte"),
        ("Tarea sin pista", "generico"),
    ],
)
def test_detecta_producto_por_titulo(titulo, esperado):
    assert producto.detectar_producto(titulo) == esperado


def test_titulo_manda_sobre_la_actividad():
    assert producto.detectar_producto("Ficha técnica", "Elabora un informe") == "ficha_tecnica"


def test_usa_la_actividad_si_el_titulo_no_dice():
    assert producto.detectar_producto("Evidencia 1", "Realiza una línea del tiempo.") == (
        "linea_tiempo"
    )


def test_todos_los_tipos_tienen_plantilla():
    tipos = {t for t, _ in producto.PALABRAS_PRODUCTO} | {"generico"}
    for tipo in tipos:
        texto = producto.plantilla_producto(tipo)
        assert "Estructura" in texto and "Extensión" in texto


def test_plantilla_desconocida_cae_a_generica():
    assert producto.plantilla_producto("no-existe") == producto.plantilla_producto("generico")


def test_prompt_incluye_formato_del_tipo_apa_y_nivel_maximo():
    prompt = build_prompt(
        PromptData(materia="M", titulo="Dimensión 2 - Ficha Técnica", actividades="Haz la ficha")
    )
    assert "## Formato del producto" in prompt
    assert "Tipo de producto: ficha técnica." in prompt
    assert "APA 7" in prompt and "no inventes referencias" in prompt
    assert "nivel máximo" in prompt and "nivel intermedio" in prompt


def test_prompt_respeta_el_tipo_forzado():
    prompt = build_prompt(PromptData(materia="M", titulo="Algo", producto="ensayo"))
    assert "Tipo de producto: ensayo." in prompt
