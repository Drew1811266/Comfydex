from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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


@contextmanager
def open_database(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect_database(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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


def _migration_statements(migration: dict[str, Any]) -> list[str]:
    statements = migration.get("statements")
    if isinstance(statements, list) and all(
        isinstance(statement, str) for statement in statements
    ):
        return [statement for statement in statements if statement.strip()]
    return [
        statement.strip()
        for statement in str(migration["sql"]).split(";")
        if statement.strip()
    ]


def migrate_project(context: ProjectContext) -> dict[str, Any]:
    ensure_directory(context.state_dir)
    if is_redirected_path(context.state_dir):
        raise ValueError("Comfydex state directory must not be redirected")
    context.database_path.relative_to(context.state_dir)

    applied: list[dict[str, Any]] = []
    with open_database(context.database_path) as db:
        db.execute("BEGIN")
        try:
            _ensure_migration_table(db)
            for migration in MIGRATIONS:
                row = db.execute(
                    "SELECT version FROM schema_migrations WHERE version = ?",
                    (migration["version"],),
                ).fetchone()
                if row is not None:
                    continue
                for statement in _migration_statements(migration):
                    db.execute(statement)
                db.execute(
                    """
                    INSERT INTO schema_migrations(version, name, applied_at)
                    VALUES (?, ?, ?)
                    """,
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
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {
        "database_path": str(context.database_path),
        "schema_version": SCHEMA_VERSION,
        "applied_migrations": applied,
    }
