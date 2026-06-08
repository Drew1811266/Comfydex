---
name: comfyui-workflows
description: Use when working with ComfyUI workflows from Codex, including inspecting workflow JSON, checking project index state, generating workflows, checking ComfyUI connection, submitting prompts, waiting for queue execution, fetching outputs, or diagnosing missing nodes and models through Comfydex MCP tools.
---

# ComfyUI Workflows With Comfydex

Use this skill when the user asks Codex to inspect, manage, run, or debug a ComfyUI workflow.

## Core Concepts

ComfyUI has two common workflow JSON shapes:

- UI workflow JSON: exported for the ComfyUI visual editor. It usually has `nodes` and `links`.
- API prompt JSON: submit-ready JSON for `/prompt`. It is usually a JSON object whose values contain `class_type` and `inputs`.

Comfydex can classify, import, and convert UI workflow JSON, but `comfy_submit_workflow` requires validated API prompt JSON.

## Standard Tool Order

For a normal run:

1. Call `comfy_project_status`.
2. Call `comfy_reindex_project` when project counts are stale or files were changed outside Comfydex.
3. Call `comfy_reindex_assets` when output assets should be searchable or sidecars are needed.
4. For low-risk one-call generation, call `comfy_generate_run_fetch`.
5. Otherwise, call `comfy_plan_workflow_generation` before creating a new workflow.
6. Call `comfy_generate_workflow` when required generation inputs are present.
7. Call `comfy_evaluate_submit_policy` before submitting an existing or generated workflow.
8. Call `comfy_check_connection`.
9. Call `comfy_get_object_info` when node metadata is needed.
10. Call `comfy_list_workflows`.
11. Call `comfy_read_workflow` for the selected file.
12. Call `comfy_analyze_workflow`.
13. Call `comfy_submit_workflow` only when submit policy is `allowed`.
14. Call `comfy_wait_for_run`.
15. Call `comfy_fetch_outputs`.
16. Call `comfy_read_run`.

## Project Index

Use `comfy_project_status` to inspect the workspace paths, `.comfydex/comfydex.db`, schema version, index counts, and index error count.

Use `comfy_reindex_project` after manual file changes or when project status looks stale. Reindexing rebuilds SQLite rows from compatibility records and does not delete workflow files, run records, batch records, or output files.

## Asset Library

Use `comfy_reindex_assets` after runs complete or output files change.

Use `comfy_search_assets` to find generated outputs by prompt text, filename, model reference, tag, rating, favorite state, workflow, status, or type.

Use `comfy_update_asset_metadata` to set tags, rating, favorite state, and notes.

Use `comfy_write_asset_sidecars` when deterministic sidecar JSON metadata is needed.

Use `comfy_plan_asset_cleanup` as a dry-run before deleting asset files. Only pass `confirm=True` after inspecting candidates.

Use `comfy_export_asset_library_report` for a markdown asset summary and `comfy_compare_assets` for asset-to-asset comparison.

## Desktop App Boundary

Comfydex also includes a `desktop/` Tauri desktop app shell for local project browsing. Treat it as a workbench for project status, workflow lists, run lists, asset search, and settings visibility.

The desktop app uses the Python desktop bridge, so its data should match MCP project operations such as `comfy_project_status`, `comfy_reindex_project`, `comfy_list_workflows`, `comfy_list_runs`, and `comfy_search_assets`.

The `0.8.0` desktop gallery can help the user review assets, compare outputs, generate asset reports, inspect cleanup dry-runs, and edit simple metadata. Treat this desktop gallery as a visual management surface, not as the source of workflow truth.

The batch task view reads batch records and child run status. Submit new batches through `comfy_batch_submit`, inspect the batch task view afterward, and use `comfy_read_batch` when Codex needs the authoritative JSON record.

Do not assume the desktop shell can edit ComfyUI workflow graphs, run ComfyUI itself, package Python offline, or replace Codex reasoning. Use MCP tools for authoritative workflow generation, validation, submission, queue waiting, output collection, diagnostics, and asset metadata updates.

## Workflow Generation

Use `comfy_plan_workflow_generation` to turn intent and parameters into a scored generation plan. Resolve `missing_information` before generating.

Use `comfy_generate_workflow` to build, validate, repair, and save a workflow. Inspect `repairs`, `gaps`, and `policy` before submitting.

Use `comfy_evaluate_submit_policy` for existing workflows. Submit only when policy is `allowed`; ask for confirmation when policy is `requires_confirmation`; do not submit when policy is `blocked`.

Use `comfy_generate_run_fetch` only for low-risk single-run requests. It can generate, save, submit, wait, call `fetch_outputs`, and reindex in one tool call.

If `comfy_generate_run_fetch` returns `requires_confirmation`, review `policy.reasons` before passing `confirm_risky_actions=True`. Common reasons include workflow overwrite and `object_info_unavailable`; unknown validation must not be silently auto-run.

Use `wait_for_completion=False` to stop after submission. Use `fetch_outputs=False` to wait without output download. After a fetch or manual output change, use `comfy_reindex_project` or the automation result's reindex data to keep the project index current.

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
