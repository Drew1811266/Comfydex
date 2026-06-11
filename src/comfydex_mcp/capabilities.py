from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .generation import plan_workflow_generation
from .node_semantics import match_semantics_to_object_info


MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
MODEL_PARAMETER_TYPES = {
    "checkpoint_name": "checkpoint",
    "lora_name": "lora",
    "controlnet_name": "controlnet",
    "upscale_model_name": "upscale",
    "vae_name": "vae",
}


def infer_model_type(path: Path) -> str:
    parts = {part.casefold() for part in path.parts}
    filename = path.name.casefold()

    if {"checkpoints", "checkpoint", "ckpt"} & parts:
        return "checkpoint"
    if {"loras", "lora"} & parts:
        return "lora"
    if {"controlnet", "controlnets", "control_net"} & parts:
        return "controlnet"
    if {"upscale_models", "upscalers", "upscale"} & parts:
        return "upscale"
    if {"vae", "vaes"} & parts:
        return "vae"
    if (
        "ipadapter" in filename
        or "ip-adapter" in filename
        or "ip_adapter" in filename
        or "adapter_ip" in filename
    ):
        return "ipadapter"
    return "unknown"


def scan_model_inventory(model_roots: list[Path]) -> dict[str, Any]:
    roots: list[str] = []
    missing_roots: list[str] = []
    models: list[dict[str, Any]] = []

    for root in model_roots:
        resolved = root.expanduser().resolve()
        if not resolved.is_dir():
            missing_roots.append(str(resolved))
            continue
        roots.append(str(resolved))
        for candidate in sorted(resolved.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.suffix.casefold() not in MODEL_EXTENSIONS:
                continue
            models.append(
                {
                    "filename": candidate.name,
                    "path": str(candidate.resolve()),
                    "model_type": infer_model_type(candidate),
                    "size_bytes": candidate.stat().st_size,
                }
            )

    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in sorted(models, key=lambda model: (model["model_type"], model["filename"])):
        by_type.setdefault(item["model_type"], []).append(item)

    return {
        "roots": roots,
        "missing_roots": missing_roots,
        "model_count": len(models),
        "models": sorted(models, key=lambda model: (model["model_type"], model["filename"])),
        "by_type": by_type,
    }


def node_inventory_from_object_info(object_info: Any) -> dict[str, Any]:
    node_types = sorted(key for key in object_info if isinstance(key, str)) if isinstance(object_info, dict) else []
    return {
        "node_count": len(node_types),
        "node_types": node_types,
        "semantic_match": match_semantics_to_object_info(object_info),
    }


def resolve_capabilities(
    intent: str,
    parameters: dict[str, Any] | None,
    object_info: dict[str, Any],
    model_inventory: dict[str, Any],
    *,
    template_id: str | None = None,
) -> dict[str, Any]:
    plan = plan_workflow_generation(intent, parameters, template_id)
    node_inventory = node_inventory_from_object_info(object_info)
    missing_nodes = _missing_required_nodes(plan, object_info)
    missing_models = _missing_required_models(plan, model_inventory)
    missing_information = list(plan.get("missing_information", []))
    can_run_now = not missing_nodes and not missing_models and not missing_information

    return {
        "status": "ready" if can_run_now else "missing_requirements",
        "can_run_now": can_run_now,
        "plan": plan,
        "node_inventory": node_inventory,
        "model_inventory": model_inventory,
        "missing_nodes": missing_nodes,
        "missing_models": missing_models,
        "missing_information": missing_information,
    }


def _missing_required_nodes(
    plan: dict[str, Any],
    object_info: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {"node_type": node_type, "reason": "missing_object_info"}
        for node_type in plan.get("required_nodes", [])
        if isinstance(node_type, str) and node_type not in object_info
    ]


def _missing_required_models(
    plan: dict[str, Any],
    model_inventory: dict[str, Any],
) -> list[dict[str, str]]:
    parameters = plan.get("parameters", {})
    missing: list[dict[str, str]] = []
    for parameter, model_type in MODEL_PARAMETER_TYPES.items():
        filename = parameters.get(parameter) if isinstance(parameters, dict) else None
        if not isinstance(filename, str) or not filename.strip():
            continue
        if not _inventory_has_model(model_inventory, model_type, filename):
            missing.append(
                {
                    "parameter": parameter,
                    "filename": filename,
                    "model_type": model_type,
                    "reason": "missing_model",
                }
            )
    return missing


def _inventory_has_model(
    model_inventory: dict[str, Any],
    model_type: str,
    filename: str,
) -> bool:
    expected = filename.casefold()
    by_type = model_inventory.get("by_type", {})
    candidates = by_type.get(model_type, []) if isinstance(by_type, dict) else []
    for item in candidates:
        if isinstance(item, dict) and str(item.get("filename", "")).casefold() == expected:
            return True
    return False


def create_install_plan(capability_report: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for model in capability_report.get("missing_models", []):
        if not isinstance(model, dict):
            continue
        actions.append(
            {
                "kind": "model",
                "target_type": str(model.get("model_type", "unknown")),
                "filename": str(model.get("filename", "")),
                "parameter": str(model.get("parameter", "")),
                "reason": str(model.get("reason", "missing_model")),
                "requires_confirmation": True,
                "automatic": False,
            }
        )
    for node in capability_report.get("missing_nodes", []):
        if not isinstance(node, dict):
            continue
        actions.append(
            {
                "kind": "custom_node",
                "node_type": str(node.get("node_type", "")),
                "reason": str(node.get("reason", "missing_object_info")),
                "restart_required": True,
                "requires_confirmation": True,
                "automatic": False,
            }
        )

    return {
        "status": "requires_confirmation" if actions else "not_required",
        "automatic": False,
        "requires_confirmation": bool(actions),
        "actions": actions,
    }


def append_install_audit(
    workspace: Path,
    install_plan: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "decision": decision,
        "plan": install_plan,
    }
    audit_path = _install_audit_path(workspace)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_install_audit(workspace: Path, limit: int = 20) -> dict[str, Any]:
    audit_path = _install_audit_path(workspace)
    if not audit_path.is_file():
        return {"path": str(audit_path), "entries": []}

    entries: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    if limit <= 0:
        return {"path": str(audit_path), "entries": []}
    return {"path": str(audit_path), "entries": entries[-limit:]}


def _install_audit_path(workspace: Path) -> Path:
    return workspace.resolve() / ".comfydex" / "install_audit.jsonl"
