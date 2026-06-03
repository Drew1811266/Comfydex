from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import ensure_directory, safe_json_path
from .validation import validate_api_workflow


def _input_names(node_info: Any) -> list[str]:
    if not isinstance(node_info, dict):
        return []
    input_info = node_info.get("input", {})
    if not isinstance(input_info, dict):
        return []

    names: list[str] = []
    for group_name in ("required", "optional"):
        group = input_info.get(group_name, {})
        if isinstance(group, dict):
            names.extend(str(name) for name in group)
    return names


def _link_index(ui_workflow: dict[str, Any]) -> dict[tuple[str, int], list[Any]]:
    links_by_target: dict[tuple[str, int], list[Any]] = {}
    links = ui_workflow.get("links", [])
    if not isinstance(links, list):
        return links_by_target

    for link in links:
        if not isinstance(link, list) or len(link) < 6:
            continue
        source_node_id = link[1]
        source_slot = link[2]
        target_node_id = link[3]
        target_slot = link[4]
        if isinstance(target_slot, bool) or not isinstance(target_slot, int):
            continue
        links_by_target[(str(target_node_id), target_slot)] = [
            str(source_node_id),
            source_slot,
        ]
    return links_by_target


def _conversion_report_filename(source_name: str) -> str:
    if (
        not source_name
        or source_name != Path(source_name).name
        or not source_name.endswith(".json")
    ):
        raise ValueError("workflow filename must be a simple .json filename")
    return f"{Path(source_name).stem}.conversion.json"


def conversion_report_path(workflows_dir: Path, source_name: str) -> Path:
    reports_dir = workflows_dir / ".reports"
    return safe_json_path(reports_dir, _conversion_report_filename(source_name))


def convert_ui_to_api(
    ui_workflow: dict[str, Any],
    object_info: dict[str, Any],
    source_workflow: str,
    target_workflow: str,
) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    draft_workflow: dict[str, Any] = {}

    nodes = ui_workflow.get("nodes") if isinstance(ui_workflow, dict) else None
    if not isinstance(nodes, list):
        nodes = []
        gaps.append({"reason": "ui_nodes_not_list"})

    links_by_target = _link_index(ui_workflow if isinstance(ui_workflow, dict) else {})
    nodes_failed = 0

    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            nodes_failed += 1
            gaps.append({"reason": "node_not_object"})
            continue

        if "id" not in raw_node:
            nodes_failed += 1
            gaps.append(
                {
                    "node_type": raw_node.get("type"),
                    "reason": "missing_node_id",
                }
            )
            continue

        node_id = str(raw_node["id"])
        node_type = raw_node.get("type")
        if not isinstance(node_type, str) or not node_type:
            nodes_failed += 1
            gaps.append({"node_id": node_id, "reason": "missing_node_type"})
            continue

        node_info = object_info.get(node_type)
        if node_info is None:
            nodes_failed += 1
            gaps.append(
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "reason": "missing_object_info",
                }
            )
            continue

        input_names = _input_names(node_info)
        widgets = raw_node.get("widgets_values", [])
        if not isinstance(widgets, list):
            widgets = []

        inputs: dict[str, Any] = {}
        widget_index = 0
        for input_slot, input_name in enumerate(input_names):
            link_value = links_by_target.get((node_id, input_slot))
            if link_value is not None:
                inputs[input_name] = link_value
                continue
            if widget_index < len(widgets):
                inputs[input_name] = widgets[widget_index]
                widget_index += 1

        draft_workflow[node_id] = {
            "class_type": node_type,
            "inputs": inputs,
        }

    for (target_node_id, target_slot), link_value in links_by_target.items():
        draft_node = draft_workflow.get(target_node_id)
        if draft_node is None:
            continue
        node_type = draft_node["class_type"]
        input_names = _input_names(object_info.get(node_type))
        if target_slot >= len(input_names):
            gaps.append(
                {
                    "node_id": target_node_id,
                    "node_type": node_type,
                    "target_slot": target_slot,
                    "source": link_value,
                    "reason": "unmapped_link_slot",
                }
            )

    validation = validate_api_workflow(draft_workflow, object_info)
    for error in validation.get("errors", []):
        gaps.append({"reason": "validation_error", "details": error})

    nodes_converted = len(draft_workflow)
    if not gaps and validation.get("status") == "valid":
        status = "converted"
        workflow: dict[str, Any] | None = draft_workflow
    elif nodes_converted:
        status = "partial"
        workflow = None
    else:
        status = "failed"
        workflow = None

    report = {
        "source_workflow": source_workflow,
        "target_workflow": target_workflow,
        "status": status,
        "nodes_total": len(nodes),
        "nodes_converted": nodes_converted,
        "nodes_failed": nodes_failed,
        "gaps": gaps,
        "validation": validation,
    }
    return {
        "workflow": workflow,
        "draft_workflow": draft_workflow if draft_workflow else None,
        "report": report,
    }


def save_conversion_report(
    workflows_dir: Path,
    source_name: str,
    report: dict[str, Any],
) -> Path:
    reports_dir = ensure_directory(workflows_dir / ".reports")
    path = safe_json_path(reports_dir, _conversion_report_filename(source_name))
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def explain_conversion_gaps(report: dict[str, Any]) -> dict[str, Any]:
    gaps = report.get("gaps", [])
    if not isinstance(gaps, list):
        gaps = []

    if not gaps:
        summary = f"Conversion status is {report.get('status', 'unknown')} with no gaps."
    else:
        parts: list[str] = []
        for gap in gaps:
            if not isinstance(gap, dict):
                parts.append("unknown gap")
                continue

            reason = str(gap.get("reason", "unknown"))
            node_type = gap.get("node_type")
            node_id = gap.get("node_id")
            details = gap.get("details")
            if node_type:
                subject = f"{node_type}"
                if node_id is not None:
                    subject = f"{subject} node {node_id}"
                parts.append(f"{subject}: {reason}")
            elif isinstance(details, dict):
                detail_reason = details.get("reason", reason)
                detail_node = details.get("node_id")
                if detail_node is not None:
                    parts.append(f"node {detail_node}: validation {detail_reason}")
                else:
                    parts.append(f"validation {detail_reason}")
            else:
                parts.append(reason)
        summary = f"{len(gaps)} conversion gap(s): " + "; ".join(parts)

    return {
        "gap_count": len(gaps),
        "summary": summary,
        "gaps": gaps,
    }
