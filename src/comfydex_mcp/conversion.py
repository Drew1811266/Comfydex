from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import ensure_directory, safe_auxiliary_json_path, safe_json_path
from .validation import validate_api_workflow

WIDGET_INPUT_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN", "BOOL"}


def _input_groups(node_info: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(node_info, dict):
        return {}, {}
    input_info = node_info.get("input", {})
    if not isinstance(input_info, dict):
        return {}, {}
    required = input_info.get("required", {})
    optional = input_info.get("optional", {})
    return (
        required if isinstance(required, dict) else {},
        optional if isinstance(optional, dict) else {},
    )


def _input_names(node_info: Any) -> list[str]:
    required, optional = _input_groups(node_info)

    names: list[str] = []
    for group in (required, optional):
        names.extend(str(name) for name in group)
    return names


def _ui_input_slots(raw_node: dict[str, Any], node_info: Any) -> list[str | None]:
    object_input_names = _input_names(node_info)
    ui_inputs = raw_node.get("inputs", [])
    if not isinstance(ui_inputs, list):
        return object_input_names

    slots: list[str | None] = []
    has_named_slot = False
    for ui_input in ui_inputs:
        input_name = (
            ui_input.get("name")
            if isinstance(ui_input, dict)
            else None
        )
        if isinstance(input_name, str) and input_name:
            slots.append(input_name)
            has_named_slot = True
        else:
            slots.append(None)

    if not has_named_slot:
        return object_input_names

    seen = {name for name in slots if name is not None}
    slots.extend(name for name in object_input_names if name not in seen)
    return slots


def _input_spec(node_info: Any, input_name: str) -> Any:
    required, optional = _input_groups(node_info)
    if input_name in required:
        return required[input_name]
    return optional.get(input_name)


def _is_required_input(node_info: Any, input_name: str) -> bool:
    required, _ = _input_groups(node_info)
    return input_name in required


def _has_input_name(node_info: Any, input_name: str) -> bool:
    required, optional = _input_groups(node_info)
    return input_name in required or input_name in optional


def _is_widget_compatible(node_info: Any, input_name: str) -> bool:
    spec = _input_spec(node_info, input_name)
    if isinstance(spec, str):
        return spec.upper() in WIDGET_INPUT_TYPES
    if not isinstance(spec, (list, tuple)) or not spec:
        return False

    first = spec[0]
    if isinstance(first, list):
        return True
    if isinstance(first, str):
        return first.upper() in WIDGET_INPUT_TYPES
    return False


def _widget_value_valid(spec: Any, value: Any) -> bool | None:
    if isinstance(spec, str):
        type_name = spec.upper()
    elif isinstance(spec, (list, tuple)) and spec:
        first = spec[0]
        if isinstance(first, list):
            return value in first
        if not isinstance(first, str):
            return None
        type_name = first.upper()
    else:
        return None

    if type_name == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "FLOAT":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        )
    if type_name in {"BOOL", "BOOLEAN"}:
        return isinstance(value, bool)
    if type_name == "STRING":
        return isinstance(value, str)
    return None


