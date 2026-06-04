from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import ensure_directory, is_redirected_path

BATCH_RUN_STATUSES = {"queued", "running", "completed", "failed"}
_BATCH_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return _as_utc(value).isoformat()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_slug(value: str | None) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
    return slug or "batch"


def _batch_id(now: datetime, label: str | None) -> str:
    prefix = _as_utc(now).strftime("%Y-%m-%dT%H-%M-%S")
    return f"{prefix}_{_safe_slug(label)}"


def _validate_batch_id(batch_id: str) -> str:
    if not isinstance(batch_id, str) or not _BATCH_ID_PATTERN.fullmatch(batch_id):
        raise ValueError("batch_id must be a safe identifier")
    return batch_id


def _batches_dir(runs_dir: Path) -> Path:
    runs_base = ensure_directory(runs_dir).resolve()
    batches = runs_base / ".batches"
    if batches.exists() and is_redirected_path(batches):
        raise ValueError(".batches directory must stay inside runs_dir")
    ensure_directory(batches)
    resolved = batches.resolve()
    if not _is_relative_to(resolved, runs_base):
        raise ValueError(".batches directory must stay inside runs_dir")
    return resolved


def _batch_dir(runs_dir: Path, batch_id: str) -> Path:
    safe_batch_id = _validate_batch_id(batch_id)
    base = _batches_dir(runs_dir)
    target = (base / safe_batch_id).resolve()
    if not _is_relative_to(target, base):
        raise ValueError("batch_id must stay inside runs_dir/.batches")
    return target


def _record_path(runs_dir: Path, batch_id: str) -> Path:
    return _batch_dir(runs_dir, batch_id) / "batch.json"


def _write_batch_record(runs_dir: Path, record: dict[str, Any]) -> None:
    target = _record_path(runs_dir, str(record["batch_id"]))
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _create_unique_batch_dir(runs_dir: Path, base_batch_id: str) -> tuple[str, Path]:
    for index in range(1, 1000):
        batch_id = base_batch_id if index == 1 else f"{base_batch_id}-{index}"
        directory = _batch_dir(runs_dir, batch_id)
        try:
            directory.mkdir()
            return batch_id, directory
        except FileExistsError:
            continue
    raise RuntimeError(f"could not allocate a unique batch_id for {base_batch_id}")


def _summarize_status(runs: list[dict[str, Any]]) -> str:
    statuses = [str(run.get("status", "queued")) for run in runs]
    if statuses and all(status == "completed" for status in statuses):
        return "completed"
    if statuses and all(status == "failed" for status in statuses):
        return "failed"
    if any(status == "failed" for status in statuses):
        return "partial"
    if any(status == "running" for status in statuses):
        return "running"
    return "queued"


def create_batch_record(
    runs_dir: Path,
    label: str,
    workflow_name: str,
    variations: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(variations, list):
        raise ValueError("variations must be a list")
    if any(not isinstance(variation, dict) for variation in variations):
        raise ValueError("variations must contain objects")

    created = now or _now()
    base_batch_id = _batch_id(created, label)
    batch_id, directory = _create_unique_batch_dir(runs_dir, base_batch_id)
    record = {
        "batch_id": batch_id,
        "label": label,
        "workflow_name": workflow_name,
        "status": "queued",
        "created_at": _format_time(created),
        "updated_at": _format_time(created),
        "runs": [
            {
                "index": index,
                "parameters": deepcopy(variation),
                "status": "queued",
                "run_id": None,
            }
            for index, variation in enumerate(variations)
        ],
    }
    (directory / "batch.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def read_batch_record(runs_dir: Path, batch_id: str) -> dict[str, Any]:
    return json.loads(_record_path(runs_dir, batch_id).read_text(encoding="utf-8"))


def update_batch_run(
    runs_dir: Path,
    batch_id: str,
    index: int,
    run_id: str | None,
    status: str,
) -> dict[str, Any]:
    if status not in BATCH_RUN_STATUSES:
        raise ValueError(f"unsupported batch run status: {status}")
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValueError("batch run index must be an integer")
    if run_id is not None and not isinstance(run_id, str):
        raise ValueError("run_id must be a string or None")

    record = read_batch_record(runs_dir, batch_id)
    runs = record.get("runs")
    if not isinstance(runs, list):
        raise ValueError("batch record runs must be a list")
    if index < 0 or index >= len(runs):
        raise ValueError("batch run index out of range")
    if not isinstance(runs[index], dict):
        raise ValueError("batch run record must be an object")

    runs[index]["run_id"] = run_id
    runs[index]["status"] = status
    record["status"] = _summarize_status(runs)
    record["updated_at"] = _format_time(_now())
    _write_batch_record(runs_dir, record)
    return record


def variation_to_operations(variation: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(variation, dict):
        raise ValueError("variation must be an object")

    has_node_inputs = "node_id" in variation or "inputs" in variation
    has_changes = "changes" in variation
    if has_node_inputs and has_changes:
        raise ValueError("variation must use either node inputs or changes")
    if has_node_inputs:
        return _node_input_operations(variation)
    if has_changes:
        return _change_operations(variation)
    raise ValueError("variation must include node_id and inputs or changes")


def _normalize_node_id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("variation change must include node_id")
    node_id = str(value)
    if not node_id:
        raise ValueError("variation change must include node_id")
    return node_id


def _normalize_input_name(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("variation change must include input")
    return value


def _node_input_operations(variation: dict[str, Any]) -> list[dict[str, Any]]:
    node_id = _normalize_node_id(variation.get("node_id"))
    inputs = variation.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("variation inputs must be a non-empty object")

    operations: list[dict[str, Any]] = []
    for input_name in sorted(inputs):
        normalized_input = _normalize_input_name(input_name)
        operations.append(
            {
                "op": "set_input",
                "node_id": node_id,
                "input": normalized_input,
                "value": deepcopy(inputs[input_name]),
            }
        )
    return operations


def _change_operations(variation: dict[str, Any]) -> list[dict[str, Any]]:
    changes = variation.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("variation changes must be a non-empty list")

    operations: list[dict[str, Any]] = []
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("variation change must be an object")
        op = change.get("op")
        if op != "set_input":
            raise ValueError(f"unsupported variation change op: {op}")
        if "value" not in change:
            raise ValueError("set_input variation change must include value")
        operations.append(
            {
                "op": "set_input",
                "node_id": _normalize_node_id(change.get("node_id")),
                "input": _normalize_input_name(change.get("input")),
                "value": deepcopy(change["value"]),
            }
        )
    return operations
