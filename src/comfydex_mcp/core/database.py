from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..paths import ensure_directory, is_redirected_path
from .project import ProjectContext
from .schema import MIGRATIONS, SCHEMA_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_database(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_migration_table(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          applied_at TEXT NOT NULL
        )
        """
    )


def migrate_project(context: ProjectContext) -> dict[str, Any]:
    ensure_directory(context.state_dir)
    if is_redirected_path(context.state_dir):
        raise ValueError("Comfydex state directory must not be redirected")
    context.database_path.relative_to(context.state_dir)

    applied: list[dict[str, Any]] = []
    with connect_database(context.database_path) as db:
        _ensure_migration_table(db)
        for migration in MIGRATIONS:
            row = db.execute(
                "SELECT version FROM schema_migrations WHERE version = ?",
                (migration["version"],),
            ).fetchone()
            if row is not None:
                continue
            db.executescript(str(migration["sql"]))
            db.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (migration["version"], migration["name"], _now()),
            )
            applied.append(
                {"version": migration["version"], "name": migration["name"]}
            )
        db.execute(
            """
            INSERT INTO project_metadata(key, value, updated_at)
            VALUES ('schema_version', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (str(SCHEMA_VERSION), _now()),
        )

    return {
        "database_path": str(context.database_path),
        "schema_version": SCHEMA_VERSION,
        "applied_migrations": applied,
    }
