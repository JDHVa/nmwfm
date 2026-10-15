use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::{Manager, RunEvent, State};
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
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![backend_info])
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
