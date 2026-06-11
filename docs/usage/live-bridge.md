# Comfydex Live Bridge

The Live Bridge is the optional ComfyUI-side custom node package that lets Comfydex push UI workflow JSON directly into an open ComfyUI desktop canvas. Codex still owns workflow reasoning and file generation; ComfyUI remains the graph editor and runtime.

Use the Live Bridge when the user wants to describe a workflow in Codex and then see that workflow appear in the ComfyUI UI without manually importing a JSON file.

## Requirements

- ComfyUI is installed locally or on a reachable machine.
- ComfyUI can be opened in a browser at the configured base URL, usually `http://127.0.0.1:8188`.
- The Comfydex repository is available on the same machine that can write into ComfyUI `custom_nodes`.
- After first installation, ComfyUI must be restarted once so the custom node routes and frontend extension are loaded.

## Install

Install by pointing at the ComfyUI base directory. The script resolves the `custom_nodes` directory, copies `custom_nodes\comfydex_live_bridge`, and writes an install manifest beside the installed package.

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\install_live_bridge.ps1 -ComfyBaseDir "E:\ComfyUI files"
```

If a previous install exists, the script creates a timestamped backup unless `-NoBackup` is passed. Restart ComfyUI after the first install.

## Update

For updates, point directly at the existing ComfyUI `custom_nodes` directory:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\install_live_bridge.ps1 -ComfyCustomNodesDir "E:\ComfyUI files\custom_nodes"
```

ComfyUI may not need a full restart for runtime changes if the backend route is already loaded. Use the desktop Settings view or `scripts\live_bridge.ps1 verify` to run Reload backend and Reload client checks.

## Verify

Use a no-push verification after install, update, or restart. This checks ComfyUI reachability, bridge route readiness, frontend extension listing, and frontend heartbeat state.

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\verify_live_bridge.ps1 -BaseUrl "http://127.0.0.1:8188" -SkipPush
```

Use push verification when you want to prove that a UI workflow can be sent into the ComfyUI canvas. The workflow file must be UI workflow JSON with top-level `nodes` and `links`.

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\verify_live_bridge.ps1 -BaseUrl "http://127.0.0.1:8188" -WorkflowPath "workflows\z-image-turbo-text-to-image.ui.json" -Force
```

`-Force` allows the bridge to replace the current canvas. Without `-Force`, the frontend client rejects a push if the current ComfyUI canvas has unsaved changes.

## Desktop Status Meanings

- Ready: ComfyUI reachable, backend route loaded, frontend extension listed, frontend connected.
- Restart required: ComfyUI reachable but bridge status route is missing.
- Refresh required: backend route loaded but frontend client has not heartbeated or is stale.
- Unsaved canvas: frontend refused a push because the current workflow has unsaved changes.

Dashboard shows the compact Live Bridge status. Settings shows full diagnostics plus Verify, Reload client, and Reload backend actions.

## Diagnostics

The verification script returns structured JSON. Important diagnostic codes include:

- `comfyui_unreachable`: ComfyUI cannot be reached at the configured base URL.
- `bridge_not_loaded`: ComfyUI is reachable but the Live Bridge status route is missing.
- `bridge_frontend_not_listed`: the backend route is loaded but the frontend extension was not listed by ComfyUI.
- `frontend_not_connected`: the frontend extension has not reported a client heartbeat.
- `frontend_stale`: the frontend heartbeat exists but is outside the freshness window.
- `unsaved_canvas`: the frontend refused a push because the canvas has unsaved changes.
- `workflow_not_ui_json`: the selected workflow is API prompt JSON or another unsupported JSON shape.
- `workflow_ack_timeout`: the script pushed a workflow but did not receive a matching frontend acknowledgement in time.

## Remove

Stop ComfyUI first, then remove the installed bridge package and manifest:

```powershell
Remove-Item -LiteralPath "E:\ComfyUI files\custom_nodes\comfydex_live_bridge" -Recurse -Force
Remove-Item -LiteralPath "E:\ComfyUI files\custom_nodes\comfydex_live_bridge.install.json" -Force
```

Start ComfyUI again after removal. The desktop app should then report Restart required because the bridge status route is no longer present.
