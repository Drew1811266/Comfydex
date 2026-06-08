# Windows Install Guide

Comfydex `1.0.0` is a Windows-first local developer release. It is installed in Codex as a local plugin and talks to a local ComfyUI server through HTTP and WebSocket APIs.

This guide covers local development installation. It is not a signed production installer and does not bundle Python, Node.js, Cargo, ComfyUI, models, or custom nodes.

## Prerequisites

- Windows 10 or later.
- Python 3.11 or newer available as `python`.
- Node.js and npm for the `desktop/` Tauri frontend.
- Rust and Cargo for Tauri shell checks.
- A local ComfyUI server, usually `http://127.0.0.1:8188`.
- A local Codex plugin checkout, usually `C:/Users/Drew/plugins/comfydex`.

## Install

From PowerShell:

```powershell
Set-Location "C:/Users/Drew/plugins/comfydex"
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
```

The helper script runs:

```powershell
python -m pip install -e ".[dev]"
npm --prefix desktop install
python scripts\validate_plugin.py
python scripts\validate_release_package.py
python -m pytest tests -q
npm --prefix desktop run typecheck
npm --prefix desktop run build
cargo check --manifest-path desktop\src-tauri\Cargo.toml
```

Use `-SkipDesktopInstall` when only the Python MCP server and Skill are needed. Use `-SkipVerification` only for a quick local install after a verified checkout.

## Codex Plugin Discovery

After installation, refresh or reinstall the local Codex plugin so Codex can discover the updated MCP tools and Skills.

The plugin should point to this repository in the personal Codex plugin marketplace. For local development, keep the checkout path stable so `.codex-plugin/plugin.json`, `.mcp.json`, and `skills/` stay discoverable.

## ComfyUI Check

Start ComfyUI locally, then ask Codex to call:

```text
comfy_check_connection
```

If ComfyUI is reachable, continue with:

```text
comfy_project_status
comfy_generate_run_fetch
```

## Boundaries

The install helper does not modify ComfyUI installation files, does not install models, does not install custom node packages into ComfyUI, and does not delete local workflow or run records.
