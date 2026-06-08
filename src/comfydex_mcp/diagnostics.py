from __future__ import annotations

from typing import Any

from .workflows import summarize_workflow

SUMMARY_MAX_LENGTH = 360
EVENT_TEXT_MAX_LENGTH = 180
EVENT_TEXT_KEYS = ("error", "message", "messages", "status", "history_status")
NESTED_TEXT_KEYS = (
    "error",
    "message",
    "messages",
    "status",
    "status_str",
    "exception_message",
)
MODEL_REFERENCE_INPUT_MARKERS = ("model", "ckpt", "lora", "vae", "checkpoint", "clip", "unet", "control_net")
MODEL_ERROR_MARKERS = (
    "not found",
    "missing",
    "cannot find",
    "could not find",
    "failed to load",
    "no such file",
    "does not exist",
)
HISTORY_FAILURE_MARKERS = ("error", "exception", "failed", "failure")
HISTORY_SUCCESS_MARKERS = ("success", "completed", "complete")


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
    if isinstance(value, (list, tuple)) and depth < 2:
        texts = []
        for item in value:
            texts.extend(_extract_texts(item, depth + 1))
        return texts
    return []


def _collect_texts(value: Any, depth: int = 0) -> list[str]:
    if depth > 5:
        return []
    if isinstance(value, str):
        text = _clean_text(value)
        return [text] if text else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        texts: list[str] = []
        for item in value.values():
            texts.extend(_collect_texts(item, depth + 1))
        return texts
    if isinstance(value, (list, tuple)):
        texts = []
        for item in value:
            texts.extend(_collect_texts(item, depth + 1))
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


def _unique_texts(values: list[str], max_items: int = 5) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _shorten(_clean_text(value), EVENT_TEXT_MAX_LENGTH)
        if text and text not in seen:
            texts.append(text)
            seen.add(text)
        if len(texts) >= max_items:
            break
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


