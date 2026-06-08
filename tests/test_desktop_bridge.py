from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from comfydex_mcp.config import ComfydexConfig, save_config
from comfydex_mcp.core.indexer import reindex_project
from comfydex_mcp.core.project import project_context_from_config
from comfydex_mcp.desktop_bridge import main, run_bridge_operation
from comfydex_mcp.runs import create_run, register_outputs, update_status
from comfydex_mcp.workflows import save_workflow


API_WORKFLOW = {
    "3": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sdxl.safetensors"},
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "cinematic cat", "clip": ["3", 1]},
    },
    "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
}


def _config(tmp_path: Path) -> ComfydexConfig:
    return ComfydexConfig(
        workspace=tmp_path,
        base_url="http://127.0.0.1:8188",
        workflows_dir=tmp_path / "workflows",
        runs_dir=tmp_path / "runs",
        headers={"Authorization": "secret"},
        request_timeout_seconds=30,
        websocket_timeout_seconds=600,
    )


def _write_workspace(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    save_config(cfg)
    save_workflow(cfg.workflows_dir, "cat.json", API_WORKFLOW)
    run = create_run(
        cfg.runs_dir,
        "cat.json",
        API_WORKFLOW,
        cfg.base_url,
        "prompt-1",
        now=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )
    update_status(cfg.runs_dir, run["run_id"], "completed")
    output_path = cfg.runs_dir / run["run_id"] / "outputs" / "images" / "cat.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("image", encoding="utf-8")
    register_outputs(
        cfg.runs_dir,
        run["run_id"],
        [
            {
                "filename": "cat.png",
                "type": "images",
                "subfolder": "images",
                "downloaded_path": str(output_path),
            }
        ],
    )
    reindex_project(project_context_from_config(cfg))


def test_bridge_project_status_returns_success_envelope(tmp_path: Path):
    _write_workspace(tmp_path)

    result = run_bridge_operation("project_status", tmp_path)

    assert result["ok"] is True
    assert result["data"]["workspace"] == str(tmp_path.resolve())
    assert result["data"]["counts"]["assets"] == 1


def test_bridge_get_config_redacts_headers(tmp_path: Path):
    _write_workspace(tmp_path)

    result = run_bridge_operation("get_config", tmp_path)

    assert result["ok"] is True
    assert result["data"]["headers"] == {"Authorization": "<redacted>"}


def test_bridge_lists_workflows_runs_and_assets(tmp_path: Path):
    _write_workspace(tmp_path)

    workflows = run_bridge_operation("list_workflows", tmp_path)
    runs = run_bridge_operation("list_runs", tmp_path)
    assets = run_bridge_operation(
        "search_assets",
        tmp_path,
        {"query": "cinematic"},
    )

    assert workflows["data"][0]["name"] == "cat.json"
    assert runs["data"][0]["workflow_name"] == "cat.json"
    assert assets["data"]["total"] == 1


def test_bridge_unknown_operation_returns_error_envelope(tmp_path: Path):
    result = run_bridge_operation("missing", tmp_path)

    assert result["ok"] is False
    assert result["error"]["type"] == "ValueError"


def test_bridge_cli_prints_json(capsys, tmp_path: Path):
    _write_workspace(tmp_path)

    exit_code = main(["project_status", "--workspace", str(tmp_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["data"]["counts"]["assets"] == 1
