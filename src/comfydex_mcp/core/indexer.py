from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..batches import read_batch_record
from ..outputs import list_outputs
from ..paths import ensure_directory
from ..runs import read_run, validate_run_id
from ..workflows import read_workflow
from .database import connect_database, migrate_project
from .project import ProjectContext
from .schema import SCHEMA_VERSION
from .store import (
    clear_index_errors,
    counts,
    list_index_errors,
    record_index_error,
    replace_batch_rows,
    replace_output_rows,
    replace_run_rows,
    replace_workflow_rows,
    set_metadata,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iso_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _safe_iso_from_stat(path: Path) -> str:
    try:
        return _iso_from_timestamp(path.stat().st_mtime)
    except OSError:
        return _now()


def _as_text(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def _as_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _output_id(run_id: str, path: str) -> str:
    return _hash_text(f"{run_id}\0{Path(path).resolve()}")


def _output_rows(context: ProjectContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for output in list_outputs(context.runs_dir):
        path = str(Path(output["path"]).resolve())
        rows.append(
            {
                "output_id": _output_id(str(output["run_id"]), path),
                "run_id": str(output["run_id"]),
                "path": path,
                "filename": str(output["filename"]),
                "type": str(output.get("type") or "output"),
                "subfolder": str(output.get("subfolder") or ""),
                "size_bytes": int(output.get("size", 0)),
                "modified_time": float(output.get("modified_time", 0.0)),
                "downloaded_path": output.get("downloaded_path"),
                "indexed_at": _now(),
            }
        )
    return rows


def _record_scan_error(
    db,
    source_type: str,
    source_id: str,
    path: Path,
    exc: Exception,
) -> None:
    message = f"{exc.__class__.__name__}: {exc}"
    record_index_error(db, source_type, source_id, path, message)


def _safe_workflow_rows(context: ProjectContext, db) -> list[dict[str, Any]]:
    ensure_directory(context.workflows_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(context.workflows_dir.glob("*.json"), key=lambda item: item.name):
        try:
            rows.extend(_workflow_rows_for_file(context, path))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            _record_scan_error(db, "workflow", path.name, path, exc)
    return rows


def _workflow_rows_for_file(context: ProjectContext, path: Path) -> list[dict[str, Any]]:
    loaded = read_workflow(context.workflows_dir, path.name)
    summary = loaded.get("summary", {})
    metadata = loaded.get("metadata", {})
    return [
        {
            "name": path.name,
            "path": str(path.resolve()),
            "kind": _as_text(loaded.get("kind"), "unknown"),
            "source": _as_text(metadata.get("source"), "manual"),
            "submit_ready": bool(metadata.get("submit_ready")),
            "validation_status": _as_text(metadata.get("validation_status"), "unknown"),
            "node_count": int(summary.get("node_count", 0)),
            "node_types": summary.get("node_types", {}),
            "model_references": summary.get("model_references", []),
            "updated_at": _safe_iso_from_stat(path),
            "indexed_at": _now(),
            "content_hash": _hash_file(path),
            "valid_json": True,
            "error": None,
        }
    ]


def _safe_run_rows(context: ProjectContext, db) -> list[dict[str, Any]]:
    ensure_directory(context.runs_dir)
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(context.runs_dir.iterdir(), key=lambda item: item.name):
        if not run_dir.is_dir() or run_dir.name == ".batches":
            continue
        try:
            validate_run_id(run_dir.name)
        except ValueError:
            continue
        record_path = run_dir / "run.json"
        if not record_path.is_file():
            continue
        try:
            rows.extend(_run_rows_for_dir(context, run_dir, record_path))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            _record_scan_error(db, "run", run_dir.name, record_path, exc)
    return rows


def _run_rows_for_dir(
    context: ProjectContext,
    run_dir: Path,
    record_path: Path,
) -> list[dict[str, Any]]:
    record = read_run(context.runs_dir, run_dir.name)
    return [
        {
            "run_id": _as_text(record.get("run_id"), run_dir.name),
            "path": str(record_path.resolve()),
            "workflow_name": record.get("workflow_name"),
            "prompt_id": record.get("prompt_id"),
            "client_id": record.get("client_id"),
            "status": _as_text(record.get("status"), "unknown"),
            "created_at": _as_text(record.get("created_at"), _safe_iso_from_stat(record_path)),
            "updated_at": _as_text(record.get("updated_at"), _safe_iso_from_stat(record_path)),
            "output_count": _as_count(record.get("outputs")),
            "event_count": _as_count(record.get("events")),
            "indexed_at": _now(),
            "content_hash": _hash_file(record_path),
            "valid_json": True,
            "error": None,
        }
    ]


def _safe_batch_rows(context: ProjectContext, db) -> list[dict[str, Any]]:
    batches_dir = context.runs_dir / ".batches"
    if not batches_dir.is_dir():
        return []

    rows: list[dict[str, Any]] = []
    for batch_dir in sorted(batches_dir.iterdir(), key=lambda item: item.name):
        if not batch_dir.is_dir():
            continue
        record_path = batch_dir / "batch.json"
        if not record_path.is_file():
            continue
        try:
            rows.extend(_batch_rows_for_dir(context, batch_dir, record_path))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            _record_scan_error(db, "batch", batch_dir.name, record_path, exc)
    return rows


def _batch_rows_for_dir(
    context: ProjectContext,
    batch_dir: Path,
    record_path: Path,
) -> list[dict[str, Any]]:
    record = read_batch_record(context.runs_dir, batch_dir.name)
    runs = record.get("runs")
    run_items = [run for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []
    completed = [run for run in run_items if run.get("status") == "completed"]
    failed = [run for run in run_items if run.get("status") == "failed"]
    return [
        {
            "batch_id": _as_text(record.get("batch_id"), batch_dir.name),
            "path": str(record_path.resolve()),
            "label": _as_text(record.get("label"), "batch"),
            "workflow_name": _as_text(record.get("workflow_name"), ""),
            "status": _as_text(record.get("status"), "unknown"),
            "created_at": _as_text(record.get("created_at"), _safe_iso_from_stat(record_path)),
            "updated_at": _as_text(record.get("updated_at"), _safe_iso_from_stat(record_path)),
            "run_count": len(run_items),
            "completed_count": len(completed),
            "failed_count": len(failed),
            "indexed_at": _now(),
            "content_hash": _hash_file(record_path),
            "valid_json": True,
            "error": None,
        }
    ]


def reindex_project(
    context: ProjectContext,
    *,
    include_outputs: bool = True,
) -> dict[str, Any]:
    migration = migrate_project(context)
    with connect_database(context.database_path) as db:
        clear_index_errors(db)
        workflow_rows = _safe_workflow_rows(context, db)
        run_rows = _safe_run_rows(context, db)
        output_rows = _output_rows(context) if include_outputs else []
        batch_rows = _safe_batch_rows(context, db)

        replace_output_rows(db, [])
        replace_workflow_rows(db, workflow_rows)
        replace_run_rows(db, run_rows)
        if include_outputs:
            replace_output_rows(db, output_rows)
        replace_batch_rows(db, batch_rows)
        set_metadata(db, "last_reindexed_at", _now())

        current_counts = counts(db)
        errors = list_index_errors(db)

    return {
        "status": "completed" if current_counts["errors"] == 0 else "completed_with_errors",
        "database_path": str(context.database_path),
        "schema_version": migration.get("schema_version", SCHEMA_VERSION),
        "counts": current_counts,
        "errors": errors,
    }
