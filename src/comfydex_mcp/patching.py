from __future__ import annotations

from copy import deepcopy
from typing import Any

from .validation import validate_api_workflow


def patch_workflow(
    workflow: dict[str, Any],
    operations: list[dict[str, Any]],
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(workflow, dict):
        raise ValueError("workflow must be an object")
    if not isinstance(operations, list):
        raise ValueError("operations must be a list")

    patched = deepcopy(workflow)
    operations_applied: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("operation must be an object")

        op = operation.get("op")
        if op == "set_input":
            changes.append(_set_input(patched, operation))
            operations_applied.append(deepcopy(operation))
        elif op == "remove_input":
            changes.append(_remove_input(patched, operation))
            applied = deepcopy(operation)
            applied["status"] = "removed"
            operations_applied.append(applied)
        elif op == "add_node":
            changes.append(_add_node(patched, operation))
            operations_applied.append(deepcopy(operation))
        elif op == "add_link":
            changes.append(_add_link(patched, operation))
            operations_applied.append(deepcopy(operation))
        else:
            raise ValueError(f"unsupported operation: {op}")

    validation = (
        validate_api_workflow(patched, object_info)
        if object_info is not None
        else None
    )
    validation_status = validation["status"] if validation is not None else None

    status = "patched" if validation_status != "invalid" else "invalid"
    return {
        "report": {
            "status": status,
            "changes": changes,
            "errors": [],
        },
        "status": "patched" if validation_status != "invalid" else "invalid",
        "workflow": patched,
        "submit_ready": validation_status == "valid",
        "operations_applied": operations_applied,
        "validation": validation,
    }


def _set_input(workflow: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    node_id = _required_text(operation, "node_id")
    input_name = _required_text(operation, "input")
    if "value" not in operation:
        raise ValueError("set_input operation must include value")

    inputs = _node_inputs(workflow, node_id)
    old_value = deepcopy(inputs.get(input_name))
    inputs[input_name] = deepcopy(operation["value"])
    return {
        "op": "set_input",
        "node_id": node_id,
        "input": input_name,
        "old_value": old_value,
        "new_value": deepcopy(operation["value"]),
    }


def _remove_input(workflow: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    node_id = _required_text(operation, "node_id")
    input_name = _required_text(operation, "input")

    inputs = _node_inputs(workflow, node_id)
    if input_name not in inputs:
        raise ValueError(f"input not found: {input_name}")
    old_value = deepcopy(inputs[input_name])
    del inputs[input_name]
    return {
        "op": "remove_input",
        "node_id": node_id,
        "input": input_name,
        "old_value": old_value,
    }


def _add_node(workflow: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    node_id = _required_text(operation, "node_id")
    class_type = _required_text(operation, "class_type")
    inputs = operation.get("inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError("add_node operation inputs must be an object")
    if node_id in workflow:
        raise ValueError(f"node_id already exists: {node_id}")

    workflow[node_id] = {
        "class_type": class_type,
        "inputs": deepcopy(inputs),
    }
    return {
        "op": "add_node",
        "node_id": node_id,
        "class_type": class_type,
        "inputs": deepcopy(inputs),
    }


def _add_link(workflow: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    source_node_id = _required_text(operation, "source_node_id")
    target_node_id = _required_text(operation, "target_node_id")
    input_name = _required_text(operation, "input")
    output_slot = operation.get("output_slot")
    if not isinstance(output_slot, int) or isinstance(output_slot, bool) or output_slot < 0:
        raise ValueError("add_link operation output_slot must be a non-negative integer")
    source_node = workflow.get(source_node_id)
    if source_node is None:
        raise ValueError(f"source_node_id not found: {source_node_id}")
    if not isinstance(source_node, dict):
        raise ValueError("source node must be an object")

    inputs = _node_inputs(workflow, target_node_id)
    old_value = deepcopy(inputs.get(input_name))
    inputs[input_name] = [source_node_id, output_slot]
    return {
        "op": "add_link",
        "source_node_id": source_node_id,
        "output_slot": output_slot,
        "target_node_id": target_node_id,
        "input": input_name,
        "old_value": old_value,
        "new_value": [source_node_id, output_slot],
    }


def _node_inputs(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    node = workflow.get(node_id)
    if not isinstance(node, dict):
        raise ValueError(f"node_id not found: {node_id}")

    inputs = node.setdefault("inputs", {})
    if not isinstance(inputs, dict):
        raise ValueError(f"node inputs must be an object: {node_id}")
    return inputs


def _required_text(operation: dict[str, Any], field: str) -> str:
    value = operation.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"operation must include {field}")
    return value
