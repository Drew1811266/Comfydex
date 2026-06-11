# Comfydex

Comfydex is a Codex plugin that connects Codex to ComfyUI. It gives Codex both the operational tools and the workflow knowledge needed to inspect, manage, submit, monitor, and collect ComfyUI workflow runs.

The plugin is installed in Codex, not in ComfyUI. ComfyUI remains the runtime server, and Comfydex talks to it through the ComfyUI HTTP and WebSocket APIs.

## Status

Current version: `1.2.0`

This 1.2 Live Bridge Productization Release focuses on a practical local ComfyUI workflow:

- connect to a local or remote ComfyUI server
- manage workflow JSON files from a Codex workspace
- maintain a workspace-local project index at `.comfydex/comfydex.db`
- search, annotate, report, compare, and safely clean up generated assets
- browse project status, workflows, runs, assets, and settings in a Windows-first Tauri desktop app shell
- use Gallery And Batch UI surfaces for asset gallery review, comparison, reports, safe cleanup UI, and batch task view inspection
- run safe one-call generate-run-fetch automation for low-risk single-run requests
- build generated workflows from deterministic generation plans
- validate generated workflows and classify submit policy before running
- analyze workflow nodes, links, model references, and missing node types
- import UI workflow JSON and convert it toward API prompt JSON
- build first-pass workflows from templates and structured plans
- scaffold, inspect, validate, import-check, document, contract-test, and repair-guide custom node packages
- submit API prompt JSON to ComfyUI
- watch execution through WebSocket events
- fall back to HTTP queue/history polling when WebSocket waiting fails
- install a ComfyUI-side Live Bridge that can push workflows directly into the desktop canvas after one bootstrap restart
- verify Live Bridge readiness from Codex scripts, MCP tools, and the desktop Settings view
- use desktop Reload client and Reload backend controls when the bridge can be refreshed without a full reinstall
- persist local run records
- diagnose runs, export run reports, compare experiments, and manage outputs
- submit simple batch runs with parameter variations
- fetch or register generated outputs
- validate release package metadata before tagging
- install and verify the local toolchain with `scripts/install_windows.ps1`
- provide Codex Skills that teach Codex workflow and custom node procedures

## Why This Exists

ComfyUI is powerful because it exposes low-level graph workflows, custom nodes, model references, and runtime APIs. That flexibility also means workflow development can become hard to inspect and automate manually.

Codex is strong at reading code, editing structured files, following tool workflows, and debugging. Comfydex bridges these strengths by giving Codex a ComfyUI-aware control layer:

- Codex can understand workflow JSON instead of treating it as opaque data.
- Codex can call ComfyUI routes directly through MCP tools.
- Codex can keep run records tied to the workflow and output files that produced them.
- Developers can iterate on ComfyUI workflows from a project workspace instead of relying only on manual UI interaction.

## Project Structure

```text
.
├── .codex-plugin/
│   └── plugin.json              # Codex plugin manifest
├── .mcp.json                    # MCP server launch config
├── desktop/                     # Tauri v2 + Vite + React desktop app shell
├── custom_nodes/                # Optional ComfyUI-side Live Bridge bootstrap
├── docs/
│   ├── release/                 # Install, release, and safety review docs
│   └── usage/                   # Usage guides
├── examples/                    # Workflow, report, and custom node examples
├── skills/
│   ├── comfyui-custom-nodes/
│   │   └── SKILL.md             # Codex custom node guidance
│   └── comfyui-workflows/
│       └── SKILL.md             # Codex workflow guidance
├── scripts/
│   ├── install_windows.ps1      # Windows local install helper
│   ├── install_live_bridge.ps1  # Install the ComfyUI Live Bridge custom node
│   ├── live_bridge.ps1          # Local bridge status, reload, and push helper
│   ├── smoke_check.py           # Manual ComfyUI connection check
│   ├── verify_live_bridge.ps1   # Post-restart Live Bridge verification
│   └── validate_release_package.py # Release package consistency check
├── src/
│   └── comfydex_mcp/
│       ├── analyzer.py          # Workflow graph and node analysis
│       ├── batches.py           # Batch record and variation helpers
│       ├── builder.py           # Workflow builder planning and assembly
│       ├── comfy_client.py      # ComfyUI HTTP client
│       ├── config.py            # Workspace config loading and redaction
│       ├── conversion.py        # UI workflow import and API conversion
│       ├── core/                # Shared project context, SQLite index, and migrations
│       ├── diagnostics.py       # Run diagnosis and comparison
│       ├── desktop_bridge.py    # JSON CLI bridge used by the desktop app
│       ├── node_contracts.py    # Custom node examples, contracts, and repair guidance
│       ├── outputs.py           # Output listing and cleanup
│       ├── paths.py             # Path safety helpers
│       ├── reports.py           # Markdown run reports
│       ├── runs.py              # Run record persistence
│       ├── server.py            # FastMCP tool server
│       ├── templates.py         # Workflow templates and suggestions
│       ├── workflows.py         # Workflow storage and summaries
│       └── ws.py                # WebSocket waiting helpers
└── tests/                       # Unit and integration-style tests
```

