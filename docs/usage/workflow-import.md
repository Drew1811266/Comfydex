# Workflow Import

Use this flow when the user provides a ComfyUI UI workflow export and wants a submit-ready API prompt.

## Tool Order

1. `comfy_classify_workflow`
2. `comfy_import_ui_workflow`
3. `comfy_convert_ui_to_api`
4. `comfy_validate_api_workflow`
5. `comfy_submit_workflow` only after validation reports `valid`

Required inputs are the UI workflow JSON file, a target API filename, and object metadata from `comfy_get_object_info` when conversion needs node input mapping.

## Validation

Run `comfy_validate_api_workflow` after conversion. If object metadata is available, use `comfy_validate_workflow_against_object_info` to catch missing required inputs and unavailable node classes before submission.

## Conversion Gaps

Treat conversion gaps as work items. Do not call a conversion successful when required widgets, links, or node metadata are unresolved. Keep the original `.ui.json` file so the user can inspect the source graph.

## Safe Submission

Workflow files must stay inside the configured workflows directory. Do not submit until validation reports `valid`, and do not overwrite an existing API workflow unless the user asked for that target name.
