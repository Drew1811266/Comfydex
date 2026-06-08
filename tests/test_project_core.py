from pathlib import Path
from datetime import datetime, timezone
import sqlite3

from comfydex_mcp.batches import create_batch_record, update_batch_run
from comfydex_mcp.config import ComfydexConfig
from comfydex_mcp.core.database import migrate_project
from comfydex_mcp.core.indexer import reindex_project
from comfydex_mcp.core.project import project_status
from comfydex_mcp.core.project import project_context_from_config
from comfydex_mcp.core.schema import SCHEMA_VERSION
from comfydex_mcp.runs import create_run, register_outputs
from comfydex_mcp.workflows import save_workflow


API_WORKFLOW = {
    "3": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "model.safetensors"},
    },
    "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
}


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


def test_project_status_reports_zero_counts_before_reindex(tmp_path: Path):
    ctx = project_context_from_config(_config(tmp_path))
    status = project_status(ctx)

    assert status["database_exists"] is True
    assert status["schema_version"] == SCHEMA_VERSION
    assert status["counts"] == {
        "workflows": 0,
        "runs": 0,
        "outputs": 0,
        "batches": 0,
        "errors": 0,
    }


def test_reindex_project_indexes_workflows_runs_outputs_and_batches(tmp_path: Path):
    cfg = _config(tmp_path)
    save_workflow(
        cfg.workflows_dir,
        "text2img.json",
        API_WORKFLOW,
        source="generated",
        validation_status="valid",
    )
    run = create_run(
        cfg.runs_dir,
        "text2img.json",
        API_WORKFLOW,
        cfg.base_url,
        "prompt-1",
        now=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )
    output_path = cfg.runs_dir / run["run_id"] / "outputs" / "output" / "image.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("image", encoding="utf-8")
    register_outputs(
        cfg.runs_dir,
        run["run_id"],
        [
            {
                "filename": "image.png",
                "type": "output",
                "downloaded_path": str(output_path),
            }
        ],
    )
    batch = create_batch_record(
        cfg.runs_dir,
        "Batch",
        "text2img.json",
        [{"node_id": "3", "inputs": {"seed": 1}}],
        now=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )
    update_batch_run(cfg.runs_dir, batch["batch_id"], 0, run["run_id"], "completed")

    ctx = project_context_from_config(cfg)
    report = reindex_project(ctx)
    status = project_status(ctx)

    assert report["status"] == "completed"
    assert report["counts"] == {
        "workflows": 1,
        "runs": 1,
        "outputs": 1,
        "batches": 1,
        "errors": 0,
    }
    assert status["counts"] == report["counts"]


def test_reindex_project_records_corrupt_workflow_json_without_deleting_it(
    tmp_path: Path,
):
    cfg = _config(tmp_path)
    cfg.workflows_dir.mkdir(parents=True)
    corrupt = cfg.workflows_dir / "bad.json"
    corrupt.write_text("{", encoding="utf-8")

    ctx = project_context_from_config(cfg)
    report = reindex_project(ctx)

    assert report["status"] == "completed_with_errors"
    assert report["counts"]["workflows"] == 0
    assert report["counts"]["errors"] == 1
    assert report["errors"][0]["source_type"] == "workflow"
    assert Path(report["errors"][0]["path"]) == corrupt.resolve()
    assert corrupt.exists()


def test_reindex_project_removes_stale_rows_when_source_files_are_deleted(
    tmp_path: Path,
):
    cfg = _config(tmp_path)
    save_workflow(cfg.workflows_dir, "text2img.json", API_WORKFLOW)
    ctx = project_context_from_config(cfg)

    first = reindex_project(ctx)
    (cfg.workflows_dir / "text2img.json").unlink()
    second = reindex_project(ctx)

    assert first["counts"]["workflows"] == 1
    assert second["counts"]["workflows"] == 0
