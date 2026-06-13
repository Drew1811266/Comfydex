# Comfydex Desktop App

Comfydex `2.0.0` provides a Windows-first Tauri desktop app shell under `desktop/`. The desktop app is a local project workbench for browsing Comfydex project state, plain output summaries, asset gallery records, reports, cleanup plans, comparisons, batch records, generated UI workflow history, Generated Graphs, run repair plans, Live Bridge readiness, and the 2.0 Readiness Gate; it does not replace Codex or the Python MCP server.

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
- compact Live Bridge readiness.

`project_status` reads the shared project index. `reindex_project` rebuilds index rows from compatibility records and does not delete local workflow files, run records, output files, batch records, sidecars, or reports.

## Live Bridge Status

The Dashboard shows a compact Live Bridge status band beside the ComfyUI connection band. The Settings view shows the expanded Live Bridge panel with diagnostics, timestamps, bridge version, frontend client id, and controls.

Status terms:

- Ready: ComfyUI reachable, backend route loaded, frontend extension listed, frontend connected.
- Restart required: ComfyUI reachable but bridge status route is missing.
- Refresh required: backend route loaded but frontend client has not heartbeated or is stale.
- Unsaved canvas: frontend refused a push because the current workflow has unsaved changes.

Controls:

- Verify refreshes the Live Bridge status from the Python desktop bridge.
- Reload client asks the ComfyUI frontend extension to reload the browser-side Live Bridge client.
- Reload backend asks the ComfyUI-side bridge route to reload backend runtime code.

Use Restart required when ComfyUI must be restarted after first installing the custom node. Use Refresh required when the backend is loaded but the ComfyUI browser tab has not loaded or recently heartbeated the frontend extension.

## Workflows

The Workflows view lists local workflow JSON records returned by `list_workflows`.

The `0.7.0` shell shows a table-first browser with a selected workflow detail panel. It does not implement graph editing or visual node rewiring.

## Runs

The Runs view lists execution records returned by `list_runs`.

It shows run id, workflow name, status, output count, updated time, and a selected run summary. Queue submission and batch execution remain MCP/Codex workflows in `0.7.0`.

Comfydex `1.8.0` adds ordinary-user summaries on top of the existing Project, Generated, Runs, and Assets views. The Project view displays the current output library summary, Generated shows preset groups and canvas replacement summaries, Runs can display plain repair guidance when present, and Assets shows output and comparison summaries while keeping the technical rows and JSON available.

Comfydex `2.0.0` shows the Settings 2.0 Readiness Gate panel. It reads `twenty_readiness_report` from the Python desktop bridge and shows first-class scenario coverage, ready counts, remaining gaps, acceptance criteria, and next steps.

Comfydex `1.7.0` added the Runs repair panel. Select a run, use Plan repair to call `plan_run_repair`, inspect the failure class, repair summary, repair actions, retry state, and recent repair history, then use the retry action when the returned plan supports it.

The retry path calls `retry_run_repair`. Fetch-output repairs can run without confirmation; resubmit repairs first return `requires_confirmation` and require a second explicit confirm action. Repair history comes from `read_repair_history`.

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

## Generated Graphs

The Generated Graphs view reads generated UI workflow history from `.comfydex/ui_graph_history.jsonl` through `read_ui_graph_history`.

The generated graph list shows:

- workflow name,
- status,
- template id,
- recipe id,
- node count,
- timestamp.

The selected graph panel shows graph metadata, path, link count, and push result when present. Use Push to call `push_ui_workflow` through the Python desktop bridge. The push path loads a generated UI workflow from local workflow storage and sends it to Live Bridge.

Generated Graphs is an action and history surface for UI Graph Builder output. It does not implement node dragging, graph rewiring, automatic model downloads, or automatic custom node installation.

## Settings

The Settings view shows:

- ComfyUI base URL,
- workflows directory,
- runs directory,
- request timeout,
- WebSocket timeout,
- redacted header count,
- connection check result.
- Live Bridge status,
- Live Bridge diagnostics,
- Reload client action,
- Reload backend action,
- 2.0 Readiness Gate scenario coverage and acceptance criteria.

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
plan_run_repair
retry_run_repair
read_repair_history
search_assets
update_asset_metadata
plan_asset_cleanup
export_asset_library_report
compare_assets
list_batches
read_batch
live_bridge_status
live_bridge_reload_client
live_bridge_reload_backend
build_ui_workflow
generate_ui_workflow
read_ui_graph_history
push_ui_workflow
twenty_readiness_report
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
- full visual generated graph editor,
- ComfyUI workflow graph editing,
- running ComfyUI itself,
- replacing Codex as the intelligent workflow and debugging layer.
