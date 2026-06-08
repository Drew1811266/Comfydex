use serde_json::{json, Value};
use std::{
    env, fs, io,
    path::{Path, PathBuf},
    process::Command,
};
use tauri::{AppHandle, Manager};

const WORKSPACE_FILE: &str = "workspace.txt";
const NO_WORKSPACE: &str = "No workspace selected";

#[tauri::command]
fn app_info() -> Value {
    ok(json!({
        "name": "Comfydex",
        "version": env!("CARGO_PKG_VERSION")
    }))
}

#[tauri::command]
fn set_workspace(app: AppHandle, path: String) -> Value {
    match validate_workspace(&path).and_then(|workspace| {
        save_workspace(&app, &workspace)?;
        Ok(workspace)
    }) {
        Ok(workspace) => run_bridge("project_status", &workspace, json!({})),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn project_status(app: AppHandle) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("project_status", &workspace, json!({})),
        Ok(None) => ok(empty_project_status()),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn reindex_project(app: AppHandle) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("reindex_project", &workspace, json!({ "include_outputs": true })),
        Ok(None) => bridge_error("WorkspaceError", "workspace must be selected before reindexing"),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn get_config(app: AppHandle) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("get_config", &workspace, json!({})),
        Ok(None) => ok(empty_config()),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn set_config(app: AppHandle, payload: Value) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("set_config", &workspace, payload),
        Ok(None) => bridge_error("WorkspaceError", "workspace must be selected before saving settings"),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn check_connection(app: AppHandle) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("check_connection", &workspace, json!({})),
        Ok(None) => ok(empty_connection()),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn list_workflows(app: AppHandle) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("list_workflows", &workspace, json!({})),
        Ok(None) => ok(json!([])),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn list_runs(app: AppHandle) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("list_runs", &workspace, json!({})),
        Ok(None) => ok(json!([])),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn search_assets(app: AppHandle, payload: Value) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("search_assets", &workspace, payload),
        Ok(None) => ok(json!({ "total": 0, "assets": [] })),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn update_asset_metadata(app: AppHandle, payload: Value) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("update_asset_metadata", &workspace, payload),
        Ok(None) => bridge_error("WorkspaceError", "workspace must be selected before updating asset metadata"),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn plan_asset_cleanup(app: AppHandle, payload: Value) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("plan_asset_cleanup", &workspace, payload),
        Ok(None) => bridge_error("WorkspaceError", "workspace must be selected before planning cleanup"),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn export_asset_library_report(app: AppHandle, payload: Value) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("export_asset_library_report", &workspace, payload),
        Ok(None) => bridge_error("WorkspaceError", "workspace must be selected before exporting reports"),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn compare_assets(app: AppHandle, payload: Value) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("compare_assets", &workspace, payload),
        Ok(None) => bridge_error("WorkspaceError", "workspace must be selected before comparing assets"),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn list_batches(app: AppHandle) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("list_batches", &workspace, json!({})),
        Ok(None) => ok(json!([])),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

#[tauri::command]
fn read_batch(app: AppHandle, batch_id: String) -> Value {
    match current_workspace(&app) {
        Ok(Some(workspace)) => run_bridge("read_batch", &workspace, json!({ "batch_id": batch_id })),
        Ok(None) => bridge_error("WorkspaceError", "workspace must be selected before reading batches"),
        Err(message) => bridge_error("WorkspaceError", message),
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            app_info,
            set_workspace,
            project_status,
            reindex_project,
            get_config,
            set_config,
            check_connection,
            list_workflows,
            list_runs,
            search_assets,
            update_asset_metadata,
            plan_asset_cleanup,
            export_asset_library_report,
            compare_assets,
            list_batches,
            read_batch
        ])
        .run(tauri::generate_context!())
        .expect("error while running Comfydex desktop");
}

fn ok(data: Value) -> Value {
    json!({ "ok": true, "data": data })
}

fn bridge_error(error_type: &str, message: impl Into<String>) -> Value {
    json!({
        "ok": false,
        "error": {
            "type": error_type,
            "message": message.into()
        }
    })
}

fn empty_project_status() -> Value {
    json!({
        "workspace": NO_WORKSPACE,
        "database_path": ".comfydex/comfydex.db",
        "schema_version": 2,
        "counts": {
            "workflows": 0,
            "runs": 0,
            "outputs": 0,
            "assets": 0,
            "batches": 0,
            "errors": 0
        },
        "last_reindexed_at": null
    })
}

fn empty_config() -> Value {
    json!({
        "base_url": "http://127.0.0.1:8188",
        "workflows_dir": "workflows",
        "runs_dir": "runs",
        "headers": {},
        "request_timeout_seconds": 30,
        "websocket_timeout_seconds": 600
    })
}

fn empty_connection() -> Value {
    json!({
        "ok": false,
        "base_url": "http://127.0.0.1:8188",
        "message": "Workspace is not selected",
        "checked_at": null
    })
}

fn run_bridge(operation: &str, workspace: &Path, payload: Value) -> Value {
    let payload_json = payload.to_string();
    let workspace_text = workspace.to_string_lossy().to_string();
    let mut command = Command::new(python_executable());
    command
        .args([
            "-m",
            "comfydex_mcp.desktop_bridge",
            operation,
            "--workspace",
            &workspace_text,
            "--payload-json",
            &payload_json,
        ])
        .env("PYTHONPATH", python_path());

    match command.output() {
        Ok(output) if output.status.success() => match serde_json::from_slice::<Value>(&output.stdout) {
            Ok(value) => value,
            Err(error) => bridge_error(
                "BridgeParseError",
                format!("failed to parse bridge JSON: {error}"),
            ),
        },
        Ok(output) => bridge_error(
            "BridgeProcessError",
            String::from_utf8_lossy(&output.stderr).trim().to_string(),
        ),
        Err(error) => bridge_error("BridgeSpawnError", error.to_string()),
    }
}

fn python_executable() -> String {
    env::var("COMFYDEX_PYTHON").unwrap_or_else(|_| "python".to_string())
}

fn python_path() -> std::ffi::OsString {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo_src = manifest_dir
        .parent()
        .and_then(Path::parent)
        .map(|root| root.join("src"));
    let mut paths: Vec<PathBuf> = repo_src.into_iter().collect();

    if let Some(existing) = env::var_os("PYTHONPATH") {
        paths.extend(env::split_paths(&existing));
    }

    env::join_paths(paths).unwrap_or_default()
}

fn validate_workspace(path: &str) -> Result<PathBuf, String> {
    let workspace = PathBuf::from(path)
        .canonicalize()
        .map_err(|error| format!("workspace path cannot be resolved: {error}"))?;

    if !workspace.is_dir() {
        return Err("workspace path must be a directory".to_string());
    }

    Ok(workspace)
}

fn workspace_file(app: &AppHandle) -> Result<PathBuf, String> {
    let config_dir = app
        .path()
        .app_config_dir()
        .map_err(|error| format!("failed to resolve app config dir: {error}"))?;
    fs::create_dir_all(&config_dir)
        .map_err(|error| format!("failed to create app config dir: {error}"))?;
    Ok(config_dir.join(WORKSPACE_FILE))
}

fn save_workspace(app: &AppHandle, workspace: &Path) -> Result<(), String> {
    fs::write(workspace_file(app)?, workspace.to_string_lossy().as_bytes())
        .map_err(|error| format!("failed to save workspace path: {error}"))
}

fn current_workspace(app: &AppHandle) -> Result<Option<PathBuf>, String> {
    let file = workspace_file(app)?;
    match fs::read_to_string(file) {
        Ok(value) => {
            let trimmed = value.trim();
            if trimmed.is_empty() {
                Ok(None)
            } else {
                Ok(Some(PathBuf::from(trimmed)))
            }
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(format!("failed to read workspace path: {error}")),
    }
}