## Runtime Model

Comfydex has four layers.

### Codex Plugin

The plugin manifest declares the plugin metadata, Skill directory, and MCP server configuration so Codex can discover and load Comfydex.

### Python MCP Server

The MCP server exposes `comfy_*` tools to Codex. These tools manage configuration, workflow files, ComfyUI API calls, WebSocket waiting, run records, and output downloads.

### Tauri Desktop App

The `desktop/` app is a Windows-first Tauri shell for local project browsing. It stores only the selected workspace path in the Tauri app config directory, then calls the Python desktop bridge for shared project operations such as `project_status`, `list_workflows`, `list_runs`, and `search_assets`.

### ComfyUI Workflow Skill

The Skill explains how Codex should work with ComfyUI workflows, including the difference between:

- UI workflow JSON, exported for the ComfyUI visual editor
- API prompt JSON, submitted to ComfyUI `/prompt`

Version `1.2.0` can import UI workflow files and help convert them, but submission still requires validated API prompt JSON. It also provides the shared project index, workflow generation engine, complete custom node loop, local asset library for generated outputs, desktop app shell backed by a Python desktop bridge with Gallery And Batch UI surfaces, safe end-to-end automation, Windows install helper, release checklist, security/path review, release package validation, and a productized ComfyUI-side Live Bridge for direct desktop canvas workflow loading.

## Capability Groups

| Group | What it adds | Primary tools |
| --- | --- | --- |
| Workflow generation | Plan, generate, validate, repair, and classify submit policy for generated API workflows. | `comfy_plan_workflow_generation`, `comfy_generate_workflow`, `comfy_evaluate_submit_policy` |
| End-to-end automation | Generate, save, submit, wait, fetch outputs, and reindex for low-risk single-run requests. | `comfy_generate_run_fetch` |
| Project index | Build and inspect a local SQLite index for workflows, runs, outputs, batches, and index errors. | `comfy_project_status`, `comfy_reindex_project` |
| Asset library | Reindex, search, annotate, sidecar, clean up, report, and compare generated output assets. | `comfy_reindex_assets`, `comfy_search_assets`, `comfy_update_asset_metadata`, `comfy_plan_asset_cleanup` |
| UI workflow import | Classify, import, convert, and explain UI workflow conversion gaps. | `comfy_classify_workflow`, `comfy_import_ui_workflow`, `comfy_convert_ui_to_api` |
| Workflow builder | Plan and build template-based API workflows from user intent. | `comfy_build_workflow_plan`, `comfy_explain_workflow_plan`, `comfy_build_workflow` |
| Validation | Validate API workflows and generated workflows against object metadata. | `comfy_validate_api_workflow`, `comfy_validate_workflow_against_object_info` |
| Custom node assistant | Scaffold, inspect, validate, import-check, document, generate examples, run contract tests, and produce repair guidance. | `comfy_scaffold_custom_node_package`, `comfy_validate_node_class`, `comfy_check_node_imports`, `comfy_generate_node_examples`, `comfy_run_node_contract_tests`, `comfy_custom_node_repair_guidance` |
| Run diagnostics | Diagnose, report, compare, and inspect run outputs. | `comfy_diagnose_run`, `comfy_export_run_report`, `comfy_compare_runs`, `comfy_list_outputs` |
| Batch runs | Submit parameter variations and read batch records. | `comfy_batch_submit`, `comfy_read_batch` |
| Desktop shell | Browse project status, workflows, runs, assets, Gallery And Batch UI, reports, comparisons, cleanup plans, and settings through the local Tauri app. | `desktop/`, Python desktop bridge |
| Live Bridge | Install, verify, reload, and push UI workflow JSON into the ComfyUI desktop canvas after the initial custom node bootstrap is loaded. | `scripts/install_live_bridge.ps1`, `scripts/verify_live_bridge.ps1`, `comfy_live_bridge_status`, `comfy_live_bridge_push_workflow` |

