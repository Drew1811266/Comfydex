# Workflow Builder

Use this flow when the user describes an image-generation workflow in natural language and wants Comfydex to build a first API prompt.

## Tool Order

1. `comfy_list_workflow_templates`
2. `comfy_suggest_workflow_template`
3. `comfy_build_workflow_plan`
4. `comfy_explain_workflow_plan`
5. `comfy_build_workflow`
6. `comfy_validate_workflow_against_object_info`

Required inputs are the user intent, available templates, target filename, and object metadata when validating against a live ComfyUI node catalog.

## Build Plans

Use the plan as the contract for the generated workflow. If the plan lists required inputs, unavailable node types, or assumptions, resolve those before building or submitting.

## Required Inputs

Required checkpoint, prompt text, image dimensions, sampler settings, and output filename prefix should be explicit in the plan. Do not invent unavailable models or custom nodes.

## Validation

Validate the generated API workflow before submission. If validation fails, revise the plan or generated inputs rather than submitting a partial workflow.
