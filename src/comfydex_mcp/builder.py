from __future__ import annotations

from copy import deepcopy
from typing import Any

from .generation import plan_workflow_generation
from .validation import validate_api_workflow


def build_workflow_plan(
    intent: str,
    template_id: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return plan_workflow_generation(intent, parameters, template_id)


def build_workflow_from_template(
    template_id: str,
    parameters: dict[str, Any],
    object_info: dict[str, Any],
) -> dict[str, Any]:
    plan = build_workflow_plan("", template_id, parameters)
    return build_workflow_from_plan(plan, object_info)


def build_workflow_from_plan(
    plan: dict[str, Any],
    object_info: dict[str, Any],
) -> dict[str, Any]:
    missing_information = deepcopy(plan.get("missing_information", []))
    if missing_information:
        return _build_result(
            "missing_information",
            submit_ready=False,
            workflow=None,
            validation=_not_run_validation(),
            plan=plan,
            gaps=[],
            missing_information=missing_information,
        )

    template = plan.get("template")
    if not isinstance(template, dict):
        raise ValueError("plan must include a template")

    gaps = _object_info_gaps(template, object_info)
    if gaps:
        return _build_result(
            "missing_object_info",
            submit_ready=False,
            workflow=None,
            validation=_not_run_validation(),
            plan=plan,
            gaps=gaps,
            missing_information=missing_information,
        )

    workflow = _build_api_workflow(template, plan.get("parameters", {}))
    validation = validate_workflow_against_object_info(workflow, object_info)
    if validation["status"] != "valid":
        return _build_result(
            validation["status"],
            submit_ready=False,
            workflow=None,
            validation=validation,
            plan=plan,
            gaps=[],
            missing_information=missing_information,
            draft_workflow=workflow,
        )

    return _build_result(
        "valid",
        submit_ready=True,
        workflow=workflow,
        validation=validation,
        plan=plan,
        gaps=[],
        missing_information=missing_information,
    )


def validate_workflow_against_object_info(
    workflow: dict[str, Any],
    object_info: dict[str, Any],
) -> dict[str, Any]:
    return validate_api_workflow(workflow, object_info)


def _build_api_workflow(
    template: dict[str, Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    nodes = template.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("template nodes must be a list")

    key_to_id: dict[str, str] = {}
    workflow: dict[str, Any] = {}

    for index, node in enumerate(nodes, start=1):
        if not isinstance(node, dict):
            raise ValueError("template node must be an object")
        node_id = str(index)
        key = node.get("key")
        class_type = node.get("class_type")
        if not isinstance(key, str) or not isinstance(class_type, str):
            raise ValueError("template node must include key and class_type")

        key_to_id[key] = node_id
        workflow[node_id] = {
            "class_type": class_type,
            "inputs": _resolve_inputs(node.get("inputs", {}), parameters),
        }

    for link in template.get("links", []):
        if not isinstance(link, dict):
            raise ValueError("template link must be an object")
        try:
            source_id = key_to_id[link["from"]]
            target_id = key_to_id[link["to"]]
            input_name = link["input"]
            output_slot = link["output_slot"]
        except KeyError as exc:
            raise ValueError("template link references an unknown node") from exc

        if not isinstance(input_name, str) or not isinstance(output_slot, int):
            raise ValueError("template link must include input and output_slot")
        workflow[target_id]["inputs"][input_name] = [source_id, output_slot]

    return workflow


def _resolve_inputs(
    input_descriptors: Any,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(input_descriptors, dict):
        raise ValueError("template node inputs must be an object")

    inputs: dict[str, Any] = {}
    for input_name, descriptor in input_descriptors.items():
        if not isinstance(input_name, str):
            raise ValueError("template input name must be a string")
        inputs[input_name] = _resolve_input_descriptor(descriptor, parameters)
    return inputs


def _resolve_input_descriptor(descriptor: Any, parameters: dict[str, Any]) -> Any:
    if isinstance(descriptor, dict) and set(descriptor) == {"parameter"}:
        parameter_name = descriptor["parameter"]
        if not isinstance(parameter_name, str):
            raise ValueError("template parameter descriptor must name a string")
        if parameter_name not in parameters:
            raise ValueError(f"missing template parameter: {parameter_name}")
        return deepcopy(parameters[parameter_name])

    if isinstance(descriptor, dict) and set(descriptor) == {"value"}:
        return deepcopy(descriptor["value"])

    return deepcopy(descriptor)


def _object_info_gaps(
    template: dict[str, Any],
    object_info: dict[str, Any],
) -> list[dict[str, Any]]:
    required_nodes = template.get("required_nodes", [])
    if not isinstance(required_nodes, list):
        raise ValueError("template required_nodes must be a list")

    return [
        {"class_type": class_type, "reason": "missing_object_info"}
        for class_type in required_nodes
        if isinstance(class_type, str) and class_type not in object_info
    ]


def _not_run_validation() -> dict[str, Any]:
    return {
        "status": "not_run",
        "errors": [],
        "warnings": [],
        "nodes_checked": 0,
    }


def _build_result(
    status: str,
    *,
    submit_ready: bool,
    workflow: dict[str, Any] | None,
    validation: dict[str, Any],
    plan: dict[str, Any],
    gaps: list[dict[str, Any]],
    missing_information: list[str],
    draft_workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": status,
        "submit_ready": submit_ready,
        "workflow": workflow,
        "validation": validation,
        "plan": plan,
        "gaps": gaps,
        "missing_information": missing_information,
    }
    if draft_workflow is not None:
        result["draft_workflow"] = draft_workflow
    return result
