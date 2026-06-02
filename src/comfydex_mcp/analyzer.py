from __future__ import annotations

from typing import Any

from .workflows import classify_workflow, summarize_workflow


def _extract_links(node_id: str, inputs: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for input_name, value in inputs.items():
        if (
            isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], int)
        ):
            links.append(
                {
                    "from_node": value[0],
                    "from_slot": value[1],
                    "to_node": node_id,
                    "input": input_name,
                }
            )
    return links


def analyze_workflow(
    workflow: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kind = classify_workflow(workflow)
    summary = summarize_workflow(workflow)
    object_info = object_info or {}
    missing_node_types: set[str] = set()
    input_issues: list[dict[str, str]] = []
    links: list[dict[str, Any]] = []
    potential_output_nodes: list[dict[str, str]] = []

    if kind == "api":
        for node_id, node in workflow.items():
            node_type = str(node.get("class_type", "unknown"))
            inputs = node.get("inputs", {})
            if not isinstance(inputs, dict):
                inputs = {}
            links.extend(_extract_links(node_id, inputs))
            if object_info and node_type not in object_info:
                missing_node_types.add(node_type)
            required = (
                object_info.get(node_type, {})
                .get("input", {})
                .get("required", {})
            )
            if isinstance(required, dict):
                for input_name in required:
                    if input_name not in inputs:
                        input_issues.append(
                            {
                                "node_id": node_id,
                                "node_type": node_type,
                                "missing_input": input_name,
                            }
                        )
            if node_type.lower().startswith("save") or "output" in node_type.lower():
                potential_output_nodes.append({"node_id": node_id, "node_type": node_type})

    return {
        "kind": kind,
        "summary": summary,
        "missing_node_types": sorted(missing_node_types),
        "input_issues": input_issues,
        "links": links,
        "potential_output_nodes": potential_output_nodes,
    }
