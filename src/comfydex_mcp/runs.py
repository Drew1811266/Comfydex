from __future__ import annotations

import json
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import ensure_directory, is_redirected_path

RUN_STATUSES = {"queued", "running", "completed", "failed", "cancelled", "unknown"}
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


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


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty safe identifier")
    if Path(run_id).is_absolute() or run_id != Path(run_id).name:
        raise ValueError("run_id must be a single safe path segment")
    if run_id in {".", ".."} or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run_id must be a single safe path segment")
    return run_id


def _run_dir(runs_dir: Path, run_id: str) -> Path:
    base = runs_dir.resolve()
    safe_run_id = validate_run_id(run_id)
    target = base / safe_run_id
    if is_redirected_path(target):
        raise ValueError("run directory must not be redirected")
    if target.exists():
        try:
            target.resolve().relative_to(base)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("run_id must stay inside runs_dir") from exc
    return target


def run_dir_path(runs_dir: Path, run_id: str) -> Path:
    return _run_dir(runs_dir, run_id)


def _record_path(runs_dir: Path, run_id: str) -> Path:
    path = _run_dir(runs_dir, run_id) / "run.json"
    if is_redirected_path(path):
        raise ValueError("run.json must stay inside run directory")
    if path.exists():
        base = runs_dir.resolve()
        try:
            path.resolve().relative_to(base)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("run.json must stay inside runs_dir") from exc
    return path


def has_safe_run_record(runs_dir: Path, run_id: str) -> bool:
    try:
        path = _record_path(runs_dir, run_id)
        path_stat = path.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        return False
    return stat.S_ISREG(path_stat.st_mode)


def _create_unique_run_dir(runs_dir: Path, base_run_id: str) -> tuple[str, Path]:
    for index in range(1, 1000):
        run_id = base_run_id if index == 1 else f"{base_run_id}-{index}"
        directory = _run_dir(runs_dir, run_id)
        try:
            directory.mkdir()
            return run_id, directory
        except FileExistsError:
            continue
    raise RuntimeError(f"could not allocate a unique run_id for {base_run_id}")


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
    base_run_id = _run_id(created, label)
    ensured_runs_dir = ensure_directory(runs_dir)
    run_id, directory = _create_unique_run_dir(ensured_runs_dir, base_run_id)
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
    ensured_runs_dir = ensure_directory(runs_dir)
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(ensured_runs_dir.iterdir(), key=lambda path: str(path)):
        if not has_safe_run_record(ensured_runs_dir, run_dir.name):
            continue
        try:
            record = read_run(ensured_runs_dir, run_dir.name)
        except (OSError, ValueError, json.JSONDecodeError, KeyError):
            continue
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
