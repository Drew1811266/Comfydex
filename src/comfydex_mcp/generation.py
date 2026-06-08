from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .templates import get_workflow_template, list_workflow_templates

DEFAULT_CONSTRAINTS = {
    "allow_overwrite": False,
    "allow_batch": False,
    "max_steps": 60,
    "max_pixels": 1048576,
}

CONFIRMATION_ISSUES = {
    "batch_request",
    "object_info_unavailable",
    "unknown_validation",
    "missing_model",
    "missing_node",
    "high_step_count",
}

INT_PARAMETER_KEYS = {"width", "height", "steps", "seed"}
FLOAT_PARAMETER_KEYS = {
    "cfg",
    "denoise",
    "strength_model",
    "strength_clip",
    "control_strength",
}
TEXT_PARAMETER_KEYS = {
    "checkpoint_name",
    "positive_prompt",
    "negative_prompt",
    "lora_name",
    "image",
    "pose_image",
    "controlnet_name",
    "upscale_model_name",
    "output_prefix",
    "filename_prefix",
}

_KEYWORD_RULES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "controlnet-skeleton",
        (
            ("controlnet", "intent mentions controlnet"),
            ("pose", "intent mentions pose"),
            ("skeleton", "intent mentions skeleton"),
            ("openpose", "intent mentions openpose"),
        ),
    ),
    (
        "upscale",
        (
            ("upscale", "intent mentions upscale"),
            ("upscaler", "intent mentions upscale"),
            ("enlarge", "intent mentions enlarge"),
            ("enhance", "intent mentions enhance"),
        ),
    ),
    (
        "basic-image-to-image",
        (
            ("image to image", "intent mentions image-to-image"),
            ("image-to-image", "intent mentions image-to-image"),
            ("img2img", "intent mentions img2img"),
            ("variation", "intent mentions variation"),
        ),
    ),
    (
        "lora-text-to-image",
        (
            ("lora", "intent mentions lora"),
            ("loras", "intent mentions lora"),
        ),
    ),
    (
        "sdxl-text-to-image",
        (
            ("sdxl", "intent mentions sdxl"),
            ("xl", "intent mentions xl"),
        ),
    ),
    (
        "basic-text-to-image",
        (
            ("text to image", "intent mentions text-to-image"),
            ("text-to-image", "intent mentions text-to-image"),
            ("txt2img", "intent mentions txt2img"),
            ("prompt", "intent mentions prompt"),
            ("image", "intent mentions image"),
        ),
    ),
)


def normalize_constraints(constraints: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**DEFAULT_CONSTRAINTS, **deepcopy(constraints or {})}
    for key in ("allow_overwrite", "allow_batch"):
        merged[key] = _maybe_bool(merged[key])
    for key in ("max_steps", "max_pixels"):
        merged[key] = _maybe_int(merged[key])
    return merged


def normalize_parameters(parameters: dict[str, Any] | None) -> dict[str, Any]:
    _require_json_serializable(parameters or {})
    normalized = deepcopy(parameters or {})
    for key, value in list(normalized.items()):
        if key in INT_PARAMETER_KEYS:
            normalized[key] = _maybe_int(value)
        elif key in FLOAT_PARAMETER_KEYS:
            normalized[key] = _maybe_float(value)
        elif key in TEXT_PARAMETER_KEYS and isinstance(value, str):
            normalized[key] = " ".join(value.split())
    return normalized


def candidate_templates(
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
) -> list[dict[str, Any]]:
    normalized_parameters = normalize_parameters(parameters)
    if template_id is not None:
        get_workflow_template(template_id)
        return [
            {
                "template_id": template_id,
                "score": 1000,
                "reasons": ["explicit template_id"],
            }
        ]

    normalized_intent = intent.casefold()
    candidates = [
        _score_template(template, normalized_intent, normalized_parameters)
        for template in list_workflow_templates()
    ]
    return sorted(
        candidates,
        key=lambda candidate: (-candidate["score"], candidate["template_id"]),
    )


