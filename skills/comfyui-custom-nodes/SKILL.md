---
name: comfyui-custom-nodes
description: Use when developing, inspecting, validating, documenting, or smoke-checking ComfyUI custom node packages with Comfydex.
---

# ComfyUI Custom Nodes With Comfydex

Use this skill when the user wants help building a ComfyUI custom node package.

## Safety Boundary

Default writes go under workspace-local `custom_nodes/`.
Do not write into a user's ComfyUI installation unless the user explicitly configures that target.

## Scaffold Flow

1. `comfy_scaffold_custom_node_package`
2. `comfy_inspect_custom_node_package`
3. `comfy_validate_node_mappings`
4. `comfy_validate_node_class`
5. `comfy_check_node_imports`
6. `comfy_generate_node_docs`
7. `comfy_generate_node_examples`
8. `comfy_run_node_contract_tests`
9. `comfy_custom_node_repair_guidance`

## Existing Package Flow

1. `comfy_inspect_custom_node_package`
2. `comfy_validate_node_mappings`
3. `comfy_validate_node_class`
4. `comfy_check_node_imports`
5. `comfy_generate_node_docs`
6. `comfy_generate_node_examples`
7. `comfy_run_node_contract_tests`
8. `comfy_custom_node_repair_guidance`

Report import errors without crashing the MCP server. Prefer the complete loop `comfy_generate_node_examples` -> `comfy_run_node_contract_tests` -> `comfy_custom_node_repair_guidance` after static validation and import checks. Keep generated documentation deterministic.
