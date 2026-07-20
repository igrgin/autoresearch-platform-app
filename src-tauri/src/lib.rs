use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::Emitter;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};
use tokio::sync::Mutex;

const PROTOCOL: &str = "battleground.commander/1";

#[derive(Clone, Default)]
struct CommanderManager(Arc<Mutex<Option<CommandChild>>>);

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CommanderRequest {
    id: String,
    op: CommanderOperation,
    #[serde(default)]
    payload: Value,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
enum CommanderOperation {
    Ping,
    Stream,
    Shutdown,
    Crash,
}

#[derive(Clone, Serialize)]
struct LifecycleEvent {
    kind: &'static str,
    detail: String,
}

#[tauri::command]
async fn commander_start(
    app: tauri::AppHandle,
    manager: tauri::State<'_, CommanderManager>,
) -> Result<(), String> {
    let mut child_slot = manager.0.lock().await;
    if child_slot.is_some() {
        return Err("Commander is already running".into());
    }

    let command = app
        .shell()
        .sidecar("battleground-commander")
        .map_err(|error| error.to_string())?
        .args(["serve", "--stdio"]);
    let (mut events, child) = command.spawn().map_err(|error| error.to_string())?;
    *child_slot = Some(child);
    drop(child_slot);

    app.emit(
        "commander-lifecycle",
        LifecycleEvent {
            kind: "started",
            detail: "sidecar spawned; awaiting protocol hello".into(),
        },
    )
    .map_err(|error| error.to_string())?;

    let event_app = app.clone();
    let event_manager = manager.inner().clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes).trim().to_owned();
                    let _ = event_app.emit("commander-frame", line);
                }
                CommandEvent::Stderr(bytes) => {
                    let _ = event_app.emit(
                        "commander-lifecycle",
                        LifecycleEvent {
                            kind: "stderr",
                            detail: String::from_utf8_lossy(&bytes).trim().to_owned(),
                        },
                    );
                }
                CommandEvent::Terminated(payload) => {
                    event_manager.0.lock().await.take();
                    let _ = event_app.emit(
                        "commander-lifecycle",
                        LifecycleEvent {
                            kind: "exited",
                            detail: format!("code={:?}, signal={:?}", payload.code, payload.signal),
                        },
                    );
                }
                CommandEvent::Error(message) => {
                    let _ = event_app.emit(
                        "commander-lifecycle",
                        LifecycleEvent {
                            kind: "stderr",
                            detail: message,
                        },
                    );
                }
                _ => {}
            }
        }
    });

    Ok(())
}

#[tauri::command]
async fn commander_send(
    request: CommanderRequest,
    manager: tauri::State<'_, CommanderManager>,
) -> Result<(), String> {
    let mut child_slot = manager.0.lock().await;
    let child = child_slot
        .as_mut()
        .ok_or_else(|| "Commander is not running".to_string())?;
    let mut encoded = serde_json::to_vec(&json!({
        "protocol": PROTOCOL,
        "id": request.id,
        "op": request.op,
        "payload": request.payload,
    }))
    .map_err(|error| error.to_string())?;
    encoded.push(b'\n');
    child.write(&encoded).map_err(|error| error.to_string())?;
    Ok(())
}

#[tauri::command]
async fn commander_kill(manager: tauri::State<'_, CommanderManager>) -> Result<(), String> {
    let child = manager
        .0
        .lock()
        .await
        .take()
        .ok_or_else(|| "Commander is not running".to_string())?;
    child.kill().map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let manager = CommanderManager::default();
    let cleanup_manager = manager.clone();
    let app = tauri::Builder::default()
        .manage(manager)
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commander_start,
            commander_send,
            commander_kill
        ])
        .build(tauri::generate_context!())
        .expect("error while building the Tauri prototype");

    app.run(move |_app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            if let Ok(mut child_slot) = cleanup_manager.0.try_lock() {
                if let Some(child) = child_slot.take() {
                    let _ = child.kill();
                }
            }
        }
    });
}