def _valid_slot(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _link_index(
    ui_workflow: dict[str, Any],
) -> tuple[dict[tuple[str, int], list[Any]], list[dict[str, Any]]]:
    links_by_target: dict[tuple[str, int], list[Any]] = {}
    gaps: list[dict[str, Any]] = []
    links = ui_workflow.get("links", [])
    if not isinstance(links, list):
        if "links" in ui_workflow:
            gaps.append({"reason": "links_not_list"})
        return links_by_target, gaps

    seen_link_ids: list[tuple[Any, tuple[str, int]]] = []
    for link in links:
        if not isinstance(link, list) or len(link) < 6:
            gaps.append({"reason": "malformed_link", "link": link})
            continue
        link_id = link[0]
        source_node_id = link[1]
        source_slot = link[2]
        target_node_id = link[3]
        target_slot = link[4]
        if not _valid_slot(source_slot) or not _valid_slot(target_slot):
            gaps.append(
                {
                    "link_id": link_id,
                    "source_node_id": str(source_node_id),
                    "source_slot": source_slot,
                    "target_node_id": str(target_node_id),
                    "target_slot": target_slot,
                    "reason": "malformed_link",
                }
            )
            continue
        target_key = (str(target_node_id), target_slot)
        existing_target = next(
            (
                existing_target
                for seen_link_id, existing_target in seen_link_ids
                if seen_link_id == link_id
            ),
            None,
        )
        if existing_target is not None:
            existing_target_node_id, existing_target_slot = existing_target
            gaps.append(
                {
                    "link_id": link_id,
                    "target_node_id": str(target_node_id),
                    "target_slot": target_slot,
                    "existing_target_node_id": existing_target_node_id,
                    "existing_target_slot": existing_target_slot,
                    "reason": "duplicate_link_id",
                }
            )
            continue
        else:
            seen_link_ids.append((link_id, target_key))
        link_value = [
            str(source_node_id),
            source_slot,
        ]
        if target_key in links_by_target:
            gaps.append(
                {
                    "link_id": link_id,
                    "source_node_id": str(source_node_id),
                    "source_slot": source_slot,
                    "target_node_id": str(target_node_id),
                    "target_slot": target_slot,
                    "existing_source": links_by_target[target_key],
                    "source": link_value,
                    "reason": "duplicate_target_link",
                }
            )
            continue
        links_by_target[target_key] = link_value
    return links_by_target, gaps


def _conversion_report_filename(source_name: str) -> str:
    if (
        not source_name
        or source_name != Path(source_name).name
        or not source_name.endswith(".json")
    ):
        raise ValueError("workflow filename must be a simple .json filename")
    return f"{Path(source_name).stem}.conversion.json"


def conversion_report_path(workflows_dir: Path, source_name: str) -> Path:
    return safe_auxiliary_json_path(
        workflows_dir,
        ".reports",
        _conversion_report_filename(source_name),
    )


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

    links_by_target, link_gaps = _link_index(
        ui_workflow if isinstance(ui_workflow, dict) else {}
    )
    gaps.extend(link_gaps)
    nodes_failed = 0
    input_slots_by_node: dict[str, list[str | None]] = {}
    seen_node_ids: set[str] = set()

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
        if node_id in seen_node_ids:
            nodes_failed += 1
            gaps.append(
                {
                    "node_id": node_id,
                    "node_type": raw_node.get("type"),
                    "reason": "duplicate_node_id",
                }
            )
            continue
        seen_node_ids.add(node_id)

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

        input_slots = _ui_input_slots(raw_node, node_info)
        input_slots_by_node[node_id] = input_slots
        widgets = raw_node.get("widgets_values", [])
        if not isinstance(widgets, list):
            widgets = []

        inputs: dict[str, Any] = {}
        widget_index = 0
        missing_required_links: set[str] = set()
        for input_slot, input_name in enumerate(input_slots):
            if input_name is None:
                continue
            if not _has_input_name(node_info, input_name):
                gaps.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "input": input_name,
                        "reason": "unknown_input_name",
                    }
                )
                continue
            link_value = links_by_target.get((node_id, input_slot))
            widget_compatible = _is_widget_compatible(node_info, input_name)
            if link_value is not None:
                if widget_compatible and widget_index < len(widgets):
                    widget_index += 1
                inputs[input_name] = link_value
                continue
            if widget_compatible and widget_index < len(widgets):
                widget_value = widgets[widget_index]
                inputs[input_name] = widget_value
                valid_widget = _widget_value_valid(
                    _input_spec(node_info, input_name),
                    widget_value,
                )
                if valid_widget is False:
                    gaps.append(
                        {
                            "node_id": node_id,
                            "node_type": node_type,
                            "input": input_name,
                            "value": widget_value,
                            "reason": "invalid_widget_value",
                        }
                    )
                widget_index += 1
                continue
            if (
                _is_required_input(node_info, input_name)
                and not widget_compatible
                and input_name not in missing_required_links
            ):
                gaps.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "input": input_name,
                        "reason": "missing_required_link",
                    }
                )
                missing_required_links.add(input_name)

        if widget_index < len(widgets):
            for widget_value in widgets[widget_index:]:
                gaps.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "value": widget_value,
                        "reason": "unmapped_widget_value",
                    }
                )

        draft_workflow[node_id] = {
            "class_type": node_type,
            "inputs": inputs,
        }

    for (target_node_id, target_slot), link_value in links_by_target.items():
        draft_node = draft_workflow.get(target_node_id)
        if draft_node is None:
            continue
        node_type = draft_node["class_type"]
        input_slots = input_slots_by_node.get(target_node_id, [])
        if target_slot >= len(input_slots) or input_slots[target_slot] is None:
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
    ensure_directory(workflows_dir / ".reports")
    path = safe_auxiliary_json_path(
        workflows_dir,
        ".reports",
        _conversion_report_filename(source_name),
    )
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
