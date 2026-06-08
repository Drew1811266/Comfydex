from pathlib import Path
import sqlite3

from comfydex_mcp.config import ComfydexConfig
from comfydex_mcp.core.database import migrate_project
from comfydex_mcp.core.project import project_context_from_config
from comfydex_mcp.core.schema import SCHEMA_VERSION


def _config(tmp_path: Path) -> ComfydexConfig:
    return ComfydexConfig(
        workspace=tmp_path,
        base_url="http://127.0.0.1:8188",
        workflows_dir=tmp_path / "workflows",
        runs_dir=tmp_path / "runs",
        headers={},
        request_timeout_seconds=30,
        websocket_timeout_seconds=600,
    )


def test_project_context_derives_state_and_database_paths(tmp_path: Path):
    ctx = project_context_from_config(_config(tmp_path))

    assert ctx.workspace == tmp_path.resolve()
    assert ctx.workflows_dir == (tmp_path / "workflows").resolve()
    assert ctx.runs_dir == (tmp_path / "runs").resolve()
    assert ctx.state_dir == (tmp_path / ".comfydex").resolve()
    assert ctx.database_path == (tmp_path / ".comfydex" / "comfydex.db").resolve()


def test_migrate_project_creates_schema_and_is_idempotent(tmp_path: Path):
    ctx = project_context_from_config(_config(tmp_path))

    first = migrate_project(ctx)
    second = migrate_project(ctx)

    assert first["schema_version"] == SCHEMA_VERSION
    assert first["applied_migrations"] == [
        {"version": 1, "name": "initial_project_index"}
    ]
    assert second["schema_version"] == SCHEMA_VERSION
    assert second["applied_migrations"] == []
    assert ctx.database_path.is_file()

    with sqlite3.connect(ctx.database_path) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {
        "schema_migrations",
        "project_metadata",
        "workflow_records",
        "run_records",
        "output_records",
        "batch_records",
        "index_errors",
    } <= tables
