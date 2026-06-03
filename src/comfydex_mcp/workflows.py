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


def workflow_metadata_filename(filename: str) -> str:
    if not filename or filename != Path(filename).name or not filename.endswith(".json"):
        raise ValueError("workflow filename must be a simple .json filename")
    return f"{Path(filename).stem}.metadata.json"


def workflow_metadata(
    filename: str,
    payload: dict[str, Any],
    *,
    source: str = "manual",
    validation_status: str = "unknown",
) -> dict[str, Any]:
    kind = classify_workflow(payload)
    actual_source = (
        "converted"
        if filename.endswith(".draft.json") and source == "manual"
        else source
    )
    submit_ready = kind == "api" and validation_status in {"unknown", "valid"}
    if actual_source == "converted" and validation_status != "valid":
        submit_ready = False
    return {
        "name": filename,
        "kind": kind,
        "source": actual_source,
        "submit_ready": submit_ready,
        "validation_status": validation_status,
    }


def save_workflow_metadata(
    workflows_dir: Path,
    filename: str,
    metadata: dict[str, Any],
) -> Path:
    metadata_dir = ensure_directory(workflows_dir / ".metadata")
    target = safe_json_path(metadata_dir, workflow_metadata_filename(filename))
    target.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return target


def read_workflow_metadata(
    workflows_dir: Path,
    filename: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    metadata_dir = workflows_dir / ".metadata"
    target = safe_json_path(metadata_dir, workflow_metadata_filename(filename))
    default = workflow_metadata(filename, payload)
    if not target.exists():
        return default

    try:
        saved = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    if not isinstance(saved, dict):
        return default

    saved_source = saved.get("source")
    source = saved_source if isinstance(saved_source, str) else default["source"]
    saved_validation_status = saved.get("validation_status")
    validation_status = (
        saved_validation_status
        if isinstance(saved_validation_status, str)
        else default["validation_status"]
    )
    merged = workflow_metadata(
        filename,
        payload,
        source=source,
        validation_status=validation_status,
    )
    saved_submit_ready = saved.get("submit_ready")
    if isinstance(saved_submit_ready, bool) and (
        saved_submit_ready is False or merged["submit_ready"] is True
    ):
        merged["submit_ready"] = saved_submit_ready
    return merged


def save_workflow(
    workflows_dir: Path,
    filename: str,
    payload: dict[str, Any],
    *,
    require_api: bool = False,
    source: str = "manual",
    validation_status: str = "unknown",
) -> Path:
    if require_api and classify_workflow(payload) != "api":
        raise ValueError("workflow must be ComfyUI API prompt JSON")
    ensure_directory(workflows_dir)
    target = safe_json_path(workflows_dir, filename)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    save_workflow_metadata(
        workflows_dir,
        filename,
        workflow_metadata(
            filename,
            payload,
            source=source,
            validation_status=validation_status,
        ),
    )
    return target


def read_workflow(workflows_dir: Path, filename: str) -> dict[str, Any]:
    target = safe_json_path(workflows_dir, filename)
    payload = json.loads(target.read_text(encoding="utf-8"))
    return {
        "name": filename,
        "path": str(target),
        "kind": classify_workflow(payload),
        "summary": summarize_workflow(payload),
        "metadata": read_workflow_metadata(workflows_dir, filename, payload),
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
