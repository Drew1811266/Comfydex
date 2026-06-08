# Security And Path Review

This document records the `1.0.0` security and path-safety review for Comfydex.

## Workflow Files

Workflow file writes use `safe_json_path`, which rejects path traversal, absolute filenames, nested paths, and non-`.json` names. Tools that write workflows keep files under the configured workflow directory.

## Run Records And Outputs

Run ids are validated as single safe path segments. Output downloads use `safe_output_path`, which rejects absolute paths, `..`, empty path parts, and paths outside the run output directory.

Output listing and cleanup ignore directories without safe run records and skip redirected files or directories. Confirmed deletion rechecks candidates before deleting them.

## Asset Cleanup

Asset cleanup uses dry-run planning by default. cleanup confirmation is explicit in MCP tools and desktop UI surfaces. The desktop UI does not construct delete paths itself; it calls shared cleanup planners.

## Headers And Config

Config responses use header redaction so sensitive header values are not returned to Codex or the desktop app. The local install helper does not request credentials and does not implement browser login or OAuth flows.

## Custom Node Boundary

Custom node scaffolding writes workspace-local packages under `custom_nodes/`. Package names are validated, package paths must stay inside the workspace boundary, and import checks run with bounded timeout and output limits.

## Desktop Bridge

The desktop bridge stores only the selected workspace path in Tauri config and calls Python bridge operations. The desktop bridge keeps workspace operations under configured project paths and rejects unsafe batch ids, workflow names, and redirected paths through shared helpers.

## Remaining 1.0 Limitations

Comfydex `1.0.0` is a local developer toolchain, not a hardened multi-user service. It does not provide sandboxed model execution, signed installer guarantees, remote server fleet isolation, or cloud tenant controls.