## Configuration

Comfydex resolves configuration from the active Codex workspace. If no config file exists, it uses these defaults:

```json
{
  "base_url": "http://127.0.0.1:8188",
  "workflows_dir": "./workflows",
  "runs_dir": "./runs",
  "headers": {},
  "request_timeout_seconds": 30,
  "websocket_timeout_seconds": 600
}
```

The config file name is:

```text
comfydex.config.json
```

Remote ComfyUI deployments can be configured by setting `base_url` and optional request headers:

```json
{
  "base_url": "https://comfy.example.com",
  "headers": {
    "Authorization": "Bearer example-token"
  }
}
```

Header values are redacted when configuration is returned through the MCP tools.

## MCP Tools

Comfydex exposes these tools:

| Tool | Purpose |
| --- | --- |
| `comfy_check_connection` | Check whether the configured ComfyUI server is reachable. |
| `comfy_get_config` | Return the active config with sensitive header values redacted. |
| `comfy_set_config` | Update base URL, directories, headers, and timeout settings. |
| `comfy_project_status` | Inspect workspace paths, database path, schema version, index counts, and index errors. |
| `comfy_reindex_project` | Rebuild the project index from local compatibility records. |
| `comfy_reindex_assets` | Reindex project assets and optionally write sidecar metadata. |
| `comfy_search_assets` | Search assets by text, workflow, status, type, tags, favorite, rating, and pagination. |
| `comfy_update_asset_metadata` | Update asset tags, rating, favorite state, and notes. |
| `comfy_write_asset_sidecars` | Write deterministic sidecar JSON metadata for assets. |
| `comfy_plan_asset_cleanup` | Dry-run or confirmed cleanup for selected or search-matched assets. |
| `comfy_export_asset_library_report` | Write a deterministic markdown asset library report. |
| `comfy_compare_assets` | Compare two assets by metadata, prompts, models, file size, and annotations. |
| `comfy_get_object_info` | Read ComfyUI `/object_info` node metadata. |
| `comfy_list_workflows` | List local workflow JSON files. |
| `comfy_read_workflow` | Read and summarize one workflow. |
| `comfy_save_workflow` | Save a workflow JSON file safely under the configured workflow directory. |
| `comfy_analyze_workflow` | Analyze node types, links, missing nodes, model references, and output nodes. |
| `comfy_submit_workflow` | Submit API prompt JSON to ComfyUI `/prompt` and create a run record. |
| `comfy_wait_for_run` | Wait for a run through WebSocket events, with HTTP polling fallback. |
| `comfy_get_queue` | Read ComfyUI `/queue`. |
| `comfy_get_history` | Read ComfyUI `/history` or `/history/{prompt_id}`. |
| `comfy_list_runs` | List local run records. |
| `comfy_read_run` | Read one run record. |
| `comfy_fetch_outputs` | Fetch or register outputs for a run using ComfyUI history and `/view`. |
| `comfy_classify_workflow` | Identify UI, API, or unknown workflow JSON. |
| `comfy_import_ui_workflow` | Store a UI workflow export and metadata. |
| `comfy_convert_ui_to_api` | Convert UI workflow JSON toward API prompt JSON. |
| `comfy_explain_conversion_gaps` | Explain unresolved conversion gaps. |
| `comfy_validate_api_workflow` | Validate API prompt shape before submission. |
| `comfy_validate_workflow_against_object_info` | Validate node classes and required inputs with object metadata. |
| `comfy_list_workflow_templates` | List built-in workflow templates. |
| `comfy_suggest_workflow_template` | Suggest a template for user intent. |
| `comfy_build_workflow_plan` | Create a structured workflow build plan. |
| `comfy_explain_workflow_plan` | Explain required inputs and assumptions in a build plan. |
| `comfy_build_workflow` | Build and save a workflow from a plan. |
| `comfy_plan_workflow_generation` | Create a scored generation plan from intent, parameters, template choice, and constraints. |
| `comfy_generate_workflow` | Build, validate, repair, and save a generated workflow when submit policy allows. |
| `comfy_generate_run_fetch` | Generate, save, submit, wait, fetch outputs, and reindex for low-risk single-run requests. |
| `comfy_evaluate_submit_policy` | Evaluate whether an existing workflow is allowed, requires confirmation, or is blocked. |
| `comfy_scaffold_custom_node_package` | Create a workspace-local custom node package. |
| `comfy_inspect_custom_node_package` | Inspect custom node package files and mappings. |
| `comfy_validate_node_mappings` | Validate custom node mapping dictionaries. |
| `comfy_validate_node_class` | Validate custom node class contracts. |
| `comfy_check_node_imports` | Import-check a custom node package in isolation. |
| `comfy_generate_node_examples` | Generate deterministic example inputs for scalar and enum node inputs. |
| `comfy_run_node_contract_tests` | Import and execute a mapped node class in an isolated subprocess and verify tuple returns. |
| `comfy_custom_node_repair_guidance` | Aggregate mapping, class, import, and contract readiness guidance for a package. |
| `comfy_generate_node_docs` | Generate deterministic node package documentation. |
| `comfy_diagnose_run` | Produce structured run diagnostics and a short summary. |
| `comfy_export_run_report` | Write `runs/<run_id>/report.md`. |
| `comfy_compare_runs` | Compare two runs by status, output count, node inputs, and model references. |
| `comfy_list_outputs` | List output files across valid run directories. |
| `comfy_cleanup_outputs` | Dry-run or confirmed cleanup for selected outputs. |
| `comfy_batch_submit` | Submit workflow parameter variations and record child runs. |
| `comfy_read_batch` | Read a stored batch record. |

