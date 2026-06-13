from __future__ import annotations

from typing import Any

RESOURCE_MARKERS = ("out of memory", "cuda out of memory", "vram", "allocation")
INVALID_PARAMETER_MARKERS = ("invalid", "bad value", "not in list", "expected")
INVALID_LINK_MARKERS = ("link", "type mismatch", "cannot connect")


def classify_run_failure(
    diagnosis: dict[str, Any],
    *,
    stage: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    signals = _string_list(diagnosis.get("signals"))
    missing_models = _string_list(diagnosis.get("missing_model_references"))
    missing_nodes = _string_list(diagnosis.get("missing_node_types"))
    text = _failure_text(diagnosis, error)

    if missing_models:
        return _classification(
            "missing_model",
            False,
            f"Missing model references: {', '.join(missing_models[:5])}.",
        )
    if missing_nodes:
        return _classification(
            "missing_node",
            False,
            f"Missing node types: {', '.join(missing_nodes[:5])}.",
        )
    if "missing_outputs" in signals:
        return _classification(
            "missing_outputs",
            True,
            "The run completed without registered outputs; fetch outputs can be retried.",
        )
    if _contains_any(text, RESOURCE_MARKERS):
        return _classification(
            "resource_failure",
            True,
            "Reduce workload settings such as resolution, batch size, or steps before retrying.",
        )
    if _contains_any(text, INVALID_PARAMETER_MARKERS):
        return _classification(
            "invalid_parameter",
            True,
            "Review node parameter values against current ComfyUI object_info before retrying.",
        )
    if _contains_any(text, INVALID_LINK_MARKERS):
        return _classification(
            "invalid_link",
            True,
            "Inspect graph links and reconnect mismatched node outputs before retrying.",
        )
    if stage == "fetch":
        return _classification(
            "fetch_failure",
            True,
            "Output fetch failed; retry output fetch after checking file access.",
        )
    if any(signal in signals for signal in ("execution_error", "history_failed")):
        return _classification(
            "execution_error",
            True,
            "Inspect ComfyUI history and retry after addressing the execution error.",
        )
    if diagnosis.get("status") == "failed":
        return _classification(
            "execution_error",
            True,
            "Inspect the failed run and retry after addressing the execution error.",
        )
    return _classification(
        "unknown_failure",
        False,
        "No specific repair path is available from the current run evidence.",
    )


def build_run_repair_plan(
    run_id: str,
    diagnosis: dict[str, Any],
    *,
    workflow_name: str | None = None,
    stage: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    classification = classify_run_failure(diagnosis, stage=stage, error=error)
    failure_class = classification["failure_class"]
    actions = _actions_for_failure(failure_class, diagnosis)
    retry = _retry_for_failure(failure_class, run_id, workflow_name)
    status = (
        "retry_available"
        if retry["supported"]
        else "manual_action_required"
        if actions
        else "blocked"
    )
    return {
        "status": status,
        "run_id": run_id,
        "workflow_name": workflow_name,
        "failure_class": failure_class,
        "summary": classification["summary"],
        "actions": actions,
        "retry": retry,
    }


def _classification(
    failure_class: str,
    retryable: bool,
    summary: str,
) -> dict[str, Any]:
    return {
        "failure_class": failure_class,
        "retryable": retryable,
        "summary": summary,
    }


def _actions_for_failure(
    failure_class: str,
    diagnosis: dict[str, Any],
) -> list[dict[str, Any]]:
    if failure_class == "missing_model":
        models = _string_list(diagnosis.get("missing_model_references"))
        return [
            {
                "kind": "select_model",
                "target": model,
                "requires_confirmation": True,
                "automatic": False,
            }
            for model in models
        ]
    if failure_class == "missing_node":
        nodes = _string_list(diagnosis.get("missing_node_types"))
        return [
            {
                "kind": "install_node",
                "target": node_type,
                "requires_confirmation": True,
                "automatic": False,
            }
            for node_type in nodes
        ]
    if failure_class in {"missing_outputs", "fetch_failure"}:
        return [
            {
                "kind": "fetch_outputs",
                "requires_confirmation": False,
                "automatic": True,
            }
        ]
    if failure_class == "resource_failure":
        return [
            {
                "kind": "reduce_workload",
                "requires_confirmation": True,
                "automatic": False,
            }
        ]
    if failure_class == "invalid_parameter":
        return [
            {
                "kind": "adjust_parameter",
                "requires_confirmation": True,
                "automatic": False,
            }
        ]
    if failure_class == "invalid_link":
        return [
            {
                "kind": "inspect_links",
                "requires_confirmation": True,
                "automatic": False,
            }
        ]
    if failure_class == "execution_error":
        return [
            {
                "kind": "inspect_history",
                "requires_confirmation": False,
                "automatic": False,
            }
        ]
    return []


def _retry_for_failure(
    failure_class: str,
    run_id: str,
    workflow_name: str | None,
) -> dict[str, Any]:
    if failure_class in {"missing_outputs", "fetch_failure"}:
        return {
            "supported": True,
            "operation": "fetch_outputs",
            "arguments": {"run_id": run_id},
            "requires_confirmation": False,
        }
    if failure_class in {
        "resource_failure",
        "invalid_parameter",
        "invalid_link",
        "execution_error",
    }:
        arguments: dict[str, Any] = {"run_id": run_id}
        if workflow_name is not None:
            arguments["workflow_name"] = workflow_name
        return {
            "supported": True,
            "operation": "resubmit_workflow",
            "arguments": arguments,
            "requires_confirmation": True,
        }
    return {"supported": False}


def _failure_text(diagnosis: dict[str, Any], error: str | None) -> str:
    parts = []
    for key in ("summary", "repair_summary", "history_status", "status"):
        value = diagnosis.get(key)
        if isinstance(value, str):
            parts.append(value)
    if error:
        parts.append(error)
    return " ".join(parts).lower()


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]
