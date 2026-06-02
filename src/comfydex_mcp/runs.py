from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import ensure_directory

RUN_STATUSES = {"queued", "running", "completed", "failed", "cancelled", "unknown"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _run_id(now: datetime, label: str | None) -> str:
    prefix = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    if not label:
        return prefix
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", label.strip()).strip("-").lower()
    return f"{prefix}_{slug}" if slug else prefix


def _run_dir(runs_dir: Path, run_id: str) -> Path:
    base = runs_dir.resolve()
    target = (base / run_id).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("run_id must stay inside runs_dir")
    return target


def _record_path(runs_dir: Path, run_id: str) -> Path:
    return _run_dir(runs_dir, run_id) / "run.json"


def read_run(runs_dir: Path, run_id: str) -> dict[str, Any]:
    return json.loads(_record_path(runs_dir, run_id).read_text(encoding="utf-8"))


def write_run(runs_dir: Path, record: dict[str, Any]) -> None:
    path = _record_path(runs_dir, str(record["run_id"]))
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def create_run(
    runs_dir: Path,
    workflow_name: str,
    workflow_json: dict[str, Any],
    base_url: str,
    prompt_id: str | None = None,
    client_id: str | None = None,
    label: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    created = now or _now()
    run_id = _run_id(created, label)
    directory = _run_dir(ensure_directory(runs_dir), run_id)
    ensure_directory(directory)
    ensure_directory(directory / "outputs")
    (directory / "workflow.json").write_text(json.dumps(workflow_json, indent=2) + "\n", encoding="utf-8")
    record = {
        "run_id": run_id,
        "workflow_name": workflow_name,
        "prompt_id": prompt_id,
        "client_id": client_id,
        "base_url": base_url,
        "status": "queued",
        "created_at": _format_time(created),
        "updated_at": _format_time(created),
        "events": [],
        "outputs": [],
    }
    write_run(runs_dir, record)
    return record


def update_status(runs_dir: Path, run_id: str, status: str) -> dict[str, Any]:
    if status not in RUN_STATUSES:
        raise ValueError(f"unsupported run status: {status}")
    record = read_run(runs_dir, run_id)
    record["status"] = status
    record["updated_at"] = _format_time(_now())
    write_run(runs_dir, record)
    return record


def append_event(runs_dir: Path, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
    record = read_run(runs_dir, run_id)
    record.setdefault("events", []).append(event)
    record["updated_at"] = _format_time(_now())
    write_run(runs_dir, record)
    return record


def register_outputs(runs_dir: Path, run_id: str, outputs: list[dict[str, Any]]) -> dict[str, Any]:
    record = read_run(runs_dir, run_id)
    record["outputs"] = outputs
    record["updated_at"] = _format_time(_now())
    write_run(runs_dir, record)
    return record


def list_runs(runs_dir: Path) -> list[dict[str, Any]]:
    ensure_directory(runs_dir)
    rows: list[dict[str, Any]] = []
    for run_json in runs_dir.glob("*/run.json"):
        record = json.loads(run_json.read_text(encoding="utf-8"))
        rows.append(
            {
                "run_id": record["run_id"],
                "workflow_name": record.get("workflow_name"),
                "prompt_id": record.get("prompt_id"),
                "status": record.get("status", "unknown"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "output_count": len(record.get("outputs", [])),
            }
        )
    return sorted(rows, key=lambda row: row.get("updated_at") or "", reverse=True)
