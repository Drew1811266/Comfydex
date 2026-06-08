# Comfydex Desktop App

Comfydex `0.7.0` adds a Windows-first Tauri desktop app shell under `desktop/`. The desktop app is a local project workbench for browsing Comfydex project state; it does not replace Codex or the Python MCP server.

The app uses a Python desktop bridge:

```powershell
python -m comfydex_mcp.desktop_bridge <operation> --workspace <path> --payload-json "{}"
```

Rust/Tauri stores the selected workspace path in the app config directory, then calls the Python desktop bridge for project data. The Python layer remains responsible for configuration loading, path safety, SQLite indexing, workflow listing, run listing, and asset search.

## Local Setup

Install the Python package and desktop dependencies from the repository root:

```powershell
python -m pip install -e ".[dev]"
npm --prefix desktop install
```

Useful checks:

```powershell
npm --prefix desktop run typecheck
npm --prefix desktop run build
cargo check --manifest-path desktop\src-tauri\Cargo.toml
```

Development server:

```powershell
npm --prefix desktop run dev
```

Tauri command checks use:

```powershell
npm --prefix desktop run tauri -- dev
```

## Workspace Selection

The selected workspace path must be explicit. Until a workspace is selected, the desktop shell renders an empty project state with zero indexed workflows, runs, outputs, assets, batches, and errors.

Project data stays in the workspace:

```text
workflows/
runs/
.comfydex/comfydex.db
```

The desktop app should not write workflow files, run records, outputs, sidecars, or reports outside the selected workspace. Workspace path validation and redirected-path rejection are handled by the Python bridge and shared path safety helpers.

## Dashboard

The Dashboard shows:

- workspace path,
- database path,
- schema version,
- counts for workflows, runs, outputs, assets, batches, and errors,
- last reindex time,
- connection result,
- Reindex action,
- Check connection action.

`project_status` reads the shared project index. `reindex_project` rebuilds index rows from compatibility records and does not delete local workflow files, run records, output files, batch records, sidecars, or reports.

## Workflows

The Workflows view lists local workflow JSON records returned by `list_workflows`.

The `0.7.0` shell shows a table-first browser with a selected workflow detail panel. It does not implement graph editing or visual node rewiring.

## Runs

The Runs view lists execution records returned by `list_runs`.

It shows run id, workflow name, status, output count, updated time, and a selected run summary. Queue submission and batch execution remain MCP/Codex workflows in `0.7.0`.

## Assets

The Assets view calls `search_assets` through the Python desktop bridge. It provides a table-first asset browser with filename, workflow, status, rating, favorite state, tags, search input, and selected asset details.

The full image gallery grid and batch-oriented asset review workflow are planned for later versions.

## Settings

The Settings view shows:

- ComfyUI base URL,
- workflows directory,
- runs directory,
- request timeout,
- WebSocket timeout,
- redacted header count,
- connection check result.

Sensitive header values must stay redacted. The desktop app should not expose login, OAuth, or browser-based account flows.

## Bridge Operations

The desktop shell uses these Python desktop bridge operations:

```text
project_status
reindex_project
get_config
set_config
check_connection
list_workflows
list_runs
search_assets
```

Tauri commands return stable envelopes:

```json
{
  "ok": true,
  "data": {}
}
```

or:

```json
{
  "ok": false,
  "error": {
    "type": "WorkspaceError",
    "message": "workspace must be selected before reindexing"
  }
}
```

## 0.7 non-goals

The `0.7.0` desktop app shell intentionally does not include:

- production installer,
- auto-updater,
- code signing,
- bundled Python runtime,
- full offline packaging,
- full gallery grid interactions,
- batch task management UI,
- ComfyUI workflow graph editing,
- running ComfyUI itself,
- replacing Codex as the intelligent workflow and debugging layer.
