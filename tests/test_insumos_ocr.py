import asyncio

from PIL import Image

from backend import services
from backend.core import ocr

from .asgi_client import MiniClient
from .test_services import TID, FakeGemini, correr, listo  # noqa: F401


def imagen(ruta, color="white"):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (60, 40), color).save(ruta)
    return ruta


class MotorFalso:
    def __call__(self, arreglo):
        return (
            [
                [[[0, 50], [10, 50], [10, 60], [0, 60]], "segunda línea", 0.9],
                [[[0, 5], [10, 5], [10, 15], [0, 15]], "primera línea", 0.9],
            ],
            None,
        )


def test_extraer_texto_ordena_por_posicion(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "_motor", MotorFalso())
    assert ocr.extraer_texto(imagen(tmp_path / "a.png"), 90) == "primera línea\nsegunda línea"


def test_extraer_texto_sin_resultados(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "_motor", lambda arr: (None, None))
    assert ocr.extraer_texto(imagen(tmp_path / "a.png")) == ""


class CtxRegistro:
    def __init__(self):
        self.mensajes = []

    async def log(self, mensaje, nivel="info"):
        self.mensajes.append(mensaje)

    async def update(self, *a, **kw):
        return None


def agregar_imagen(state, tmp_path):
    original = imagen(state.paths.insumos / TID / "o.png")
    recortada = imagen(state.paths.insumos / TID / "c.jpg")
    return state.storage.add_insumo(
        TID, "imagen", original_path=str(original), recortada_path=str(recortada)
    )


def test_sin_ocr_instalado_avisa_y_sigue(seeded, tmp_path, monkeypatch):
    agregar_imagen(seeded, tmp_path)
    monkeypatch.setattr(ocr, "disponible", lambda: False)
    ctx = CtxRegistro()
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == ""
    assert any("rapidocr-onnxruntime" in m for m in ctx.mensajes)


def test_ocr_se_cachea_y_se_invalida_al_rotar(seeded, tmp_path, monkeypatch):
    fila = agregar_imagen(seeded, tmp_path)
    llamadas = []

    def falso(ruta, rotacion=0):
        llamadas.append(rotacion)
        return f"texto {rotacion}"

    monkeypatch.setattr(ocr, "disponible", lambda: True)
    monkeypatch.setattr(ocr, "extraer_texto", falso)
    ctx = CtxRegistro()
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == "texto 0"
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == "texto 0"
    assert llamadas == [0]
    assert seeded.insumo_public(seeded.storage.get_insumo(fila["id"]))["ocr_texto"] == "texto 0"
    seeded.storage.update_insumo(fila["id"], rotacion=90)
    assert asyncio.run(services._texto_ocr(seeded, ctx, TID)) == "texto 90"
    assert llamadas == [0, 90]


def test_generar_agrega_el_texto_ocr_al_prompt(listo, tmp_path, monkeypatch):  # noqa: F811
    agregar_imagen(listo, tmp_path)
    prompts = []

    class Captura(FakeGemini):
        async def generar(self, prompt, pdf_path, hooks):
            prompts.append(prompt)
            return "## R\n\nT"

    listo.gemini = Captura()
    monkeypatch.setattr(ocr, "disponible", lambda: True)
    monkeypatch.setattr(ocr, "extraer_texto", lambda ruta, rotacion=0: "Apunte: ley de Ohm")
    job = correr(listo)
    assert job.estado == "ok", job.mensaje
    assert "Texto extraído de las imágenes" in prompts[0] and "ley de Ohm" in prompts[0]


def registrar(state, nombre, contenido: bytes | None, tmp_path):
    origen = None
    if contenido is not None:
        origen = tmp_path / nombre
        origen.write_bytes(contenido)
    return services.registrar_recurso(state, TID, nombre, origen)


def test_recursos_listar_y_usar_texto(app, seeded, tmp_path):
    client = MiniClient(app, headers={"X-Token": "dev"})
    r = registrar(seeded, "notas.txt", b"apuntes del profe", tmp_path)
    lista = client.get(f"/tareas/{TID}/recursos").json()
    assert lista == [
        {
            "id": r["id"],
            "tarea_id": TID,
            "nombre": "notas.txt",
            "tipo": "texto",
            "descargado": True,
            "usado": False,
        }
    ]
    uso = client.post(f"/tareas/{TID}/recursos/{r['id']}/usar")
    assert uso.status_code == 200 and uso.json()["texto"] == "apuntes del profe"
    assert client.get(f"/tareas/{TID}/recursos").json()[0]["usado"] is True


def test_recursos_usar_imagen_crea_insumo_recortado(app, seeded, tmp_path):
    client = MiniClient(app, headers={"X-Token": "dev"})
    origen = imagen(tmp_path / "foto.png", "gray")
    r = services.registrar_recurso(seeded, TID, "foto.png", origen)
    uso = client.post(f"/tareas/{TID}/recursos/{r['id']}/usar").json()
    assert uso["tipo"] == "imagen" and uso["recortada_url"]
    assert len(seeded.storage.list_insumos(TID)) == 1


def test_recursos_errores(app, seeded, tmp_path):
    client = MiniClient(app, headers={"X-Token": "dev"})
    pdf = registrar(seeded, "libro.pdf", b"%PDF", tmp_path)
    assert client.post(f"/tareas/{TID}/recursos/{pdf['id']}/usar").status_code == 415
    sin = registrar(seeded, "foto.png", None, tmp_path)
    r = client.post(f"/tareas/{TID}/recursos/{sin['id']}/usar")
    assert r.status_code == 409 and r.json()["error"]["code"] == "sin_descargar"
    assert client.post(f"/tareas/{TID}/recursos/nada/usar").status_code == 404
    assert client.get("/tareas/no-existe/recursos").status_code == 404
