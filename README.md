# Comfydex

Comfydex is a Codex plugin that connects Codex to ComfyUI. It gives Codex both the operational tools and the workflow knowledge needed to inspect, manage, submit, monitor, and collect ComfyUI workflow runs.

The plugin is installed in Codex, not in ComfyUI. ComfyUI remains the runtime server, and Comfydex talks to it through the ComfyUI HTTP and WebSocket APIs.

## Status

Current version: `0.1.0`

This first release focuses on a practical developer workflow:

- connect to a local or remote ComfyUI server
- manage workflow JSON files from a Codex workspace
- analyze workflow nodes, links, model references, and missing node types
- submit API prompt JSON to ComfyUI
- watch execution through WebSocket events
- fall back to HTTP queue/history polling when WebSocket waiting fails
- persist local run records
- fetch or register generated outputs
- provide a Codex Skill that teaches Codex how to reason about ComfyUI workflows

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
├── skills/
│   └── comfyui-workflows/
│       └── SKILL.md             # Codex workflow guidance
├── scripts/
│   └── smoke_check.py           # Manual ComfyUI connection check
├── src/
│   └── comfydex_mcp/
│       ├── analyzer.py          # Workflow graph and node analysis
│       ├── comfy_client.py      # ComfyUI HTTP client
│       ├── config.py            # Workspace config loading and redaction
│       ├── paths.py             # Path safety helpers
│       ├── runs.py              # Run record persistence
│       ├── server.py            # FastMCP tool server
│       ├── workflows.py         # Workflow storage and summaries
│       └── ws.py                # WebSocket waiting helpers
└── tests/                       # Unit and integration-style tests
```

## Runtime Model

Comfydex has three layers.

### Codex Plugin

The plugin manifest declares the plugin metadata, Skill directory, and MCP server configuration so Codex can discover and load Comfydex.

### Python MCP Server

The MCP server exposes `comfy_*` tools to Codex. These tools manage configuration, workflow files, ComfyUI API calls, WebSocket waiting, run records, and output downloads.

### ComfyUI Workflow Skill

The Skill explains how Codex should work with ComfyUI workflows, including the difference between:

- UI workflow JSON, exported for the ComfyUI visual editor
- API prompt JSON, submitted to ComfyUI `/prompt`

Version `0.1.0` can analyze both shapes, but submission requires API prompt JSON.

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

## Local Data

By default, Comfydex stores workspace data in:

```text
workflows/
runs/
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

## Safety Boundaries

Comfydex intentionally keeps the first release narrow:

- default ComfyUI target is local: `http://127.0.0.1:8188`
- remote URLs are opt-in through config
- custom headers are supported, but login and OAuth flows are not implemented
- workflow writes are restricted to the configured workflow directory
- output downloads are restricted to the corresponding run output directory
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
python "C:/Users/Drew/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" "C:/Users/Drew/plugins/comfydex"
```

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
python "C:/Users/Drew/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" "C:/Users/Drew/plugins/comfydex"
```

## Version 0.1.0 Scope

Included:

- Codex plugin scaffold
- Python MCP server
- ComfyUI HTTP client
- ComfyUI WebSocket wait handling
- HTTP polling fallback
- workflow storage and analysis
- run record persistence
- output fetching
- ComfyUI workflow Skill
- smoke check script
- automated tests

Not included yet:

- natural-language workflow generation
- UI workflow JSON to API prompt JSON conversion
- custom node package scaffolding
- visual output preview inside Codex
- old output cleanup
- semantic workflow version diffing

## License

MIT