## Typical Workflow

1. Check the ComfyUI connection.
2. Read available node metadata.
3. List and read workflow files.
4. Analyze a workflow for node classes, links, models, and output nodes.
5. Submit the workflow.
6. Wait for the run to complete.
7. Fetch generated outputs.
8. Read the final run record.

In Codex, this usually maps to:

```text
comfy_check_connection
comfy_get_object_info
comfy_list_workflows
comfy_read_workflow
comfy_analyze_workflow
comfy_submit_workflow
comfy_wait_for_run
comfy_fetch_outputs
comfy_read_run
```

For low-risk generated workflows, `comfy_generate_run_fetch` can combine generation, submission, waiting, output fetching, and reindexing in one call. It stops before saving or submitting when `policy.decision` is `requires_confirmation` unless `confirm_risky_actions=True`.

## 0.9 Usage Examples

### End-to-end automation

```text
comfy_generate_run_fetch
name: city.json
intent: text to image
parameters:
  checkpoint_name: model.safetensors
  positive_prompt: cinematic city at night
```

The automation path is for low-risk single-run requests. It uses `wait_for_completion=True` and `fetch_outputs=True` by default, then runs project reindex so the workflow, run, and assets are visible to MCP and desktop views.

If the response includes `object_info_unavailable`, workflow overwrite, or another medium-risk policy reason, review `policy.reasons` before rerunning with `confirm_risky_actions=True`. A blocked policy cannot be overridden.

### Desktop app shell

```powershell
npm --prefix desktop install
npm --prefix desktop run typecheck
npm --prefix desktop run build
cargo check --manifest-path desktop\src-tauri\Cargo.toml
```

The desktop shell is a local project workbench. It does not run ComfyUI, does not edit workflow graphs, and does not replace Codex. It uses the Python desktop bridge to reuse the same project index, config redaction, path safety, workflow listing, run listing, and asset search logic as the MCP server.

