use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WindowEvent};
use tokio::sync::watch;

#[derive(Clone, Debug, Serialize, Deserialize)]
struct BackendInfo {
    port: u16,
    token: String,
}

struct BackendState {
    info: watch::Receiver<Option<BackendInfo>>,
    child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

struct Preferencias {
    cerrar_a_bandeja: AtomicBool,
}

#[tauri::command]
fn set_cerrar_a_bandeja(valor: bool, estado: State<'_, Preferencias>) {
    estado.cerrar_a_bandeja.store(valor, Ordering::SeqCst);
}

fn mostrar_ventana(app: &AppHandle) {
    if let Some(ventana) = app.get_webview_window("main") {
        let _ = ventana.show();
        let _ = ventana.unminimize();
        let _ = ventana.set_focus();
    }
}

fn crear_bandeja(app: &AppHandle) -> tauri::Result<()> {
    let abrir = MenuItem::with_id(app, "abrir", "Abrir", true, None::<&str>)?;
    let sincronizar = MenuItem::with_id(app, "sync", "Sincronizar ahora", true, None::<&str>)?;
    let salir = MenuItem::with_id(app, "salir", "Salir", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&abrir, &sincronizar, &salir])?;

    let mut bandeja = TrayIconBuilder::new()
        .tooltip("nmwfm")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, evento| match evento.id.as_ref() {
            "abrir" => mostrar_ventana(app),
            "sync" => {
                let _ = app.emit("tray-sync", ());
            }
            "salir" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|bandeja, evento| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = evento
            {
                mostrar_ventana(bandeja.app_handle());
            }
        });
    if let Some(icono) = app.default_window_icon() {
        bandeja = bandeja.icon(icono.clone());
    }
    bandeja.build(app)?;
    Ok(())
}

#[tauri::command]
async fn backend_info(state: State<'_, BackendState>) -> Result<BackendInfo, String> {
    let mut rx = state.info.clone();
    let esperado = tokio::time::timeout(Duration::from_secs(90), rx.wait_for(|v| v.is_some())).await;
    match esperado {
        Ok(Ok(valor)) => valor.clone().ok_or_else(|| "Servicio local no disponible".to_string()),
        _ => Err("El servicio local no respondió a tiempo".to_string()),
    }
}

#[cfg(not(debug_assertions))]
fn lanzar_backend(
    app: &tauri::AppHandle,
    tx: watch::Sender<Option<BackendInfo>>,
) -> Result<tauri_plugin_shell::process::CommandChild, Box<dyn std::error::Error>> {
    use tauri_plugin_shell::process::CommandEvent;
    use tauri_plugin_shell::ShellExt;

    let (mut rx, child) = app.shell().sidecar("nmwfm-backend")?.spawn()?;
    tauri::async_runtime::spawn(async move {
        while let Some(evento) = rx.recv().await {
            if let CommandEvent::Stdout(linea) = evento {
                let texto = String::from_utf8_lossy(&linea);
                if let Some(json) = texto.trim().strip_prefix("NMWFM_READY ") {
                    if let Ok(info) = serde_json::from_str::<BackendInfo>(json) {
                        let _ = tx.send(Some(info));
                    }
                }
            }
        }
    });
    Ok(child)
}

pub fn run() {
    let (tx, rx) = watch::channel::<Option<BackendInfo>>(None);

    let app = tauri::Builder::default()
        .manage(Preferencias {
            cerrar_a_bandeja: AtomicBool::new(true),
        })
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![backend_info, set_cerrar_a_bandeja])
        .on_window_event(|ventana, evento| {
            if let WindowEvent::CloseRequested { api, .. } = evento {
                let preferencias = ventana.app_handle().state::<Preferencias>();
                if preferencias.cerrar_a_bandeja.load(Ordering::SeqCst) {
                    api.prevent_close();
                    let _ = ventana.hide();
                }
            }
        })
        .setup(move |app| {
            #[cfg(debug_assertions)]
            let child = {
                let _ = tx.send(Some(BackendInfo {
                    port: 8765,
                    token: "dev".to_string(),
                }));
                None
            };

            #[cfg(not(debug_assertions))]
            let child = Some(lanzar_backend(app.handle(), tx)?);

            crear_bandeja(app.handle())?;

            app.manage(BackendState {
                info: rx,
                child: Mutex::new(child),
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error al construir la aplicación");

    app.run(|handle, evento| {
        if let RunEvent::Exit = evento {
            if let Some(estado) = handle.try_state::<BackendState>() {
                if let Some(hijo) = estado.child.lock().ok().and_then(|mut g| g.take()) {
                    let _ = hijo.kill();
                }
            }
        }
    });
}
