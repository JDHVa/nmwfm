from backend.core import nexus

from . import fixtures


def test_dialogo_pestana_pc_con_input_file():
    d = nexus.parse_dialogo_entrega(fixtures.entregar_html())
    assert d.pestanas == ["PC", "OneDrive", "Recurso Externo"]
    assert d.activa == "PC"
    assert d.tiene_input_file
    assert d.tiene_dropzone


def test_snackbar_exito():
    snack = nexus.parse_snackbar(fixtures.SNACKBAR_EXITO)
    assert snack.exito
    assert snack.texto == "La Tarea ha sido cargada y entregada con éxito"


def test_snackbar_exito_sin_acentos_ni_mayusculas():
    html = fixtures.SNACKBAR_EXITO.replace("entregada con éxito", "ENTREGADA CON EXITO")
    assert nexus.parse_snackbar(html).exito


def test_snackbar_sin_clase_de_exito_es_error():
    html = fixtures.SNACKBAR_EXITO.replace(" snackbar-success", " snackbar-error").replace(
        "La Tarea ha sido cargada y entregada con éxito", "Archivo demasiado grande"
    )
    snack = nexus.parse_snackbar(html)
    assert not snack.exito
    assert snack.texto == "Archivo demasiado grande"


def test_snackbar_exito_con_otro_texto_no_cuenta():
    html = fixtures.SNACKBAR_EXITO.replace("entregada con éxito", "guardada")
    assert not nexus.parse_snackbar(html).exito


def test_sin_snackbar():
    assert nexus.parse_snackbar("<div></div>") is None
