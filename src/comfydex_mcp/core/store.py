from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        "workflows": int(db.execute("SELECT COUNT(*) FROM workflow_records").fetchone()[0]),
        "runs": int(db.execute("SELECT COUNT(*) FROM run_records").fetchone()[0]),
        "outputs": int(db.execute("SELECT COUNT(*) FROM output_records").fetchone()[0]),
        "assets": int(db.execute("SELECT COUNT(*) FROM asset_records").fetchone()[0]),
        "batches": int(db.execute("SELECT COUNT(*) FROM batch_records").fetchone()[0]),
        "errors": int(db.execute("SELECT COUNT(*) FROM index_errors").fetchone()[0]),
    }


def metadata_value(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute(
        "SELECT value FROM project_metadata WHERE key = ?",
        (key,),
    ).fetchone()
    return None if row is None else str(row["value"])


def set_metadata(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute(
        """
        INSERT INTO project_metadata(key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          value = excluded.value,
          updated_at = excluded.updated_at
        """,
        (key, value, _now()),
    )


def clear_index_errors(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM index_errors")


def record_index_error(
    db: sqlite3.Connection,
    source_type: str,
    source_id: str,
    path: Path,
    message: str,
) -> None:
    normalized_path = str(path.resolve())
    error_id = hashlib.sha256(
        f"{source_type}\0{source_id}\0{normalized_path}\0{message}".encode("utf-8")
    ).hexdigest()
    db.execute(
        """
        INSERT INTO index_errors(error_id, source_type, source_id, path, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(error_id) DO UPDATE SET
          message = excluded.message,
          created_at = excluded.created_at
        """,
        (error_id, source_type, source_id, normalized_path, message, _now()),
    )


def list_index_errors(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT error_id, source_type, source_id, path, message, created_at
        FROM index_errors
        ORDER BY source_type, source_id, path
        """
    ).fetchall()
    return [dict(row) for row in rows]


def replace_workflow_rows(db: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    db.execute("DELETE FROM workflow_records")
    db.executemany(
        """
        INSERT INTO workflow_records(
          name, path, kind, source, submit_ready, validation_status, node_count,
          node_types_json, model_references_json, updated_at, indexed_at,
          content_hash, valid_json, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["name"],
                row["path"],
                row["kind"],
                row["source"],
                1 if row["submit_ready"] else 0,
                row["validation_status"],
                row["node_count"],
                _json(row["node_types"]),
                _json(row["model_references"]),
                row["updated_at"],
                row["indexed_at"],
                row["content_hash"],
                1 if row["valid_json"] else 0,
                row.get("error"),
            )
            for row in rows
        ],
    )


def replace_run_rows(db: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    db.execute("DELETE FROM run_records")
    db.executemany(
        """
        INSERT INTO run_records(
          run_id, path, workflow_name, prompt_id, client_id, status, created_at,
          updated_at, output_count, event_count, indexed_at, content_hash,
          valid_json, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["run_id"],
                row["path"],
                row.get("workflow_name"),
                row.get("prompt_id"),
                row.get("client_id"),
                row["status"],
                row["created_at"],
                row["updated_at"],
                row["output_count"],
                row["event_count"],
                row["indexed_at"],
                row["content_hash"],
                1 if row["valid_json"] else 0,
                row.get("error"),
            )
            for row in rows
        ],
    )


def replace_output_rows(db: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    db.execute("DELETE FROM output_records")
    db.executemany(
        """
        INSERT INTO output_records(
          output_id, run_id, path, filename, type, subfolder, size_bytes,
          modified_time, downloaded_path, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["output_id"],
                row["run_id"],
                row["path"],
                row["filename"],
                row["type"],
                row["subfolder"],
                row["size_bytes"],
                row["modified_time"],
                row.get("downloaded_path"),
                row["indexed_at"],
            )
            for row in rows
        ],
    )


def existing_asset_annotations(db: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = db.execute(
        """
        SELECT asset_id, tags_json, rating, favorite, notes, updated_at
        FROM asset_records
        """
    ).fetchall()
    return {str(row["asset_id"]): dict(row) for row in rows}


def replace_asset_rows(db: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    db.execute("DELETE FROM asset_records")
    db.executemany(
        """
        INSERT INTO asset_records(
          asset_id, output_id, run_id, workflow_name, status, prompt_text,
          model_references_json, path, filename, type, subfolder, size_bytes,
          modified_time, content_hash, sidecar_path, thumbnail_path,
          thumbnail_status, tags_json, rating, favorite, notes, indexed_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["asset_id"],
                row["output_id"],
                row["run_id"],
                row.get("workflow_name"),
                row["status"],
                row["prompt_text"],
                _json(row["model_references"]),
                row["path"],
                row["filename"],
                row["type"],
                row["subfolder"],
                row["size_bytes"],
                row["modified_time"],
                row["content_hash"],
                row.get("sidecar_path"),
                row.get("thumbnail_path"),
                row["thumbnail_status"],
                row["tags_json"],
                row.get("rating"),
                1 if row["favorite"] else 0,
                row["notes"],
                row["indexed_at"],
                row["updated_at"],
            )
            for row in rows
        ],
    )


def replace_batch_rows(db: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    db.execute("DELETE FROM batch_records")
    db.executemany(
        """
        INSERT INTO batch_records(
          batch_id, path, label, workflow_name, status, created_at, updated_at,
          run_count, completed_count, failed_count, indexed_at, content_hash,
          valid_json, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["batch_id"],
                row["path"],
                row["label"],
                row["workflow_name"],
                row["status"],
                row["created_at"],
                row["updated_at"],
                row["run_count"],
                row["completed_count"],
                row["failed_count"],
                row["indexed_at"],
                row["content_hash"],
                1 if row["valid_json"] else 0,
                row.get("error"),
            )
            for row in rows
        ],
    )
