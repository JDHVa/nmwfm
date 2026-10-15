from backend.core.prompt_builder import PromptData, build_prompt
from backend.core.types import Rubrica, RubricaCriterio, RubricaNivel


def rubrica() -> Rubrica:
    def niveles(p):
        return [RubricaNivel(p, "Descripción alta"), RubricaNivel(0, "Sin Evidencia")]

    return Rubrica(
        niveles=["Completa", "Sin Evidencia"],
        criterios=[
            RubricaCriterio("Explica correctamente los conceptos.", niveles(3)),
            RubricaCriterio("Muestra compromiso y responsabilidad en el trabajo.", niveles(2)),
            RubricaCriterio("Muestra Compromiso con la entrega.", niveles(1)),
        ],
    )


def test_prompt_excluye_responsabilidad_y_compromiso():
    prompt = build_prompt(
        PromptData(
            materia="Algoritmos Bio Inspirados",
            titulo="Ficha técnica",
            numero="1.2",
            puntos=2.5,
            actividades="Elabora una ficha.",
            contenido="- Demuestra responsabilidad.",
            criterios_desempeno="- Identifica fundamentos.\n- Muestra RESPONSABILIDAD.",
            rubrica=rubrica(),
            instrucciones_extra="Usa ejemplos locales.",
        )
    )
    assert "Explica correctamente los conceptos." in prompt
    assert "compromiso" not in prompt.lower()
    assert "Muestra RESPONSABILIDAD" not in prompt
    assert "Identifica fundamentos" in prompt
    assert "Algoritmos Bio Inspirados" in prompt
    assert "Usa ejemplos locales." in prompt
    assert "SOLO en Markdown" in prompt
    assert "nivel máximo" in prompt
    assert "archivos adjuntos" in prompt


def test_prompt_sin_insumos():
    prompt = build_prompt(PromptData(materia="M", titulo="T", tiene_insumos=False))
    assert "archivos adjuntos" not in prompt
