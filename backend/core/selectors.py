"""Selectores centralizados. Los de SIASE/NEXUS salen de htmls/; los de GEMINI son suposiciones."""

SIASE_TIPO_SELECT = "#tipo"
SIASE_TIPO_ALUMNO = "01"
SIASE_CUENTA = "#cuenta"
SIASE_PASSWORD = "#pass"
SIASE_ENTRAR = "form[name='inicio'] button[type='submit']"
# VALIDAR en vivo: texto de error tipico de SIASE ante credenciales invalidas
SIASE_ERROR_LOGIN = (
    "text=/contraseña incorrecta|usuario o contraseña|datos incorrectos|no es válid/i"
)
SIASE_NEXUS_LOGO = "a[onmouseover*=\"muestra('nexus')\"]"
SIASE_MOSTRAR_NEXUS_JS = "muestra('nexus')"
SIASE_NEXUS_LINK = "#linkNexus"
SIASE_CARRERA_LINK = "form[name='SelCarrera'] a"
SIASE_MENU_EVALUACION = "a[href*='econeva01']"
SIASE_PERIODO_SELECT = "select[name='HTMLPeriodo']"
SIASE_PERIODO_SIN_ELEGIR = "0"
SIASE_EVAL_ACEPTAR = "input[type='button'][value='Aceptar']"
SIASE_EVAL_TABLA = r"text=/Total\s+Puntos/i"
SIASE_EVAL_FILAS = "tr"
SIASE_EVAL_COLUMNAS = {
    "PAR 1": "par1",
    "PAR 2": "par2",
    "PORT": "portafolio",
    "EMT": "emt",
    "EG": "eg",
}

NX_CARDS_ROOT = "app-cursos-card"
NX_CARD = "app-cursos-card mat-card.nx-mat-card-curso"
NX_CARD_CLICK = "a.color-2"
NX_CARD_NAME = "mat-card-content .text-ellipsis"
NX_CARD_ID_BUTTON = "button[id^='btnColor']"

NX_MENU_OPTION = "mat-nav-list a.menu-option"
NX_MENU_LABEL = ".label"
NX_MENU_ESTRUCTURA = "Estructura"
NX_PORTADA = "app-curso-portada"
NX_PORTADA_ROWS = "app-curso-portada table tr"
NX_ICON_PROFESOR = "fa-user-tie"
NX_ICON_PERIODO = "fa-calendar"
NX_ICON_MODALIDAD = "fa-users-class"

NX_ESTRUCTURA = "app-estructura-competencias"
NX_PANEL = "app-estructura-competencias mat-expansion-panel"
NX_PANEL_TITLE = "mat-expansion-panel-header span.bold-500"
NX_PANEL_DESC = "mat-expansion-panel-header .color-3 div"
NX_PANEL_ITEM = "mat-list-item"
NX_PANEL_ITEM_LINK = "mat-list-item a"
NX_ITEM_LABEL_DIV = "a div"
NX_ITEM_POINTS_BOX = "div.absolute"
NX_ITEM_MODALITY_ICON = "i[mattooltip]"

NX_DETALLE_ROOT = "app-estructura-elemento-contenido"
NX_DETALLE_HEADER = "div.mb-4"
NX_DETALLE_TITLE = "div.bold-500.font-size-20"
NX_DETALLE_ICON_FECHA = "fa-calendar"
NX_DETALLE_ICON_PUNTOS = "fa-trophy"
NX_DETALLE_ICON_MODALIDAD = ("fa-user", "fa-users")
NX_DETALLE_CARD = "mat-card"
NX_DETALLE_CARD_TITLE = "mat-card-title"
NX_DETALLE_CARD_BODY = "mat-card-content .fr-view"
NX_SECCION_ACTIVIDADES = "actividades de aprendizaje"
NX_SECCION_CONTENIDO = "contenido"
NX_SECCION_CRITERIOS = "criterios de desempeno"
NX_ENTREGAR_BUTTON = "button.mat-raised-button.mat-primary"
NX_ENTREGAR_TEXT = "Entregar"
NX_ENTREGA_TABS = "mat-tab-group"
NX_ENTREGA_TAB = ".mat-tab-label"
NX_ENTREGA_TAB_ACTIVA = ".mat-tab-label.mat-tab-label-active"
NX_ENTREGA_TAB_PC = "PC"
NX_ENTREGA_UPLOAD = "app-file-upload"
NX_ENTREGA_INPUT = "app-file-upload input[type='file']"
NX_ENTREGA_DROPZONE = "#dropZone"
NX_ENTREGA_DIALOG = "mat-dialog-container, .cdk-overlay-pane"
NX_ENTREGA_CONFIRMAR = "button.mat-raised-button.mat-primary:not([disabled])"
NX_ENTREGA_CONFIRMAR_FALLBACK = (
    "xpath=//app-file-upload/following::button[contains(@class,'mat-raised-button')]"
    "[contains(@class,'mat-primary')][not(@disabled)]"
)
NX_ENTREGA_CERRAR = (
    "button[mat-dialog-close], button[aria-label='Close'], button[aria-label='Cerrar']"
)
NX_OVERLAY_BACKDROP = ".cdk-overlay-backdrop"
NX_SNACKBAR = "snack-bar-container"
NX_SNACKBAR_TEXT = "simple-snack-bar > span"
NX_SNACKBAR_CLOSE = "snack-bar-container button"
NX_SNACKBAR_EXITO_CLASS = "snackbar-success"
NX_SNACKBAR_EXITO_TEXT = "entregada con exito"

