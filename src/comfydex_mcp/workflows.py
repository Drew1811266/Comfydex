from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .paths import ensure_directory, safe_json_path

MODEL_KEYS = {
    "ckpt_name",
    "checkpoint",
    "lora_name",
    "vae_name",
    "model_name",
    "unet_name",
    "clip_name",
}
MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin")


def classify_workflow(payload: Any) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("nodes"), list):
        return "ui"
    if isinstance(payload, dict) and payload and all(
        isinstance(value, dict) and "class_type" in value for value in payload.values()
    ):
        return "api"
    return "unknown"


def summarize_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    node_types: Counter[str] = Counter()
    model_refs: list[str] = []
    kind = classify_workflow(payload)
    if kind == "unknown":
        return {"node_count": 0, "node_types": {}, "model_references": []}

    if kind == "api":
        for node in payload.values():
            node_type = str(node.get("class_type", "unknown"))
            node_types[node_type] += 1
            inputs = node.get("inputs", {})
            if isinstance(inputs, dict):
                for key, value in inputs.items():
                    if key in MODEL_KEYS and isinstance(value, str):
                        model_refs.append(value)

    if kind == "ui":
        for node in payload.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("type", "unknown"))
            node_types[node_type] += 1
            widgets = node.get("widgets_values", [])
            if isinstance(widgets, list):
                for value in widgets:
                    if isinstance(value, str) and value.lower().endswith(MODEL_EXTENSIONS):
                        model_refs.append(value)

    return {
        "node_count": sum(node_types.values()),
        "node_types": dict(sorted(node_types.items())),
        "model_references": sorted(set(model_refs)),
    }


def save_workflow(
    workflows_dir: Path,
    filename: str,
    payload: dict[str, Any],
    *,
    require_api: bool = False,
) -> Path:
    if require_api and classify_workflow(payload) != "api":
        raise ValueError("workflow must be ComfyUI API prompt JSON")
    ensure_directory(workflows_dir)
    target = safe_json_path(workflows_dir, filename)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def read_workflow(workflows_dir: Path, filename: str) -> dict[str, Any]:
    target = safe_json_path(workflows_dir, filename)
    payload = json.loads(target.read_text(encoding="utf-8"))
    return {
        "name": filename,
        "path": str(target),
        "kind": classify_workflow(payload),
        "summary": summarize_workflow(payload),
        "json": payload,
    }


def list_workflows(workflows_dir: Path) -> list[dict[str, Any]]:
    ensure_directory(workflows_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(workflows_dir.glob("*.json")):
        valid = True
        kind = "unknown"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            kind = classify_workflow(payload)
        except json.JSONDecodeError:
            valid = False
        rows.append(
            {
                "name": path.name,
                "relative_path": path.name,
                "modified_time": path.stat().st_mtime,
                "size": path.stat().st_size,
                "valid_json": valid,
                "kind": kind,
            }
        )
    return rows