The `Assets` view now includes asset gallery and table modes, metadata editing, comparison, safe cleanup UI, and asset report preview. The `Batches` view is a batch task view for inspecting batch records, child runs, and variation parameters created by MCP batch tools.

### Workflow generation

```text
comfy_plan_workflow_generation
comfy_generate_workflow
comfy_evaluate_submit_policy
```

Generated workflows expose validation, repairs, and submit policy. Submit only when policy is `allowed`; ask for confirmation when policy is `requires_confirmation`; do not submit when policy is `blocked`.

### Project index

```text
comfy_project_status
comfy_reindex_project
comfy_project_status
comfy_reindex_assets
comfy_search_assets
comfy_update_asset_metadata
comfy_write_asset_sidecars
comfy_plan_asset_cleanup
comfy_export_asset_library_report
comfy_compare_assets
```

The project index is stored at `.comfydex/comfydex.db`. Reindexing rebuilds SQLite rows from compatibility records and does not delete workflow files, run records, batch records, output files, sidecars, or reports.

### UI workflow import

```text
comfy_classify_workflow
comfy_import_ui_workflow
comfy_convert_ui_to_api
comfy_validate_api_workflow
comfy_submit_workflow
```

Keep the original UI workflow. Treat conversion gaps from `comfy_explain_conversion_gaps` as actionable work before submission.

### Workflow builder

```text
comfy_list_workflow_templates
comfy_suggest_workflow_template
comfy_build_workflow_plan
comfy_explain_workflow_plan
comfy_build_workflow
comfy_validate_workflow_against_object_info
```

Do not submit generated workflows while the plan lists missing required inputs or unavailable node types.

### Custom node assistant

```text
comfy_scaffold_custom_node_package
comfy_inspect_custom_node_package
comfy_validate_node_mappings
comfy_validate_node_class
comfy_check_node_imports
comfy_generate_node_docs
comfy_generate_node_examples
comfy_run_node_contract_tests
comfy_custom_node_repair_guidance
```

Default custom node writes are workspace-local under `custom_nodes/`. Example generation returns `generated` or `blocked`; contract tests return `passed`, `blocked`, or `failed`; repair guidance returns `ready`, `needs_work`, or `blocked`.

### Run diagnostics and batch work

```text
comfy_diagnose_run
comfy_export_run_report
comfy_compare_runs
comfy_list_outputs
comfy_cleanup_outputs
comfy_batch_submit
comfy_read_batch
```

Cleanup is dry-run by default. Use `confirm=True` only after inspecting candidates.

## Local Data

By default, Comfydex stores workspace data in:

```text
workflows/
runs/
.comfydex/comfydex.db
```

Workflow files are stored as JSON under `workflows/`.

Each submitted workflow creates a run directory under `runs/`:

```text
runs/
  2026-06-02T10-30-00_text2img/
    run.json
    workflow.json
    outputs/
```

Run records store:

- run id
- workflow name
- prompt id
- client id
- base URL
- status
- timestamps
- WebSocket and fallback events
- output references and downloaded paths

The SQLite project index under `.comfydex/comfydex.db` stores searchable rows for workflows, runs, outputs, batches, and recoverable index errors. It is rebuilt from the JSON and filesystem compatibility records.

## Safety Boundaries

Comfydex intentionally keeps the implementation bounded:

- default ComfyUI target is local: `http://127.0.0.1:8188`
- remote URLs are opt-in through config
- custom headers are supported, but login and OAuth flows are not implemented
- workflow writes are restricted to the configured workflow directory
- workflow submission should happen only after validation reports `valid`
- custom node scaffolding defaults to workspace-local `custom_nodes/`
- output downloads are restricted to the corresponding run output directory
- output cleanup is dry-run by default and requires `confirm=True` for deletion
- path traversal is rejected
- header values are redacted in config responses
- Comfydex does not modify ComfyUI installation files

## Installation For Local Codex Development

This repository is structured as a local Codex plugin. For local development, place or clone it at:

```text
C:/Users/Drew/plugins/comfydex
```

Install the Python package in editable mode:

```powershell
Set-Location "C:/Users/Drew/plugins/comfydex"
python -m pip install -e ".[dev]"
```

