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

Comfydex `1.9.0` is a Windows-first local developer toolchain. Use MCP tools for the 2.0 Readiness Gate, Ordinary User Guidance, workflow generation, the UI Graph Builder, the Execution And Repair Loop, the Scenario Recipe Registry, capability resolution, validation, safe submission, queue waiting, output fetching, diagnostics, asset management, custom node validation, and project indexing. Use `scripts/install_windows.ps1` and `docs/release/windows-install.md` for local install verification when the user asks how to install or validate the local release.

## Standard Tool Order

For a normal run:

1. Call `comfy_project_status`.
2. Call `comfy_reindex_project` when project counts are stale or files were changed outside Comfydex.
3. Call `comfy_reindex_assets` when output assets should be searchable or sidecars are needed.
4. Call `comfy_list_20_scenarios` or `comfy_20_readiness_report` when checking 2.0 first-class scenario coverage or release readiness.
5. Call `comfy_list_generation_presets` when the user wants simple quality, speed, aspect ratio, or style choices.
6. For low-risk one-call generation, call `comfy_generate_run_fetch`.
7. Otherwise, call `comfy_suggest_workflow_recipes` to inspect recipe candidates when the user describes a scenario.
8. Call `comfy_resolve_recipe_capabilities` for recipe-aware capability checks before relying on named local models or installed custom nodes.
9. Call `comfy_plan_workflow_generation` before creating a new workflow and inspect the selected recipe id, `user_guidance`, and `resolved_defaults`.
10. Call `comfy_explain_user_plan` when a plain-language summary is needed for an existing plan.
11. Call `comfy_build_ui_workflow` when the user wants a readable generated UI workflow graph without saving.
12. Call `comfy_generate_ui_workflow` when the user wants to save a generated UI workflow for ComfyUI canvas review.
13. Call `comfy_generate_push_ui_workflow` when the user wants to save and perform a Live Bridge push into the ComfyUI canvas.
14. Call `comfy_read_ui_graph_history` when Codex or Desktop needs generated UI workflow history.
15. Call `comfy_generate_workflow` when required generation inputs are present and the target is API prompt JSON.
16. Call `comfy_evaluate_submit_policy` before submitting an existing or generated workflow.
17. Call `comfy_check_connection`.
18. Call `comfy_get_object_info` when node metadata is needed.
19. Call `comfy_model_inventory` and `comfy_resolve_capabilities` before relying on named local models or installed custom nodes outside a recipe path.
20. Call `comfy_create_install_plan` when capability resolution reports missing requirements; record the user's accepted/rejected decision with `comfy_record_install_audit`.
21. Call `comfy_list_workflows`.
22. Call `comfy_read_workflow` for the selected file.
23. Call `comfy_analyze_workflow`.
24. Call `comfy_submit_workflow` only when submit policy is `allowed`.
25. Call `comfy_wait_for_run`.
26. Call `comfy_fetch_outputs`.
27. Call `comfy_read_run`.
28. If a run fails or completes without outputs, call `comfy_plan_run_repair`.
29. Call `comfy_retry_run_repair` only for supported retry operations and only pass `confirm=True` after the user confirms confirmation-required retries.
30. Call `comfy_read_repair_history` to inspect recent repair decisions.

## Scenario Recipe Registry

Use `comfy_list_workflow_recipes`, `comfy_search_workflow_recipes`, and `comfy_suggest_workflow_recipes` when the user asks for a natural workflow scenario such as text-to-image, LoRA, image-to-image, upscale, or ControlNet pose.

Recipe tools return recipe candidates. A generation plan can include a selected recipe id next to the selected template. Use those fields to explain the plan before building or submitting.

Use `comfy_resolve_recipe_capabilities` for recipe-aware capability checks. The recipe path performs no automatic downloads, does not install custom nodes, and does not mutate ComfyUI.

## Capability Resolver

Use `comfy_model_inventory` to inspect local model files. Use `comfy_resolve_capabilities` to compare a requested workflow plan with live ComfyUI `object_info` and the local model inventory.

If required models or nodes are missing, use `comfy_create_install_plan` to create a conservative manual review plan. The plan does not download models, install custom nodes, or mutate ComfyUI; there are no automatic downloads. Use `comfy_record_install_audit` and `comfy_read_install_audit` to record and review accepted or rejected decisions.

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

Use `comfy_summarize_assets` when the user needs a plain output-library summary in addition to the technical asset rows.

## Desktop App Boundary

Comfydex also includes a `desktop/` Tauri desktop app shell for local project browsing. Treat it as a workbench for project status, workflow lists, run lists, asset search, and settings visibility.

The desktop app uses the Python desktop bridge, so its data should match MCP project operations such as `comfy_project_status`, `comfy_reindex_project`, `comfy_list_workflows`, `comfy_list_runs`, and `comfy_search_assets`.

