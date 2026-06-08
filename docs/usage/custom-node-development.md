# Custom Node Development

Use this flow when the user wants to scaffold, inspect, validate, or document a ComfyUI custom node package.

## Workspace Boundary

Default writes go under workspace-local `custom_nodes/`. Do not write into a user's ComfyUI installation unless the user explicitly configures that target.

## Scaffold Flow

1. `comfy_scaffold_custom_node_package`
2. `comfy_inspect_custom_node_package`
3. `comfy_validate_node_mappings`
4. `comfy_validate_node_class`
5. `comfy_check_node_imports`
6. `comfy_generate_node_docs`

Required inputs are a safe package name and, for validation, the class or mapping key being checked.

## Inspection And Validation

Use `comfy_validate_node_class` to check `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, and callable behavior. Use `comfy_validate_node_mappings` to verify `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`.

## Import Checks

Use `comfy_check_node_imports` before claiming the package loads. Import errors should be reported as diagnostics; they must not crash the MCP server. Generated docs should be deterministic and kept in the package.