For the 1.0 local developer install path, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
```

See `docs/release/windows-install.md` for prerequisites, Codex plugin discovery, and ComfyUI connection checks.

The plugin is expected to be listed in the personal Codex marketplace:

```text
C:/Users/Drew/.agents/plugins/marketplace.json
```

Example marketplace entry:

```json
{
  "name": "comfydex",
  "source": {
    "source": "local",
    "path": "./plugins/comfydex"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

After installing or refreshing the plugin, start a new Codex thread so Codex can discover the updated Skill and MCP tools.

## Verification

Run the full test suite:

```powershell
Set-Location "C:/Users/Drew/plugins/comfydex"
python -m pytest -v
```

Validate the Codex plugin manifest:

```powershell
python scripts/validate_plugin.py
```

Validate release package consistency:

```powershell
python scripts/validate_release_package.py
```

Validate the desktop app shell:

```powershell
npm --prefix desktop run typecheck
npm --prefix desktop run build
cargo check --manifest-path desktop\src-tauri\Cargo.toml
```

Validate the Live Bridge after installing or updating it:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\verify_live_bridge.ps1 -BaseUrl "http://127.0.0.1:8188" -SkipPush
```

Desktop Live Bridge status terms:

- Ready: ComfyUI reachable, backend route loaded, frontend extension listed, frontend connected.
- Restart required: ComfyUI reachable but bridge status route is missing.
- Refresh required: backend route loaded but frontend client has not heartbeated or is stale.
- Unsaved canvas: frontend refused a push because the current workflow has unsaved changes.

Use Reload client from Settings when the frontend client needs to reconnect. Use Reload backend after changing bridge Python/runtime files and restarting ComfyUI is not required for the backend reload path.

## Release Notes

### 1.2.0 - Live Bridge Productization

- Added MCP and desktop bridge operations for Live Bridge status, frontend reload, backend reload, push, and verification.
- Added desktop Dashboard and Settings Live Bridge status panels with Ready, Restart required, Refresh required, and Unsaved canvas diagnostics.
- Hardened install, update, backup, verification, and push acknowledgement scripts for the ComfyUI-side bridge.
- Added release docs, status meanings, and release gates for the productized Live Bridge workflow.

### 1.1.0 - Live Bridge Release

- Added `custom_nodes/comfydex_live_bridge`, a ComfyUI-side bridge with stable bootstrap routes and reloadable runtime logic.
- Added a frontend loader/client split so bridge client code can be reloaded without restarting ComfyUI after the initial custom node bootstrap is loaded.
- Added safe live workflow push behavior with a `force` flag for replacing unsaved desktop canvas state intentionally.
- Added `scripts/install_live_bridge.ps1`, `scripts/live_bridge.ps1`, and `scripts/verify_live_bridge.ps1` for installation, local status/reload/push operations, and post-restart P6 verification.
- Added tests for the bridge backend, frontend contract, safety behavior, install script, local command script, and P6 verification script.
- Improved `comfy_wait_for_run` so completed history can be detected before waiting on the WebSocket.

### 1.0.0 - Usable Developer Release

- Added `scripts/install_windows.ps1` as a Windows local install and verification helper.
- Added release docs for Windows install, final release checklist, and security/path review.
- Extended `scripts/validate_release_package.py` to enforce 1.0 release assets.
- Finalized README, Skill guidance, release metadata, and version consistency for the 1.0 local developer toolchain.

### 0.9.0 - End-To-End Automation And Hardening

- Added `comfy_generate_run_fetch` for safe one-call generate-run-fetch automation.
- Hardened submit policy so `object_info_unavailable` and unknown validation states require explicit confirmation.
- Added structured recovery responses for submit, wait, fetch, and reindex stages.
- Added `scripts/validate_release_package.py` for release metadata, desktop package, docs, and plugin consistency checks.

### 0.8.0

- Added Gallery And Batch UI surfaces in the Tauri desktop app.
- Upgraded the Assets view with asset gallery/table modes, favorite/rating/tag/notes controls, comparison, report generation, and safe cleanup UI.
- Added a Batches navigation view with batch task view lists, Batch detail, Child runs, and Variation parameters.
- Added desktop bridge and Tauri commands for asset metadata updates, cleanup planning, asset reports, asset comparison, batch listing, and batch reading.

### 0.7.0

- Added a Windows-first Tauri desktop app shell under `desktop/`.
- Added the Python desktop bridge CLI used by Tauri commands.
- Added dashboard, workflow, run, asset, and settings workbench views with browser fallback data.
- Added Tauri commands for workspace selection, project status, reindex, config, connection checks, workflow listing, run listing, and asset search.
- Added desktop build checks with TypeScript, Vite, and Rust `cargo check`.

### 0.6.0

- Added schema version `2` with indexed `asset_records`.
- Added asset search, tags, ratings, favorites, notes, and annotation preservation across reindex.
- Added sidecar metadata, asset cleanup planning, asset library reports, and asset comparison.
- Added `comfy_reindex_assets`, `comfy_search_assets`, `comfy_update_asset_metadata`, `comfy_write_asset_sidecars`, `comfy_plan_asset_cleanup`, `comfy_export_asset_library_report`, and `comfy_compare_assets`.

### 0.5.0

- Added deterministic custom node example generation for scalar defaults and enum choices.
- Added isolated custom node contract tests that instantiate mapped node classes, call `FUNCTION`, and verify tuple return counts.
- Added parsed import diagnostics and package-level repair guidance.
- Added `comfy_generate_node_examples`, `comfy_run_node_contract_tests`, and `comfy_custom_node_repair_guidance`.

### 0.4.0

- Added deterministic workflow generation planning with scored template candidates.
- Added generated workflow validation, safe repair records, and submit policy classification.
- Added `comfy_plan_workflow_generation`, `comfy_generate_workflow`, and `comfy_evaluate_submit_policy`.
- Preserved compatibility for existing workflow builder tools.

### 0.3.0

- Added a shared project core with `ProjectContext`, SQLite schema migrations, and project status reporting.
- Added a workspace-local project index at `.comfydex/comfydex.db`.
- Added `comfy_project_status` and `comfy_reindex_project`.
- Indexed workflows, runs, outputs, batches, and recoverable index errors while preserving compatibility records.

### 0.2.0

- Added UI workflow import, conversion, conversion-gap reporting, and API validation.
- Added workflow templates, build plans, template suggestions, and generated workflow validation.
- Added workspace-local custom node scaffolding, inspection, validation, import checks, and docs generation.
- Added run diagnostics, markdown reports, run comparison, output listing, confirmed cleanup, and batch records.
- Hardened run and output path safety around traversal, symlink/reparse redirection, and cleanup confirmation.

### 0.1.0

- Initial Codex plugin and Python MCP server.
- Added ComfyUI connection checks, workflow storage, workflow analysis, submission, waiting, run records, and output fetching.

Run a manual connection check from a Codex workspace:

```powershell
Set-Location "D:/Software Project/Comfydex"
python "C:/Users/Drew/plugins/comfydex/scripts/smoke_check.py"
```

If ComfyUI is running at `http://127.0.0.1:8188`, the smoke check should report `reachable: True`.

If ComfyUI is not running or is blocked by a proxy, the smoke check exits normally and reports `reachable: False` with an error type and message.

## Development Notes

The implementation is intentionally modular:

- `config.py` owns config defaults, validation, persistence, and redaction.
- `core/` owns project context, SQLite migrations, indexing, and status queries.
- `paths.py` owns path traversal protection.
- `workflows.py` owns workflow file operations and summaries.
- `analyzer.py` owns graph and object metadata analysis.
- `runs.py` owns run records and status updates.
- `comfy_client.py` owns ComfyUI HTTP calls.
- `ws.py` owns WebSocket URL construction and event waiting.
- `server.py` wires the modules into MCP tools.

Before publishing changes, run:

```powershell
python -m pytest -q
python scripts/validate_plugin.py
python -m json.tool .codex-plugin/plugin.json > $null
python -m json.tool .mcp.json > $null
npm --prefix desktop run typecheck
npm --prefix desktop run build
cargo check --manifest-path desktop\src-tauri\Cargo.toml
```

## License

MIT