def _wait_payloads(run_record: dict[str, Any], events: list[Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    wait_result = run_record.get("wait_result")
    if isinstance(wait_result, dict):
        payloads.append(wait_result)
    for event in events:
        if isinstance(event, dict) and event.get("type") == "wait_result":
            payloads.append(event)
    return payloads


def _history_status_from_texts(texts: list[str]) -> str | None:
    lowered = [_clean_text(text).lower() for text in texts]
    if any(any(marker in text for marker in HISTORY_FAILURE_MARKERS) for text in lowered):
        return "failed"
    if any(any(marker in text for marker in HISTORY_SUCCESS_MARKERS) for text in lowered):
        return "completed"
    return None


def _history_status_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("history_status", "terminal_status"):
        value = payload.get(key)
        if isinstance(value, str):
            status = _history_status_from_texts([value])
            if status is not None:
                return status
    if payload.get("completed") is True:
        return "completed"
    return _history_status_from_texts(_collect_texts(payload))


def _workflow_model_references(
    workflow: Any,
    workflow_analysis: dict[str, Any] | None,
) -> list[str]:
    references: set[str] = set()
    if isinstance(workflow_analysis, dict):
        for container in (workflow_analysis, workflow_analysis.get("summary")):
            if not isinstance(container, dict):
                continue
            values = container.get("model_references")
            if isinstance(values, list):
                references.update(value for value in values if isinstance(value, str) and value)
    if isinstance(workflow, dict):
        try:
            summary = summarize_workflow(workflow)
        except Exception:
            summary = {}
        values = summary.get("model_references") if isinstance(summary, dict) else None
        if isinstance(values, list):
            references.update(value for value in values if isinstance(value, str) and value)
    return sorted(references)


def _missing_model_references(model_references: list[str], texts: list[str]) -> list[str]:
    lowered_texts = [text.lower() for text in texts]
    missing: set[str] = set()
    for reference in model_references:
        lowered_reference = reference.lower()
        for text in lowered_texts:
            if lowered_reference in text and any(marker in text for marker in MODEL_ERROR_MARKERS):
                missing.add(reference)
                break
    return sorted(missing)


def _run_record(run_record: Any) -> dict[str, Any]:
    return run_record if isinstance(run_record, dict) else {}


def _output_count(run_record: dict[str, Any]) -> int:
    outputs = run_record.get("outputs")
    return len(outputs) if isinstance(outputs, list) else 0


def _workflow_nodes(workflow: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(workflow, dict):
        return {}
    return {str(node_id): node for node_id, node in workflow.items() if isinstance(node, dict)}


def _node_inputs(node: dict[str, Any]) -> dict[str, Any]:
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        return {}
    return {str(input_name): value for input_name, value in inputs.items()}


def _node_sort_key(node_id: str) -> tuple[int, int | str, str]:
    try:
        return (0, int(node_id), node_id)
    except ValueError:
        return (1, node_id, node_id)


def _is_model_reference_input(input_name: str) -> bool:
    normalized = input_name.lower()
    return any(marker in normalized for marker in MODEL_REFERENCE_INPUT_MARKERS)


def _format_missing_node_types(node_types: list[str]) -> str:
    visible = node_types[:5]
    suffix = f" (+{len(node_types) - len(visible)} more)" if len(node_types) > len(visible) else ""
    return f"Missing node types: {', '.join(visible)}{suffix}."


def _build_summary(
    run_id: Any,
    status: str,
    signals: list[str],
    missing_node_types: list[str],
    events: list[Any],
    diagnostic_texts: list[str],
    missing_model_references: list[str],
) -> str:
    parts = [f"Run {run_id} status is {status}."]
    event_texts = _event_texts(events)
    if event_texts:
        parts.append("Events: " + "; ".join(event_texts[:3]) + ".")
    if diagnostic_texts:
        parts.append("Diagnostics: " + "; ".join(diagnostic_texts[:3]) + ".")
    if missing_node_types:
        parts.append(_format_missing_node_types(missing_node_types))
    if missing_model_references:
        parts.append(f"Missing model references: {', '.join(missing_model_references[:5])}.")
    if "missing_outputs" in signals:
        parts.append("Completed run has no registered outputs.")
    return _shorten(" ".join(parts), SUMMARY_MAX_LENGTH)


def diagnose_run(
    run_record: dict[str, Any],
    workflow: dict[str, Any] | None = None,
    object_info: dict[str, Any] | None = None,
    workflow_analysis: dict[str, Any] | None = None,
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
    wait_payloads = _wait_payloads(normalized_run_record, events)
    diagnostic_texts = _unique_texts(
        [text for payload in wait_payloads for text in _collect_texts(payload)]
    )
    history_status = None
    for payload in wait_payloads:
        if payload.get("fallback_used"):
            signals.add("fallback_used")
        payload_history_status = _history_status_from_payload(payload)
        if payload_history_status is not None:
            history_status = payload_history_status
            signals.add(f"history_{payload_history_status}")

    model_references = _workflow_model_references(workflow, workflow_analysis)
    missing_model_references = _missing_model_references(model_references, diagnostic_texts)
    if missing_model_references:
        signals.add("missing_model_reference")
    sorted_signals = sorted(signals)

    return {
        "run_id": normalized_run_record.get("run_id"),
        "status": status,
        "signals": sorted_signals,
        "missing_node_types": missing_node_types,
        "history_status": history_status,
        "model_references": model_references,
        "missing_model_references": missing_model_references,
        "summary": _build_summary(
            normalized_run_record.get("run_id"),
            status,
            sorted_signals,
            missing_node_types,
            events,
            diagnostic_texts,
            missing_model_references,
        ),
    }


def compare_runs(
    left_run: Any,
    right_run: Any,
    left_workflow: Any,
    right_workflow: Any,
) -> dict[str, Any]:
    left_record = _run_record(left_run)
    right_record = _run_record(right_run)
    left_status = left_record.get("status")
    right_status = right_record.get("status")
    left_output_count = _output_count(left_record)
    right_output_count = _output_count(right_record)

    left_nodes = _workflow_nodes(left_workflow)
    right_nodes = _workflow_nodes(right_workflow)
    left_node_ids = set(left_nodes)
    right_node_ids = set(right_nodes)
    common_node_ids = sorted(left_node_ids & right_node_ids, key=_node_sort_key)

    node_changes = [
        {"node_id": node_id, "change": "removed"}
        for node_id in sorted(left_node_ids - right_node_ids, key=_node_sort_key)
    ]
    node_changes.extend(
        {"node_id": node_id, "change": "added"}
        for node_id in sorted(right_node_ids - left_node_ids, key=_node_sort_key)
    )
    node_changes.sort(key=lambda change: (_node_sort_key(change["node_id"]), change["change"]))

    node_type_changes = []
    input_changes = []
    model_reference_changes = []

    for node_id in common_node_ids:
        left_node = left_nodes[node_id]
        right_node = right_nodes[node_id]
        left_class_type = left_node.get("class_type")
        right_class_type = right_node.get("class_type")
        if left_class_type != right_class_type:
            node_type_changes.append({"node_id": node_id, "left": left_class_type, "right": right_class_type})

        left_inputs = _node_inputs(left_node)
        right_inputs = _node_inputs(right_node)
        input_names = sorted(set(left_inputs) | set(right_inputs))
        for input_name in input_names:
            left_present = input_name in left_inputs
            right_present = input_name in right_inputs
            left_value = left_inputs[input_name] if left_present else None
            right_value = right_inputs[input_name] if right_present else None
            if left_present == right_present and left_value == right_value:
                continue
            change = {"node_id": node_id, "input": input_name, "left": left_value, "right": right_value}
            if left_present != right_present:
                change["left_present"] = left_present
                change["right_present"] = right_present
            input_changes.append(change)
            if _is_model_reference_input(input_name):
                model_reference_changes.append(dict(change))

    return {
        "left_run_id": left_record.get("run_id"),
        "right_run_id": right_record.get("run_id"),
        "status_changed": None
        if left_status == right_status
        else {"left": left_status, "right": right_status},
        "output_count_changed": None
        if left_output_count == right_output_count
        else {"left": left_output_count, "right": right_output_count},
        "input_changes": input_changes,
        "node_changes": node_changes,
        "node_type_changes": node_type_changes,
        "model_reference_changes": model_reference_changes,
    }
