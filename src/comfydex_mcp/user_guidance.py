from __future__ import annotations

from collections import Counter
from typing import Any


MISSING_ITEM_ACTIONS = {
    "checkpoint_name": "Choose a checkpoint model",
    "positive_prompt": "Write the prompt",
    "negative_prompt": "Add a negative prompt or leave the default",
    "image": "Choose an input image",
    "lora_name": "Choose a LoRA file",
}

FAILURE_TITLES = {
    "missing_model": "A model is missing",
    "missing_node": "A required node is missing",
    "missing_outputs": "The run finished without saved outputs",
    "resource_failure": "The computer ran out of resources",
    "invalid_parameter": "A setting is not accepted by ComfyUI",
    "invalid_link": "The workflow wiring needs repair",
    "fetch_failure": "The output could not be downloaded",
    "execution_error": "ComfyUI stopped during the run",
    "unknown_failure": "The run needs review",
}


def explain_generation_plan_for_user(plan: dict[str, Any]) -> dict[str, Any]:
    parameters = _dict(plan.get("parameters"))
    missing = _string_list(plan.get("missing_information"))
    policy = _dict(plan.get("policy"))
    decision = str(policy.get("decision") or ("blocked" if missing else "allowed"))
    width = parameters.get("width")
    height = parameters.get("height")
    steps = parameters.get("steps")
    model = str(parameters.get("checkpoint_name") or "the selected model")
    size_text = (
        f"{width} x {height}"
        if isinstance(width, int) and isinstance(height, int)
        else "the default size"
    )
    step_text = f"{steps} steps" if isinstance(steps, int) else "the default step count"
    blocked = bool(missing) or decision == "blocked"
    title = "More information is needed" if blocked else "Ready to create an image"
    severity = "blocked" if blocked else "warn" if decision == "requires_confirmation" else "ok"

    return {
        "title": title,
        "summary": f"Comfydex will use {model} at {size_text} with {step_text}.",
        "severity": severity,
        "bullets": [
            f"Model: {model}",
            f"Image size: {size_text}",
            f"Sampling: {step_text}",
        ],
        "next_actions": _missing_actions(missing),
        "technical": {
            "template_id": plan.get("selected_template_id"),
            "mode": plan.get("mode"),
            "policy_decision": decision,
            "policy_reasons": _string_list(policy.get("reasons")),
            "missing_information": missing,
        },
    }


def explain_repair_plan_for_user(repair_plan: dict[str, Any]) -> dict[str, Any]:
    failure_class = str(repair_plan.get("failure_class") or "unknown_failure")
    retry = _dict(repair_plan.get("retry"))
    actions = _action_bullets(repair_plan.get("actions"))
    summary = str(repair_plan.get("summary") or FAILURE_TITLES.get(failure_class, "Review the run."))
    severity = "warn" if retry.get("supported") else "blocked"
    if failure_class in {"missing_model", "missing_node", "resource_failure"}:
        severity = "blocked"
    return {
        "title": FAILURE_TITLES.get(failure_class, FAILURE_TITLES["unknown_failure"]),
        "summary": summary,
        "severity": severity,
        "bullets": actions or [summary],
        "next_actions": _repair_next_actions(repair_plan),
        "technical": {
            "failure_class": failure_class,
            "retry_supported": bool(retry.get("supported")),
            "retry_operation": retry.get("operation"),
        },
    }


def explain_capability_report_for_user(report: dict[str, Any]) -> dict[str, Any]:
    missing_models = _missing_model_names(report.get("missing_models"))
    missing_nodes = _missing_node_names(report.get("missing_nodes"))
    missing_information = _string_list(report.get("missing_information"))
    ready = bool(report.get("can_run_now")) and not missing_models and not missing_nodes and not missing_information
    bullets = [f"Missing model: {name}" for name in missing_models]
    bullets.extend(f"Missing node: {name}" for name in missing_nodes)
    bullets.extend(f"Missing input: {name}" for name in missing_information)
    return {
        "title": "Ready to run" if ready else "Setup is needed first",
        "summary": (
            "Comfydex found the needed models and nodes."
            if ready
            else "Comfydex needs a few items before this request can run."
        ),
        "severity": "ok" if ready else "blocked",
        "bullets": bullets or ["No missing items were found."],
        "next_actions": _missing_actions(missing_information),
        "technical": {
            "status": report.get("status"),
            "missing_models": missing_models,
            "missing_nodes": missing_nodes,
            "missing_information": missing_information,
        },
    }


