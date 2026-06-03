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


def _input_spec(node_info: Any, input_name: str) -> Any:
    if not isinstance(node_info, dict):
        return None
    input_info = node_info.get("input", {})
    if not isinstance(input_info, dict):
        return None
    for group_name in ("required", "optional"):
        group = input_info.get(group_name, {})
        if isinstance(group, dict) and input_name in group:
            return group[input_name]
    return None


def _target_input_types(spec: Any) -> list[str] | None:
    if isinstance(spec, str) and spec:
        return [spec]
    if not isinstance(spec, (list, tuple)) or not spec:
        return None

    first = spec[0]
    if isinstance(first, str) and first:
        return [first]
    return None


def _source_output_type(source_info: Any, output_slot: int) -> str | None:
    if not isinstance(source_info, dict):
        return None
    outputs = source_info.get("output")
    if not isinstance(outputs, (list, tuple)) or output_slot >= len(outputs):
        return None
    output_type = outputs[output_slot]
    return output_type if isinstance(output_type, str) and output_type else None


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
        and value[1] >= 0
    )


def _is_link_reference(value: Any) -> bool:
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
    nodes_by_id = {str(node_id): node for node_id, node in workflow.items()}
    has_probable_output_node = False

    for node_id, node in workflow.items():
        node_id_text = str(node_id)
        if not isinstance(node, dict):
            errors.append({"node_id": node_id_text, "reason": "node_not_object"})
            continue

        if "class_type" not in node:
            errors.append({"node_id": node_id_text, "reason": "missing_class_type"})
            continue

        class_type = node["class_type"]
        if not isinstance(class_type, str):
            errors.append(
                {
                    "node_id": node_id_text,
                    "reason": "invalid_class_type",
                }
            )
            continue

        if class_type in PROBABLE_OUTPUT_NODE_TYPES:
            has_probable_output_node = True

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
            if not _is_link_reference(value):
                continue

            source_node_id = value[0]
            source_slot = value[1]
            if not _is_link(value):
                errors.append(
                    {
                        "node_id": node_id_text,
                        "input": input_name,
                        "target_node_id": source_node_id,
                        "output_slot": source_slot,
                        "reason": "invalid_output_slot",
                    }
                )
                continue

            if source_node_id not in node_ids:
                errors.append(
                    {
                        "node_id": node_id_text,
                        "input": input_name,
                        "target_node_id": source_node_id,
                        "reason": "broken_link",
                    }
                )
                continue

            source_node = nodes_by_id[source_node_id]
            if not isinstance(source_node, dict):
                continue
            source_type = source_node.get("class_type")
            if not isinstance(source_type, str):
                continue
            source_info = object_info.get(source_type)
            if not isinstance(source_info, dict):
                continue
            source_outputs = source_info.get("output")
            if isinstance(source_outputs, (list, tuple)) and source_slot >= len(
                source_outputs
            ):
                errors.append(
                    {
                        "node_id": node_id_text,
                        "input": input_name,
                        "target_node_id": source_node_id,
                        "output_slot": source_slot,
                        "reason": "invalid_output_slot",
                    }
                )
                continue

            source_output_type = _source_output_type(source_info, source_slot)
            target_types = _target_input_types(
                _input_spec(object_info[class_type], input_name)
            )
            if (
                source_output_type is not None
                and target_types is not None
                and source_output_type not in target_types
            ):
                errors.append(
                    {
                        "node_id": node_id_text,
                        "input": input_name,
                        "target_node_id": source_node_id,
                        "output_slot": source_slot,
                        "source_type": source_output_type,
                        "target_types": target_types,
                        "reason": "link_type_mismatch",
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
