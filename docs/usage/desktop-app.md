# Comfydex Desktop App

Comfydex `0.8.0` provides a Windows-first Tauri desktop app shell under `desktop/`. The desktop app is a local project workbench for browsing Comfydex project state, asset gallery records, reports, cleanup plans, comparisons, and batch records; it does not replace Codex or the Python MCP server.

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

`0.8.0` adds Gallery and Table modes. Gallery mode shows compact output tiles; Table mode keeps the dense sortable workbench shape from `0.7.0`.

The selected asset panel includes:

- Favorite toggle,
- Rating input,
- Tags input,
- Notes input,
- workflow, prompt, and path details.

### Compare

Use the Compare panel to select exactly two assets and call `compare_assets`. The desktop UI shows changed indexed fields while keeping the Python bridge responsible for comparison logic.

### Cleanup

Cleanup is dry-run by default. Use Dry run to call `plan_asset_cleanup` without deleting files. Use Confirm cleanup only after checking candidates and enabling the explicit confirmation checkbox.

The UI never constructs delete paths itself. Confirmed cleanup still goes through the shared safe cleanup planner.

### Generate report

Use Generate report to call `export_asset_library_report` for the current filters. The report panel shows the generated markdown path and a preview of the report text.

## Batches

The Batches view lists batch task view records from `runs/.batches`.

The batch list shows:

- batch id or label,
- workflow name,
- status,
- completed count,
- failed count,
- updated timestamp.

The Batch detail panel shows the selected batch status, workflow, created time, and updated time.

The Child runs table shows each child run index, status, run id, and error. The Variation parameters preview shows the per-run parameter payloads used by the batch record.

Batch submission remains an MCP/Codex operation in `0.8.0`; the desktop UI reads and inspects existing batch records.

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
update_asset_metadata
plan_asset_cleanup
export_asset_library_report
compare_assets
list_batches
read_batch
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

The `0.8.0` desktop app shell intentionally does not include:

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