def summarize_assets_for_user(result: dict[str, Any]) -> dict[str, Any]:
    assets = [asset for asset in result.get("assets", []) if isinstance(asset, dict)]
    total = int(result.get("total") if isinstance(result.get("total"), int) else len(assets))
    favorite_count = sum(1 for asset in assets if asset.get("favorite") is True)
    ratings = [asset.get("rating") for asset in assets if isinstance(asset.get("rating"), int)]
    model_counts = Counter(
        model
        for asset in assets
        for model in _string_list(asset.get("model_references"))
    )
    top_models = [name for name, _count in model_counts.most_common(3)]
    title = f"{total} {_plural(total, 'output')} indexed" if total else "No outputs indexed"
    summary_parts = [f"{total} {_plural(total, 'output')} indexed"]
    summary_parts.append(f"{favorite_count} {_plural(favorite_count, 'favorite')}")
    if ratings:
        summary_parts.append(f"average rating {sum(ratings) / len(ratings):.1f}")
    bullets = [f"Model used: {model}" for model in top_models]
    if not bullets:
        bullets = ["No model references were indexed."]
    return {
        "title": title,
        "summary": "; ".join(summary_parts) + ".",
        "severity": "ok" if total else "warn",
        "bullets": bullets,
        "next_actions": [] if total else ["Run a workflow and reindex the project."],
        "technical": {
            "total": total,
            "asset_count": len(assets),
            "favorite_count": favorite_count,
            "top_models": top_models,
        },
    }


def explain_asset_comparison_for_user(comparison: dict[str, Any]) -> dict[str, Any]:
    differences = _dict(comparison.get("differences"))
    changed_fields = [
        name
        for name, value in differences.items()
        if isinstance(value, dict) and value.get("changed") is True
    ]
    changed = bool(changed_fields)
    return {
        "title": "Outputs are different" if changed else "Outputs match",
        "summary": (
            f"Changed fields: {', '.join(changed_fields)}."
            if changed
            else "The indexed metadata matches for the compared outputs."
        ),
        "severity": "warn" if changed else "ok",
        "bullets": [f"Changed: {field}" for field in changed_fields],
        "next_actions": [],
        "technical": {"changed_fields": changed_fields},
    }


def _missing_actions(missing: list[str]) -> list[str]:
    actions = [MISSING_ITEM_ACTIONS.get(name, f"Provide {name}") for name in missing]
    return list(dict.fromkeys(actions))


def _repair_next_actions(repair_plan: dict[str, Any]) -> list[str]:
    retry = _dict(repair_plan.get("retry"))
    if retry.get("supported"):
        return ["Review the repair actions, then retry the run."]
    return ["Resolve the listed issue, then generate again."]


def _action_bullets(actions: Any) -> list[str]:
    if not isinstance(actions, list):
        return []
    bullets: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        target = action.get("target") or action.get("filename") or action.get("node_type")
        kind = str(action.get("kind") or "action").replace("_", " ")
        if target:
            bullets.append(f"{kind}: {target}")
        else:
            bullets.append(kind)
    return bullets


def _missing_model_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            filename = item.get("filename")
            if isinstance(filename, str) and filename:
                names.append(filename)
    return names


def _missing_node_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            node_type = item.get("node_type")
            if isinstance(node_type, str) and node_type:
                names.append(node_type)
    return names


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _plural(count: int, singular: str) -> str:
    return singular if count == 1 else f"{singular}s"
