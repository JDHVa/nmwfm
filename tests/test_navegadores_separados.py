import asyncio

from backend import services
from backend.core.browser import BrowserManager
from backend.core.gemini import GeminiWeb

from .test_services import TID, FakeGemini, correr, listo  # noqa: F401
from .test_sync_modos import _FakePw


class PwCompartido(_FakePw):
    def __init__(self):
        super().__init__()
        self.perfiles = []

    async def launch_persistent_context(self, **kw):
        self.perfiles.append(kw["user_data_dir"])
        ctx = await super().launch_persistent_context(**kw)
        ctx.user_data_dir = kw["user_data_dir"]
        return ctx


def dos_managers(tmp_path):
    nexus = BrowserManager(tmp_path / "browser_profile", dev=True)
    gemini = BrowserManager(tmp_path / "gemini_profile", dev=True)
    pw = PwCompartido()
    nexus._pw = pw
    gemini._pw = pw
    return nexus, gemini, pw


def test_cada_manager_abre_su_propio_perfil(tmp_path):
    nexus, gemini, pw = dos_managers(tmp_path)

    async def escenario():
        return await nexus.context(headless=True), await gemini.context()

    c_nexus, c_gemini = asyncio.run(escenario())
    assert c_nexus is not c_gemini
    assert pw.perfiles == [str(tmp_path / "browser_profile"), str(tmp_path / "gemini_profile")]
    assert c_nexus.headless is True and c_gemini.headless is False


def test_cambiar_el_modo_de_nexus_no_cierra_la_ventana_de_gemini(tmp_path):
    nexus, gemini, _ = dos_managers(tmp_path)

    async def escenario():
        visible = await gemini.context()
        await nexus.context(headless=False)
        oculto = await nexus.context(headless=True)
        return visible, oculto

    visible, oculto = asyncio.run(escenario())
    assert visible.cerrado is False and oculto.cerrado is False
    contextos_nexus = [c for c in nexus._pw.lanzados if c.user_data_dir.endswith("browser_profile")]
    assert [c.cerrado for c in contextos_nexus] == [True, False]


def test_los_locks_son_independientes(tmp_path):
    nexus, gemini, _ = dos_managers(tmp_path)
    assert nexus.lock is not gemini.lock

    async def escenario():
        async with nexus.lock, gemini.lock:
            return nexus.lock.locked() and gemini.lock.locked()

    assert asyncio.run(escenario()) is True


def test_el_estado_usa_dos_navegadores_y_gemini_el_suyo(state):
    assert state.browser is not state.browser_gemini
    assert state.browser.profile_dir == state.paths.browser_profile
    assert state.browser_gemini.profile_dir == state.paths.gemini_profile
    assert state.paths.gemini_profile != state.paths.browser_profile
    assert isinstance(state.gemini, GeminiWeb) or state.gemini is not None


def test_el_estado_real_construye_gemini_sobre_su_propio_navegador(tmp_path):
    from backend.services import AppState

    from .conftest import MemoryCredentials

    st = AppState(tmp_path / "data", "x", dev=True, credentials=MemoryCredentials())
    try:
        assert isinstance(st.gemini, GeminiWeb) and st.gemini.browser is st.browser_gemini
    finally:
        st.storage.close()


def test_generar_no_espera_el_lock_de_nexus(listo):  # noqa: F811
    async def escenario():
        async with listo.browser.lock:
            job = listo.jobs.start(
                "generar", lambda ctx: services.run_generar(listo, ctx, TID, None)
            )
            for _ in range(200):
                if job.estado in ("ok", "error"):
                    break
                await asyncio.sleep(0.02)
            return job

    job = asyncio.run(escenario())
    assert job.estado == "ok", job.mensaje


def test_sync_no_espera_el_lock_de_gemini(state, monkeypatch):
    llamado = []

    async def falso(st, ctx, procesar, modo, reanudar, acum):
        llamado.append(modo)
        return 1, 0

    monkeypatch.setattr(services, "_secuencial", falso)

    async def escenario():
        async with state.browser_gemini.lock:
            job = state.jobs.start("sync", lambda ctx: services.run_sync(state, ctx, "completo"))
            for _ in range(200):
                if job.estado in ("ok", "error"):
                    break
                await asyncio.sleep(0.02)
            return job

    job = asyncio.run(escenario())
    assert job.estado == "ok", job.mensaje
    assert llamado == ["completo"]


def test_el_login_de_gemini_usa_el_lock_de_gemini(state):
    class Gemini(FakeGemini):
        async def iniciar_sesion(self, hooks):
            self.dentro = True

    state.gemini = Gemini()

    async def escenario():
        async with state.browser.lock:
            job = state.jobs.start(
                "login_gemini", lambda ctx: services.run_login_gemini(state, ctx)
            )
            for _ in range(200):
                if job.estado in ("ok", "error"):
                    break
                await asyncio.sleep(0.02)
            return job

    assert asyncio.run(escenario()).estado == "ok"


def test_el_respaldo_no_incluye_el_perfil_de_gemini(seeded):
    from backend import respaldo

    (seeded.paths.data / "gemini_profile").mkdir(exist_ok=True)
    (seeded.paths.data / "gemini_profile" / "Cookies").write_text("secreto")
    import zipfile

    nombre = asyncio.run(respaldo.crear(seeded))["nombre"]
    with zipfile.ZipFile(respaldo.carpeta(seeded) / nombre) as zf:
        assert not any(n.startswith("gemini_profile") for n in zf.namelist())
    assert correr is not None
