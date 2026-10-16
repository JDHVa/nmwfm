import asyncio

from backend import config
from backend.api import create_app
from backend.jobs import JobManager

from .asgi_client import MiniClient, multipart
from .test_images import synthetic_photo


def test_health_sin_token_y_resto_protegido(app):
    anon = MiniClient(app)
    assert anon.get("/health").status_code == 200
    r = anon.get("/settings")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "no_autorizado"
    bad = MiniClient(app, headers={"X-Token": "otro"})
    assert bad.get("/settings").status_code == 401


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": config.VERSION}


def test_error_format_404(client):
    r = client.get("/tareas/no-existe")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "tarea_no_encontrada" and err["message"]


def test_cors_preflight(app):
    r = MiniClient(app).request(
        "OPTIONS",
        "/health",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-token",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:1420"


def test_settings_roundtrip(client, state):
    r = client.get("/settings")
    assert r.json() == {
        "cuenta": "",
        "tiene_password": False,
        "nombre": "",
        "matricula": "",
        "dev": True,
        "entregar_sin_revisar": False,
        "reducir_animaciones": False,
        "sync_inicial_hecha": False,
        "ultima_sync": None,
        "sync_cada_horas": 0,
        "recorte_modelo": "auto",
        "modelo_recorte_disponible": False,
    }
    r = client.put(
        "/settings",
        json={
            "cuenta": "1234567",
            "nombre": "Ana",
            "password": "secreto",
            "reducir_animaciones": True,
        },
    )
    body = r.json()
    assert r.status_code == 200
    assert body["cuenta"] == "1234567" and body["tiene_password"] is True
    assert "password" not in body and "secreto" not in r.content.decode()
    assert state.credentials.get("1234567") == "secreto"
    assert body["reducir_animaciones"] is True and body["nombre"] == "Ana"


def test_settings_validation(client):
    r = client.put("/settings", json={"entregar_sin_revisar": "si"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validacion"
    assert client.put("/settings", json={"password": "x"}).json()["error"]["code"] == "sin_cuenta"


def test_sync_sin_credenciales(client):
    r = client.post("/sync")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "sin_credenciales"


def test_materias_y_etapas(client, seeded):
    materias = client.get("/materias").json()
    assert materias[0]["nombre"] == "Lógica" and materias[0]["profesor"] == "PROFE UNO"
    etapas = client.get("/materias/100/etapas").json()
    assert etapas[0]["tareas"][0]["id"] == "100-1.1"
    assert etapas[0]["tareas"][0]["estado"] == "pendiente"
    assert client.get("/materias/999/etapas").status_code == 404


def test_insumos_flujo(client, seeded):
    tid = "100-1.1"
    r = client.post(f"/tareas/{tid}/insumos/texto", json={"texto": "mis apuntes"})
    assert r.status_code == 200 and r.json()["texto"] == "mis apuntes"
    a = r.json()["id"]
    b = client.post(f"/tareas/{tid}/insumos/texto", json={"texto": "otro"}).json()["id"]

    r = client.patch(f"/insumos/{b}", json={"orden": 0, "rotacion": 90})
    assert r.json()["rotacion"] == 90
    ids = [i["id"] for i in client.get(f"/tareas/{tid}/insumos").json()]
    assert ids == [b, a]
    assert client.patch(f"/insumos/{a}", json={"rotacion": 45}).status_code == 422

    assert client.delete(f"/insumos/{a}").status_code == 204
    assert len(client.get(f"/tareas/{tid}/insumos").json()) == 1
    assert client.delete(f"/insumos/{a}").status_code == 404


def test_subida_imagen_y_files(client, seeded):
    import cv2

    photo, _ = synthetic_photo()
    ok, buf = cv2.imencode(".jpg", photo)
    body, ctype = multipart([("files", "foto.jpg", buf.tobytes())])
    r = client.post("/tareas/100-1.1/insumos", content=body, headers={"content-type": ctype})
    assert r.status_code == 200, r.content
    insumo = r.json()[0]
    assert insumo["tipo"] == "imagen" and insumo["usar_recorte"] is True
    assert insumo["recortada_url"].startswith("/files/insumos/")
    served = client.get(insumo["recortada_url"])
    assert served.status_code == 200 and served.content[:2] == b"\xff\xd8"
    assert client.get("/files/nmwfm.db").status_code == 404
    assert client.get("/files/insumos/../nmwfm.db").status_code == 404

    bad, ctype = multipart([("files", "nota.txt", b"hola")])
    r = client.post("/tareas/100-1.1/insumos", content=bad, headers={"content-type": ctype})
    assert r.status_code == 400 and r.json()["error"]["code"] == "imagen_invalida"


def test_generacion_vacia_y_entregar_requiere_confirmar(client, seeded):
    assert client.get("/tareas/100-1.1/generacion").json() is None
    r = client.post("/tareas/100-1.1/entregar", json={"confirmar": False})
    assert r.status_code == 400
    assert client.post("/jobs/zzz/continuar").status_code == 404


def test_job_esperando_usuario_y_continuar(state):
    app = create_app(state=state)
    client = MiniClient(app, headers={"X-Token": "dev"})

    async def scenario():
        reached = asyncio.Event()

        async def fake(ctx):
            await ctx.update("paso uno", 0.5)
            reached.set()
            await ctx.wait_user("resuelve el captcha")
            return {"hecho": True}

        job = state.jobs.start("sync", fake)
        queue = state.jobs.subscribe()
        await reached.wait()
        for _ in range(50):
            data = (await client.arequest("GET", f"/jobs/{job.id}")).json()
            if data["estado"] == "esperando_usuario":
                break
            await asyncio.sleep(0.02)
        assert data["estado"] == "esperando_usuario" and data["mensaje"] == "resuelve el captcha"
        assert data["progreso"] == 50
        resumed = (await client.arequest("POST", f"/jobs/{job.id}/continuar")).json()
        assert resumed["id"] == job.id
        for _ in range(50):
            data = (await client.arequest("GET", f"/jobs/{job.id}")).json()
            if data["estado"] == "ok":
                break
            await asyncio.sleep(0.02)
        assert data["estado"] == "ok" and data["resultado"] == {"hecho": True}
        assert data["progreso"] == 100
        mensajes = []
        while not queue.empty():
            mensajes.append(queue.get_nowait())
        assert {m["type"] for m in mensajes} == {"job"}
        assert any(m["job"]["estado"] == "esperando_usuario" for m in mensajes)

    asyncio.run(scenario())


def test_job_error(state):
    async def scenario():
        async def boom(ctx):
            raise NotImplementedError("sin dialogo de subida")

        job = state.jobs.start("entregar", boom)
        for _ in range(50):
            if job.estado == "error":
                break
            await asyncio.sleep(0.02)
        assert job.estado == "error" and "sin dialogo" in job.mensaje

    asyncio.run(scenario())


def test_job_manager_es_independiente():
    assert JobManager().get("x") is None
