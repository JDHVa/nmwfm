import asyncio
import sqlite3
import zipfile

from backend import respaldo

from .asgi_client import MiniClient


def preparar_archivos(state):
    data = state.paths.data
    (data / "browser_profile").mkdir(exist_ok=True)
    (data / "browser_profile" / "Cookies").write_text("secreto")
    (data / "debug").mkdir(exist_ok=True)
    (data / "debug" / "snap.html").write_text("x")
    insumos = data / "insumos" / "100-1.1"
    insumos.mkdir(parents=True)
    (insumos / "a.txt").write_text("apunte original")
    gen = data / "generaciones" / "100-1.1"
    gen.mkdir(parents=True)
    (gen / "tarea.pdf").write_bytes(b"%PDF")


def crear(state):
    return asyncio.run(respaldo.crear(state))


def nombres(state, nombre):
    with zipfile.ZipFile(respaldo.carpeta(state) / nombre) as zf:
        return set(zf.namelist())


def test_crear_incluye_datos_y_excluye_perfil_debug_y_respaldos(seeded):
    preparar_archivos(seeded)
    primero = crear(seeded)
    segundo = crear(seeded)
    contenido = nombres(seeded, segundo["nombre"])
    assert "nmwfm.db" in contenido
    assert "insumos/100-1.1/a.txt" in contenido and "generaciones/100-1.1/tarea.pdf" in contenido
    assert not any(n.startswith(("browser_profile", "debug", "respaldos")) for n in contenido)
    assert primero["nombre"] != segundo["nombre"] or primero["bytes"] > 0
    assert segundo["url"].startswith("/files/respaldos/")


def test_la_base_del_zip_es_legible_y_consistente(seeded, tmp_path):
    respaldo_zip = crear(seeded)
    with zipfile.ZipFile(respaldo.carpeta(seeded) / respaldo_zip["nombre"]) as zf:
        zf.extract("nmwfm.db", tmp_path)
    filas = sqlite3.connect(tmp_path / "nmwfm.db").execute("SELECT id FROM tareas").fetchall()
    assert ("100-1.1",) in filas


def test_restaurar_recupera_base_y_archivos(seeded):
    preparar_archivos(seeded)
    copia = crear(seeded)
    seeded.storage.borrar_tareas(["100-1.1"])
    (seeded.paths.data / "insumos" / "100-1.1" / "a.txt").write_text("cambiado")
    assert seeded.storage.get_tarea("100-1.1") is None
    resultado = asyncio.run(respaldo.restaurar(seeded, respaldo.carpeta(seeded) / copia["nombre"]))
    assert resultado["restaurados"] >= 3
    assert resultado["respaldo_previo"].startswith("pre-restauracion-")
    assert seeded.storage.get_tarea("100-1.1") is not None
    assert (seeded.paths.data / "insumos" / "100-1.1" / "a.txt").read_text() == "apunte original"
    assert (respaldo.carpeta(seeded) / resultado["respaldo_previo"]).exists()


def zip_con(ruta, miembros):
    with zipfile.ZipFile(ruta, "w") as zf:
        for nombre, datos in miembros.items():
            zf.writestr(nombre, datos)
    return ruta


def test_rechaza_zip_con_rutas_peligrosas_sin_tocar_nada(seeded):
    malo = zip_con(
        respaldo.carpeta(seeded) / "malo.zip", {"nmwfm.db": b"x", "../fuera/evil.txt": b"mal"}
    )
    try:
        asyncio.run(respaldo.restaurar(seeded, malo))
    except respaldo.ApiError as exc:
        assert exc.status == 400 and exc.code == "respaldo_invalido"
    else:
        raise AssertionError("debía fallar")
    assert not (seeded.paths.data.parent / "fuera" / "evil.txt").exists()
    assert seeded.storage.get_tarea("100-1.1") is not None


def test_rechaza_zip_sin_base_y_archivo_que_no_es_zip(seeded):
    sin_db = zip_con(respaldo.carpeta(seeded) / "sin.zip", {"insumos/x.txt": b"x"})
    falso = respaldo.carpeta(seeded) / "falso.zip"
    falso.write_text("no soy zip")
    for ruta in (sin_db, falso):
        try:
            asyncio.run(respaldo.restaurar(seeded, ruta))
        except respaldo.ApiError as exc:
            assert exc.status == 400
        else:
            raise AssertionError("debía fallar")


def test_no_restaura_con_jobs_en_curso(seeded):
    copia = crear(seeded)

    async def escenario():
        async def lento(ctx):
            await asyncio.sleep(0.3)

        seeded.jobs.start("sync", lento)
        await asyncio.sleep(0.02)
        return await respaldo.restaurar(seeded, respaldo.carpeta(seeded) / copia["nombre"])

    try:
        asyncio.run(escenario())
    except respaldo.ApiError as exc:
        assert exc.status == 409 and exc.code == "jobs_en_curso"
    else:
        raise AssertionError("debía fallar")


def test_api_crear_listar_y_restaurar_por_nombre(app, seeded):
    client = MiniClient(app, headers={"X-Token": "dev"})
    creado = client.post("/respaldo").json()
    assert creado["bytes"] > 0
    assert [r["nombre"] for r in client.get("/respaldo").json()][0] == creado["nombre"]
    seeded.storage.borrar_tareas(["100-1.1"])
    r = client.post("/respaldo/restaurar", json={"nombre": creado["nombre"]})
    assert r.status_code == 200 and seeded.storage.get_tarea("100-1.1") is not None
    assert client.post("/respaldo/restaurar", json={"nombre": "no-existe.zip"}).status_code == 404


def test_api_restaurar_subiendo_el_zip(app, seeded):
    client = MiniClient(app, headers={"X-Token": "dev"})
    creado = client.post("/respaldo").json()
    datos = (respaldo.carpeta(seeded) / creado["nombre"]).read_bytes()
    seeded.storage.borrar_tareas(["100-1.1"])
    limite = "----limite"
    cuerpo = (
        (
            f'--{limite}\r\nContent-Disposition: form-data; name="file"; filename="b.zip"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode()
        + datos
        + f"\r\n--{limite}--\r\n".encode()
    )
    r = client.post(
        "/respaldo/restaurar",
        content=cuerpo,
        headers={"content-type": f"multipart/form-data; boundary={limite}"},
    )
    assert r.status_code == 200, r.content
    assert seeded.storage.get_tarea("100-1.1") is not None