def plan_workflow_generation(
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidates = candidate_templates(intent, parameters, template_id)
    selected_template_id = str(candidates[0]["template_id"])
    template = get_workflow_template(selected_template_id)
    normalized_parameters = normalize_parameters(parameters)
    merged_parameters = {
        **deepcopy(template["parameters"]),
        **normalized_parameters,
    }
    missing_information = [
        input_name
        for input_name in template["required_inputs"]
        if not _has_parameter_value(merged_parameters, input_name)
    ]

    return {
        "intent": intent,
        "mode": _mode_from_template_id(selected_template_id),
        "selected_template_id": selected_template_id,
        "candidate_templates": candidates[:3],
        "template": template,
        "required_nodes": deepcopy(template["required_nodes"]),
        "parameters": merged_parameters,
        "constraints": normalize_constraints(constraints),
        "assumptions": deepcopy(template["assumptions"]),
        "missing_information": missing_information,
        "issues": [],
    }


def repair_plan_parameters(
    plan: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    parameters = deepcopy(plan.get("parameters", {}))
    constraints = normalize_constraints(plan.get("constraints", {}))
    repairs: list[dict[str, Any]] = []
    issues: list[str] = []

    steps = parameters.get("steps")
    max_steps = constraints["max_steps"]
    if isinstance(steps, int) and isinstance(max_steps, int) and steps > max_steps:
        parameters["steps"] = max_steps
        repairs.append(
            {
                "kind": "clamped_steps",
                "path": "parameters.steps",
                "before": steps,
                "after": max_steps,
            }
        )

    width = parameters.get("width")
    height = parameters.get("height")
    max_pixels = constraints["max_pixels"]
    if (
        isinstance(width, int)
        and isinstance(height, int)
        and isinstance(max_pixels, int)
        and width * height > max_pixels
    ):
        issues.append("pixel_count_exceeds_limit")

    return parameters, repairs, issues


def build_generated_workflow(
    plan: dict[str, Any],
    object_info: dict[str, Any],
    *,
    target_exists: bool = False,
    allow_draft: bool = False,
) -> dict[str, Any]:
    from .builder import build_workflow_from_plan

    constraints = normalize_constraints(plan.get("constraints", {}))
    repaired_parameters, repairs, issues = repair_plan_parameters(plan)
    repaired_plan = {
        **deepcopy(plan),
        "parameters": repaired_parameters,
        "constraints": constraints,
    }

    if issues:
        validation = _not_run_validation()
        policy = evaluate_submit_policy(
            validation=validation,
            submit_ready=False,
            constraints=constraints,
            target_exists=target_exists,
            issues=issues,
        )
        return {
            "status": "blocked",
            "submit_ready": False,
            "workflow": None,
            "validation": validation,
            "plan": repaired_plan,
            "gaps": [],
            "missing_information": deepcopy(plan.get("missing_information", [])),
            "repairs": repairs,
            "policy": policy,
        }

    result = build_workflow_from_plan(repaired_plan, object_info)
    policy = evaluate_submit_policy(
        validation=result["validation"],
        submit_ready=bool(result["submit_ready"]),
        constraints=constraints,
        target_exists=target_exists,
    )
    result["plan"] = repaired_plan
    result["repairs"] = repairs
    result["policy"] = policy
    if allow_draft and result.get("draft_workflow") is not None:
        result["draft_allowed"] = True
    return result


def evaluate_submit_policy(
    *,
    validation: dict[str, Any],
    submit_ready: bool,
    constraints: dict[str, Any],
    target_exists: bool = False,
    issues: list[str] | None = None,
) -> dict[str, Any]:
    normalized_constraints = normalize_constraints(constraints)
    reasons = list(issues or [])
    blocked = False
    requires_confirmation = False

    if any(reason in {"pixel_count_exceeds_limit"} for reason in reasons):
        blocked = True

    validation_status = validation.get("status")
    if validation_status != "valid" or not submit_ready:
        blocked = True
        if "validation_not_submit_ready" not in reasons:
            reasons.append("validation_not_submit_ready")

    if target_exists and not normalized_constraints["allow_overwrite"]:
        reasons.append("workflow_overwrite")
        if not blocked:
            requires_confirmation = True

    confirmation_reasons = {
        reason for reason in reasons if reason in CONFIRMATION_ISSUES
    }
    if normalized_constraints["allow_batch"]:
        confirmation_reasons.discard("batch_request")
    if confirmation_reasons and not blocked:
        requires_confirmation = True

    decision = (
        "blocked"
        if blocked
        else "requires_confirmation"
        if requires_confirmation
        else "allowed"
    )
    return {
        "decision": decision,
        "requires_confirmation": requires_confirmation,
        "blocked": blocked,
        "reasons": reasons,
        "risk_level": "high" if blocked else "medium" if requires_confirmation else "low",
    }


def _score_template(
    template: dict[str, Any],
    normalized_intent: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    template_id = str(template["id"])
    score = 0
    reasons: list[str] = []

    for rule_template_id, keyword_rules in _KEYWORD_RULES:
        if rule_template_id != template_id:
            continue
        for keyword, reason in keyword_rules:
            if keyword in normalized_intent:
                score += 50
                reasons.append(reason)

    for tag in template.get("tags", []):
        if isinstance(tag, str) and tag.casefold() in normalized_intent:
            score += 8
            reason = f"intent mentions tag {tag}"
            if reason not in reasons:
                reasons.append(reason)

    matched_inputs = [
        input_name
        for input_name in template.get("required_inputs", [])
        if input_name in parameters and _has_parameter_value(parameters, input_name)
    ]
    if matched_inputs:
        score += len(matched_inputs) * 6
        reasons.append("parameters match required inputs")

    if template_id == "basic-text-to-image":
        score += 1
        if not reasons:
            reasons.append("default text-to-image fallback")

    return {
        "template_id": template_id,
        "score": score,
        "reasons": reasons,
    }


def _mode_from_template_id(template_id: str) -> str:
    if template_id == "basic-image-to-image":
        return "image-to-image"
    if template_id == "upscale":
        return "upscale"
    if template_id == "controlnet-skeleton":
        return "controlnet"
    return "text-to-image"


def _maybe_int(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped)
    return value


def _maybe_float(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return value
    return value


def _maybe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return bool(value)


def _not_run_validation() -> dict[str, Any]:
    return {
        "status": "not_run",
        "errors": [],
        "warnings": [],
        "nodes_checked": 0,
    }


def _has_parameter_value(parameters: dict[str, Any], name: str) -> bool:
    if name not in parameters:
        return False
    value = parameters[name]
    return value is not None and value != ""


def _require_json_serializable(value: Any) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("parameters must be JSON serializable") from exc
