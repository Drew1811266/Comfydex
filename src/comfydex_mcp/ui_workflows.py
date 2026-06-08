from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .workflows import read_workflow, save_workflow


def classify_workflow_payload(payload: Any) -> dict[str, Any]:
    evidence: list[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("nodes"), list):
        evidence.append("nodes is a list")
        if isinstance(payload.get("links"), list):
            evidence.append("links is a list")
        return {"kind": "ui", "evidence": evidence}

    if isinstance(payload, dict) and payload and all(
        isinstance(value, dict) and "class_type" in value for value in payload.values()
    ):
        evidence.append("node values include class_type")
        return {"kind": "api", "evidence": evidence}

    return {
        "kind": "unknown",
        "evidence": ["payload did not match ui or api workflow shape"],
    }


def summarize_import_readiness(
    payload: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = classify_workflow_payload(payload)
    kind = classification["kind"]
    if kind != "ui":
        return {
            "kind": kind,
            "nodes_total": 0,
            "known_node_types": [],
            "unknown_node_types": [],
            "node_types": {},
            "conversion_ready": kind == "api",
        }

    node_types: Counter[str] = Counter()
    for node in payload.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_types[str(node.get("type", "unknown"))] += 1

    known_node_types = sorted(
        node_type for node_type in node_types if object_info and node_type in object_info
    )
    unknown_node_types = sorted(
        node_type
        for node_type in node_types
        if object_info is not None and node_type not in object_info
    )

    return {
        "kind": "ui",
        "nodes_total": sum(node_types.values()),
        "known_node_types": known_node_types,
        "unknown_node_types": unknown_node_types,
        "node_types": dict(sorted(node_types.items())),
        "conversion_ready": object_info is None or not unknown_node_types,
    }


def import_ui_workflow(
    workflows_dir: Path,
    filename: str,
    payload: dict[str, Any],
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = classify_workflow_payload(payload)
    if classification["kind"] != "ui":
        raise ValueError(
            "comfy_import_ui_workflow requires ComfyUI UI workflow JSON"
        )

    path = save_workflow(
        workflows_dir,
        filename,
        payload,
        source="imported",
        validation_status="unknown",
    )
    loaded = read_workflow(path.parent, path.name)
    return {
        "name": loaded["name"],
        "path": loaded["path"],
        "metadata": loaded["metadata"],
        "classification": classification,
        "readiness": summarize_import_readiness(payload, object_info),
    }
