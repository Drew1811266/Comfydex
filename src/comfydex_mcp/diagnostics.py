from __future__ import annotations

from typing import Any

SUMMARY_MAX_LENGTH = 360
EVENT_TEXT_MAX_LENGTH = 180
EVENT_TEXT_KEYS = ("error", "message", "status")
NESTED_TEXT_KEYS = ("error", "message", "status", "status_str", "exception_message")


def _shorten(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _extract_texts(value: Any, depth: int = 0) -> list[str]:
    if isinstance(value, str):
        text = _clean_text(value)
        return [text] if text else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict) and depth < 2:
        texts: list[str] = []
        for key in NESTED_TEXT_KEYS:
            if key in value:
                texts.extend(_extract_texts(value[key], depth + 1))
        return texts
    return []


def _event_texts(events: list[Any]) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        prefix = f"{event_type}: " if isinstance(event_type, str) and event_type else ""
        for key in EVENT_TEXT_KEYS:
            if key not in event:
                continue
            for text in _extract_texts(event[key]):
                entry = _shorten(prefix + text, EVENT_TEXT_MAX_LENGTH)
                if entry not in seen:
                    texts.append(entry)
                    seen.add(entry)
    return texts


def _events_from(run_record: Any) -> list[Any]:
    if not isinstance(run_record, dict):
        return []
    events = run_record.get("events", [])
    return events if isinstance(events, list) else []


def _missing_node_types(workflow: Any, object_info: Any) -> list[str]:
    if not isinstance(workflow, dict) or not isinstance(object_info, dict):
        return []

    missing: set[str] = set()
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if isinstance(class_type, str) and class_type and class_type not in object_info:
            missing.add(class_type)
    return sorted(missing)


def _format_missing_node_types(node_types: list[str]) -> str:
    visible = node_types[:5]
    suffix = f" (+{len(node_types) - len(visible)} more)" if len(node_types) > len(visible) else ""
    return f"Missing node types: {', '.join(visible)}{suffix}."


def _build_summary(run_id: Any, status: str, signals: list[str], missing_node_types: list[str], events: list[Any]) -> str:
    parts = [f"Run {run_id} status is {status}."]
    event_texts = _event_texts(events)
    if event_texts:
        parts.append("Events: " + "; ".join(event_texts[:3]) + ".")
    if missing_node_types:
        parts.append(_format_missing_node_types(missing_node_types))
    if "missing_outputs" in signals:
        parts.append("Completed run has no registered outputs.")
    return _shorten(" ".join(parts), SUMMARY_MAX_LENGTH)


def diagnose_run(
    run_record: dict[str, Any],
    workflow: dict[str, Any] | None = None,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_run_record = run_record if isinstance(run_record, dict) else {}
    events = _events_from(normalized_run_record)
    status_value = normalized_run_record.get("status", "unknown")
    status = status_value if isinstance(status_value, str) and status_value else "unknown"
    signals = {
        event["type"]
        for event in events
        if isinstance(event, dict) and isinstance(event.get("type"), str) and event["type"]
    }

    outputs = normalized_run_record.get("outputs")
    if status == "completed" and not outputs:
        signals.add("missing_outputs")

    missing_node_types = _missing_node_types(workflow, object_info)
    sorted_signals = sorted(signals)

    return {
        "run_id": normalized_run_record.get("run_id"),
        "status": status,
        "signals": sorted_signals,
        "missing_node_types": missing_node_types,
        "summary": _build_summary(
            normalized_run_record.get("run_id"), status, sorted_signals, missing_node_types, events
        ),
    }
