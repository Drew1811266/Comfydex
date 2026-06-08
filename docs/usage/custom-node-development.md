# Custom Node Development

Use this flow when the user wants to scaffold, inspect, validate, contract-test, document, or repair a ComfyUI custom node package.

## Workspace Boundary

Default writes go under workspace-local `custom_nodes/`. Do not write into a user's ComfyUI installation unless the user explicitly configures that target.

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

Required inputs are a safe package name and, for validation, the class or mapping key being checked.

## Inspection And Validation

Use `comfy_validate_node_class` to check `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, and callable behavior. Use `comfy_validate_node_mappings` to verify `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`.

## Import Checks

Use `comfy_check_node_imports` before claiming the package loads. Import errors should be reported as diagnostics; they must not crash the MCP server. Generated docs should be deterministic and kept in the package.

## Complete Local Loop

Use `comfy_generate_node_examples` after static validation to build deterministic inputs for scalar and enum fields. The result is `generated` when all required inputs can be represented locally, and `blocked` when runtime-only inputs such as `IMAGE`, `LATENT`, `MODEL`, `CLIP`, `VAE`, or `CONDITIONING` require live ComfyUI values.

Use `comfy_run_node_contract_tests` only after examples are `generated`. The runner imports the package in an isolated subprocess, instantiates the mapped class, calls the method named by `FUNCTION`, and verifies the result is a tuple whose length matches `RETURN_TYPES`. Contract status is `passed`, `blocked`, or `failed`.

Use `comfy_custom_node_repair_guidance` after each iteration. A `ready` result means static validation and import checks are clear. `needs_work` means the package can be repaired locally. `blocked` means import or contract blockers must be fixed before the node loop can continue.