NX_CONTENIDO_MATERIA = "app-curso mat-sidenav-content"
NX_DETALLE_ENCABEZADO = ".bold-500.font-size-20"
NX_DETALLE_CARDS = "app-estructura-elemento-contenido mat-card"
NX_RUBRICA_CRITERIO = "table.nx-table-rubrica div.puntos"
NX_TAB_ACTIVA = "nav.mat-tab-nav-bar a.mat-tab-link.mat-tab-label-active"
NX_ENCABEZADO_MATERIA = "h5 span.ml-2"
NX_CARD_NOMBRES = "app-cursos-card mat-card.nx-mat-card-curso mat-card-content .text-ellipsis"
NX_PANEL_HEADER = "mat-expansion-panel-header"
NX_LOADER = "mat-spinner, mat-progress-spinner, mat-progress-bar"
NX_TAB_ENTREGAS_CSS = (
    "nav.mat-tab-nav-bar a.mat-tab-link[routerlink='Entregas'], "
    "nav.mat-tab-nav-bar a.mat-tab-link[ng-reflect-router-link='Entregas']"
)
NX_TAB_ENTREGAS_TEXT = "Entregas"
NX_ENTREGAS_TABLA = "table.mat-table"
NX_ENTREGAS_FILA = "tr.mat-row"
NX_ENTREGAS_NOMBRE = "td.cdk-column-nombre"
NX_ENTREGAS_FECHA = "td.cdk-column-fecha"
NX_ENTREGAS_VACIO = "text=/No se encontraron Entregas/i"
# VALIDAR en vivo: aviso de NEXUS cuando la sesion se cierra en otra ventana
NX_SESION_CERRADA = "text=/sesi[oó]n.{0,20}(cerrada|expir)/i"
NX_PALABRAS_EXAMEN = ("examen", "diagnostic", "cuestionario en linea")
NX_ETAPA_PIA = "producto integrador"
NX_MENU_CALIFICACIONES = "Calificaciones"
NX_CALIFICACIONES_TABLA = "app-curso mat-sidenav-content table"
NX_RUTA_PIA = "/ProductoIntegrador/"
NX_PALABRA_OCULTA = "autoevaluacion"

NX_TABS = "nav.mat-tab-nav-bar .mat-tab-links a.mat-tab-link"
NX_TAB_RUBRICA_CSS = (
    "nav.mat-tab-nav-bar a.mat-tab-link[routerlink='Rubrica'], "
    "nav.mat-tab-nav-bar a.mat-tab-link[ng-reflect-router-link='Rubrica']"
)
NX_TAB_CONTENIDOS_CSS = (
    "nav.mat-tab-nav-bar a.mat-tab-link[routerlink='Contenidos'], "
    "nav.mat-tab-nav-bar a.mat-tab-link[ng-reflect-router-link='Contenidos']"
)
NX_TAB_RUBRICA_TEXT = "Rúbrica"
NX_TAB_CONTENIDOS_TEXT = "Contenidos"
NX_RUBRICA = "table.nx-table-rubrica"
NX_RUBRICA_ROWS = "tr"
NX_RUBRICA_PUNTOS = "div.puntos"
NX_RUBRICA_DESC = "div.desc"

# --- NEXUS: navegacion (VALIDAR en vivo) ---
NX_LISTA_LINK = "a[href='#/App/UnidadesAprendizaje']"

# --- GEMINI (editor, envío y carga validados en vivo el 2026-10-15; el DOM cambia seguido) ---
GM_EDITOR = (
    "rich-textarea div.ql-editor[contenteditable='true'], "
    "div[contenteditable='true'][role='textbox']"
)
GM_UPLOAD_MENU_BUTTON = (
    "button[aria-label='Subidas y herramientas'], "
    "button[aria-label*='Abrir menú de carga'],button[aria-label*='Subir archivo'], "
    "button[aria-label*='Upload'], button.upload-card-button"
)
GM_UPLOAD_MENU_ITEM = (
    "button[data-test-id='local-images-files-uploader-button'], "
    "button[role='menuitem']:has-text('Subir archivos'), "
    "button[role='menuitem']:has-text('Upload files')"
)
GM_FILE_INPUT = "input[type='file']"
GM_ATTACHMENT_CHIP = "uploader-file-preview, .file-preview-container, [data-test-id='file-preview']"
GM_SEND_BUTTON = "button[aria-label*='Enviar mensaje'], button[aria-label*='Send message']"
GM_STOP_BUTTON = "button[aria-label*='Detener'], button[aria-label*='Stop response']"
GM_RESPONSE = "model-response message-content, .model-response-text"
GM_COPY_BUTTON = "button[aria-label*='Copiar'], button[aria-label*='Copy']"
GM_MORE_BUTTON = (
    "button[aria-label*='Mostrar más opciones'], button[aria-label*='Show more options']"
)
GM_SIGNED_IN_MARKER = (
    "a[href*='accounts.google.com/SignOutOptions'], a[aria-label*='Cuenta de Google'], "
    "a[aria-label*='Google Account']"
)
GM_SIGN_IN_LINK = "a[href*='accounts.google.com/ServiceLogin'], a:has-text('Iniciar sesión')"
GM_BLOCK_MARKERS = (
    "iframe[src*='recaptcha']",
    "text=/tráfico inusual|unusual traffic/i",
    "text=/verifica que eres|verify it'?s you/i",
)
