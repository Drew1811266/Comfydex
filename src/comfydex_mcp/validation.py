from __future__ import annotations

from typing import Any

PROBABLE_OUTPUT_NODE_TYPES = {"PreviewImage", "SaveAudio", "SaveImage"}


def _required_inputs(node_info: Any) -> dict[str, Any]:
    if not isinstance(node_info, dict):
        return {}
    input_info = node_info.get("input", {})
    if not isinstance(input_info, dict):
        return {}
    required = input_info.get("required", {})
    return required if isinstance(required, dict) else {}


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    )


def validate_api_workflow(
    workflow: dict[str, Any],
    object_info: dict[str, Any],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not isinstance(workflow, dict) or not workflow:
        return {
            "status": "invalid",
            "errors": [{"reason": "workflow_not_object"}],
            "warnings": warnings,
            "nodes_checked": 0,
        }

    node_ids = {str(node_id) for node_id in workflow}
    has_probable_output_node = False

    for node_id, node in workflow.items():
        node_id_text = str(node_id)
        if not isinstance(node, dict):
            errors.append({"node_id": node_id_text, "reason": "node_not_object"})
            continue

        class_type = node.get("class_type")
        if class_type in PROBABLE_OUTPUT_NODE_TYPES:
            has_probable_output_node = True

        if "class_type" not in node:
            errors.append({"node_id": node_id_text, "reason": "missing_class_type"})
            continue

        if class_type not in object_info:
            errors.append(
                {
                    "node_id": node_id_text,
                    "class_type": class_type,
                    "reason": "missing_object_info",
                }
            )
            continue

        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            errors.append({"node_id": node_id_text, "reason": "inputs_not_object"})
            continue

        for input_name in _required_inputs(object_info[class_type]):
            if input_name not in inputs:
                errors.append(
                    {
                        "node_id": node_id_text,
                        "class_type": class_type,
                        "input": input_name,
                        "reason": "missing_required_input",
                    }
                )

        for input_name, value in inputs.items():
            if _is_link(value) and value[0] not in node_ids:
                errors.append(
                    {
                        "node_id": node_id_text,
                        "input": input_name,
                        "target_node_id": value[0],
                        "reason": "broken_link",
                    }
                )

    if not has_probable_output_node:
        warnings.append({"reason": "no_probable_output_node"})

    return {
        "status": "invalid" if errors else "valid",
        "errors": errors,
        "warnings": warnings,
        "nodes_checked": len(workflow),
    }