The `0.8.0` desktop gallery can help the user review assets, compare outputs, generate asset reports, inspect cleanup dry-runs, and edit simple metadata. Treat this desktop gallery as a visual management surface, not as the source of workflow truth.

The batch task view reads batch records and child run status. Submit new batches through `comfy_batch_submit`, inspect the batch task view afterward, and use `comfy_read_batch` when Codex needs the authoritative JSON record.

The Generated Graphs view reads generated UI workflow history and can push a selected generated UI workflow through the Python desktop bridge operation `push_ui_workflow`. Treat Generated Graphs as an action and history surface for UI Graph Builder output, not as a visual node editor.

The Runs repair panel reads repair plans through `plan_run_repair`, retries through `retry_run_repair`, and reads recent repair history through `read_repair_history`. Treat it as a failure review and conservative retry surface, not as an automatic installer, model downloader, or graph editor.

Do not assume the desktop shell can edit ComfyUI workflow graphs, run ComfyUI itself, package Python offline, or replace Codex reasoning. Use MCP tools for authoritative workflow generation, validation, submission, queue waiting, output collection, diagnostics, and asset metadata updates.

## Workflow Generation

Use `comfy_plan_workflow_generation` to turn intent and parameters into a scored generation plan. Inspect recipe candidates, the selected recipe id, and `missing_information` before generating.

For ordinary users, prefer presets such as `quality_preset`, `aspect_ratio`, and `style_preset` over asking for internal sampler details. Inspect `user_guidance` for the plain-language summary and `resolved_defaults` for the exact width, height, steps, CFG, GPU class, model family, and preset decisions.

Use `comfy_generate_workflow` to build, validate, repair, and save a workflow. Inspect `repairs`, `gaps`, and `policy` before submitting.

Use `comfy_evaluate_submit_policy` for existing workflows. Submit only when policy is `allowed`; ask for confirmation when policy is `requires_confirmation`; do not submit when policy is `blocked`.

Use `comfy_generate_run_fetch` only for low-risk single-run requests. It can generate, save, submit, wait, call `fetch_outputs`, and reindex in one tool call.

When `comfy_generate_run_fetch` completes successfully, inspect `output_summary` before presenting the result to a non-developer user.

If `comfy_generate_run_fetch` returns `requires_confirmation`, review `policy.reasons` before passing `confirm_risky_actions=True`. Common reasons include workflow overwrite and `object_info_unavailable`; unknown validation must not be silently auto-run.

If `comfy_generate_run_fetch` fails during submit, wait, failed wait, or fetch, inspect the returned `diagnosis`, `failure_class`, `repair_summary`, and `repair_plan`. Fetch failures use a repair plan with `retry.operation == "fetch_outputs"`. Resubmit repair plans require `requires_confirmation` before retry.

Use `wait_for_completion=False` to stop after submission. Use `fetch_outputs=False` to wait without output download. After a fetch or manual output change, use `comfy_reindex_project` or the automation result's reindex data to keep the project index current.

## Execution And Repair Loop

Use the Execution And Repair Loop when a run fails or completes without registered outputs:

1. `comfy_read_run`
2. `comfy_diagnose_run`
3. `comfy_plan_run_repair`
4. `comfy_retry_run_repair`
5. `comfy_read_repair_history`

Repair data uses `failure_class`, `repair_summary`, `repair_plan`, `actions`, `retry`, `requires_confirmation`, and `retry_result` consistently across MCP, automation failure responses, and desktop bridge operations.

Retry `fetch_outputs` only when the repair plan supports it. Do not resubmit a workflow unless the plan says retry is supported and the user has confirmed confirmation-required retry.

Repair plans do not grant permission for model installation, custom node installation, or downloads. Keep no silent downloads, no automatic downloads, and no automatic custom node installation.

## UI Graph Builder

Use the UI Graph Builder when the user wants a generated UI workflow that can be inspected in ComfyUI's visual editor. Call `comfy_build_ui_workflow` first when Codex should inspect a readable graph without saving.

Use `comfy_generate_ui_workflow` to save a generated UI workflow and append generated graph history. Use `comfy_generate_push_ui_workflow` only when Live Bridge is ready and the user wants the generated graph pushed to the ComfyUI canvas. Use `comfy_read_ui_graph_history` to review saved and pushed generated graph records.

Generated UI workflow files are for canvas review and editing. They are not API prompt JSON and should not be submitted through `/prompt` without conversion and validation.

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
- Use `comfy_plan_run_repair` before deciding whether a retry is safe.
- Use `comfy_read_repair_history` when comparing recent recovery attempts.
- Do not claim output download success until `comfy_fetch_outputs` returns downloaded paths or registered output references.

## Safety

- Do not reveal configured header values.
- Do not write workflow files outside the configured workflow directory.
- Do not download outputs outside the run output directory.
- Ask before changing the configured remote ComfyUI base URL.
