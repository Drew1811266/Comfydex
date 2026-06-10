# Comfydex Live Bridge Hot Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a maintainable Comfydex Live Bridge that can push workflows into a running ComfyUI desktop canvas and hot-reload bridge client/backend behavior after one bootstrap install.

**Architecture:** A stable ComfyUI custom node package exposes fixed HTTP routes and websocket events. Runtime behavior is split into small backend modules and a frontend loader/client pair so Codex can update behavior through controlled reload endpoints instead of requiring ComfyUI route re-registration.

**Tech Stack:** Python 3.12, aiohttp routes from ComfyUI `PromptServer`, ComfyUI frontend extension JavaScript, PowerShell install scripts, pytest, Node `--check`.

---

### Task 1: Workspace Package And Installer

**Files:**
- Create: `custom_nodes/comfydex_live_bridge/__init__.py`
- Create: `custom_nodes/comfydex_live_bridge/backend.py`
- Create: `custom_nodes/comfydex_live_bridge/web/comfydex_live_bridge.js`
- Create: `scripts/install_live_bridge.ps1`
- Test: `tests/test_live_bridge_package.py`

- [ ] Write tests that assert the bridge package exists in the workspace, exports ComfyUI custom node metadata, and installer copies files into a target `custom_nodes` directory.
- [ ] Run pytest and confirm these tests fail before implementation.
- [ ] Implement the workspace package and install script.
- [ ] Run pytest and confirm Task 1 tests pass.

### Task 2: Stable Backend RPC

**Files:**
- Modify: `custom_nodes/comfydex_live_bridge/__init__.py`
- Modify: `custom_nodes/comfydex_live_bridge/backend.py`
- Test: `tests/test_live_bridge_backend.py`

- [ ] Write tests for `status`, `load_workflow`, `reload_backend`, and fixed RPC dispatch behavior without requiring ComfyUI to run.
- [ ] Run pytest and confirm tests fail on missing backend behavior.
- [ ] Implement backend handlers with dependency injection for `PromptServer`.
- [ ] Run pytest and confirm backend tests pass.

### Task 3: Frontend Loader And Client Hot Reload

**Files:**
- Modify: `custom_nodes/comfydex_live_bridge/web/comfydex_live_bridge.js`
- Create: `custom_nodes/comfydex_live_bridge/web/client.js`
- Test: `tests/test_live_bridge_frontend.py`

- [ ] Write tests that inspect JS source for loader/client split, cache-busted dynamic import, websocket event listeners, and client `dispose`.
- [ ] Run pytest and confirm tests fail before implementation.
- [ ] Implement loader and client module.
- [ ] Run pytest and `node --check` for both JS files.

### Task 4: Safe Workflow Push

**Files:**
- Modify: `custom_nodes/comfydex_live_bridge/backend.py`
- Modify: `custom_nodes/comfydex_live_bridge/web/client.js`
- Test: `tests/test_live_bridge_safety.py`

- [ ] Write tests for workflow object validation, `force` defaulting to false, and websocket payload shape.
- [ ] Run pytest and confirm tests fail before safety implementation.
- [ ] Implement backend validation and frontend dirty-canvas guard.
- [ ] Run pytest and JS syntax checks.

### Task 5: Local Tooling For Codex

**Files:**
- Create: `scripts/live_bridge.ps1`
- Test: `tests/test_live_bridge_scripts.py`

- [ ] Write tests that assert the CLI supports `status`, `push-workflow`, `reload-client`, and `reload-backend`.
- [ ] Run pytest and confirm tests fail before the script exists.
- [ ] Implement the PowerShell command wrapper against `http://127.0.0.1:8000/comfydex/live/*`.
- [ ] Run pytest and inspect PowerShell parser output.

### Task 6: End-To-End Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-06-10-comfydex-live-bridge-hot-reload.md`
- Create: `scripts/verify_live_bridge.ps1`

- [ ] Run full pytest suite.
- [ ] Run Python compile checks for the bridge package.
- [ ] Run Node syntax checks for bridge frontend files.
- [ ] Install bridge into `E:\ComfyUI files\custom_nodes`.
- [ ] If ComfyUI has been restarted, verify `/comfydex/live/status`; otherwise record the restart boundary explicitly.
- [ ] If the bridge route is active, push `workflows/z-image-turbo-text-to-image.ui.json` into the running canvas.
- [ ] Run `scripts/verify_live_bridge.ps1 -WorkflowPath workflows/z-image-turbo-text-to-image.ui.json -Force` after ComfyUI restarts.

### Self-Review

- Spec coverage: P1 through P6 are represented as separate tasks with tests or runtime checks.
- Placeholder scan: No implementation step relies on unspecified behavior; runtime ComfyUI verification has an explicit restart boundary.
- Type consistency: Backend route names and script command names use the same route family: `/comfydex/live/status`, `/comfydex/live/load_workflow`, `/comfydex/live/reload_client`, `/comfydex/live/reload_backend`, and `/comfydex/live/rpc`.

### Verification Notes

- 2026-06-10: `pytest -q` passed with 20 tests.
- 2026-06-10: Python compile checks passed for workspace and installed bridge backend files.
- 2026-06-10: `node --check` passed for workspace and installed bridge frontend files.
- 2026-06-10: `scripts/install_live_bridge.ps1` installed the bridge into `E:\ComfyUI files\custom_nodes\comfydex_live_bridge`.
- 2026-06-10: The running ComfyUI process still returned 404 for `/comfydex/live/status`, and `/extensions` did not list `comfydex_live_bridge`, because the desktop process has not restarted since installation.
- 2026-06-10: The active Comfy Desktop window title still includes `*Unsaved Workflow`; do not restart it automatically.
- 2026-06-10: Backend hot reload is implemented as stable `backend.py` route registration plus reloadable `runtime.py` business logic through `/comfydex/live/reload_backend`.
- 2026-06-10: Backend reload is transactional: if `runtime.py` reload fails, the old runtime remains active and the endpoint returns `backend_reload_failed`.
- 2026-06-10: Added `scripts/verify_live_bridge.ps1` for post-restart P6 verification. In the current unrestarted ComfyUI process it returns structured JSON with `bridge_not_loaded` and HTTP status 404.
- 2026-06-10: After starting Comfy Desktop, `scripts/verify_live_bridge.ps1 -WorkflowPath workflows/z-image-turbo-text-to-image.ui.json -Force` passed. It verified bridge status, listed frontend extensions, reloaded the client, reloaded backend runtime generation 1, and pushed `z-image-turbo-text-to-image.ui`.
- 2026-06-10: Comfy Desktop window title changed to `ComfyUI - z-image-turbo-text-to-image.ui`, confirming the desktop frontend received the live workflow load event.
