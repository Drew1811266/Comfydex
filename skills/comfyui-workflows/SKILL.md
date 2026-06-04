---
name: comfyui-workflows
description: Use when working with ComfyUI workflows from Codex, including inspecting workflow JSON, checking ComfyUI connection, submitting prompts, waiting for queue execution, fetching outputs, or diagnosing missing nodes and models through Comfydex MCP tools.
---

# ComfyUI Workflows With Comfydex

Use this skill when the user asks Codex to inspect, manage, run, or debug a ComfyUI workflow.

## Core Concepts

ComfyUI has two common workflow JSON shapes:

- UI workflow JSON: exported for the ComfyUI visual editor. It usually has `nodes` and `links`.
- API prompt JSON: submit-ready JSON for `/prompt`. It is usually a JSON object whose values contain `class_type` and `inputs`.

First-version Comfydex can analyze both shapes, but `comfy_submit_workflow` requires API prompt JSON.

## Standard Tool Order

For a normal run:

1. Call `comfy_check_connection`.
2. Call `comfy_get_object_info` when node metadata is needed.
3. Call `comfy_list_workflows`.
4. Call `comfy_read_workflow` for the selected file.
5. Call `comfy_analyze_workflow`.
6. Call `comfy_submit_workflow`.
7. Call `comfy_wait_for_run`.
8. Call `comfy_fetch_outputs`.
9. Call `comfy_read_run`.

## Workflow Editing Rules

- Preserve node ids unless the user asks for a structural rewrite.
- Preserve links that are unrelated to the requested change.
- Update only the smallest set of node inputs needed for the user request.
- If a workflow is UI JSON, explain that submission requires API prompt JSON.
- Use `comfy_get_object_info` before validating unfamiliar node inputs.

## UI Workflow Import

When the user provides ComfyUI UI workflow JSON, call tools in this order:

1. `comfy_classify_workflow`
2. `comfy_import_ui_workflow`
3. `comfy_convert_ui_to_api`
4. `comfy_validate_api_workflow`
5. `comfy_submit_workflow` only after validation reports `valid`

Keep the original `.ui.json` file. Treat conversion gaps as actionable work, not as successful conversion.

## Workflow Builder

For workflow creation from intent, call:

1. `comfy_list_workflow_templates`
2. `comfy_build_workflow_plan`
3. `comfy_explain_workflow_plan`
4. `comfy_build_workflow`
5. `comfy_validate_workflow_against_object_info`

Do not submit generated workflows while required inputs or unavailable node types are listed in the plan.

## Diagnosis Rules

When a workflow fails:

- Check missing node types from `comfy_analyze_workflow`.
- Check missing model references in the workflow summary.
- Check `/history` through `comfy_get_history` for ComfyUI error data.
- Check the run record with `comfy_read_run` before retrying.
- Do not claim output download success until `comfy_fetch_outputs` returns downloaded paths or registered output references.

## Safety

- Do not reveal configured header values.
- Do not write workflow files outside the configured workflow directory.
- Do not download outputs outside the run output directory.
- Ask before changing the configured remote ComfyUI base URL.
