from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import respx

from comfydex_mcp import desktop_bridge
from comfydex_mcp.config import ComfydexConfig, save_config
from comfydex_mcp.batches import create_batch_record
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
UI_WORKFLOW = {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []}


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


def _add_second_asset(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    run = create_run(
        cfg.runs_dir,
        "cat.json",
        API_WORKFLOW,
        cfg.base_url,
        "prompt-2",
        now=datetime(2026, 6, 8, 1, tzinfo=timezone.utc),
    )
    update_status(cfg.runs_dir, run["run_id"], "completed")
    output_path = cfg.runs_dir / run["run_id"] / "outputs" / "images" / "cat-2.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("image-2", encoding="utf-8")
    register_outputs(
        cfg.runs_dir,
        run["run_id"],
        [
            {
                "filename": "cat-2.png",
                "type": "images",
                "subfolder": "images",
                "downloaded_path": str(output_path),
            }
        ],
    )
    reindex_project(project_context_from_config(cfg))


def _asset_ids(tmp_path: Path) -> list[str]:
    result = run_bridge_operation("search_assets", tmp_path, {"limit": 10})
    return [asset["asset_id"] for asset in result["data"]["assets"]]


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


@respx.mock
def test_bridge_check_connection_returns_desktop_connection_shape(tmp_path: Path):
    _write_workspace(tmp_path)
    respx.get("http://127.0.0.1:8188/system_stats").mock(
        return_value=httpx.Response(200, json={"system": {"os": "nt"}})
    )

    result = run_bridge_operation("check_connection", tmp_path)

    assert result["ok"] is True
    assert result["data"]["ok"] is True
    assert result["data"]["base_url"] == "http://127.0.0.1:8188"
    assert result["data"]["message"] == "Connected"
    assert result["data"]["checked_at"]
    assert result["data"]["details"]["reachable"] is True


def test_bridge_live_bridge_status_returns_success_envelope(monkeypatch, tmp_path: Path):
    _write_workspace(tmp_path)

    async def fake_status(config):
        return {"ok": True, "ready": True, "base_url": config.base_url}

    monkeypatch.setattr(desktop_bridge, "get_live_bridge_status", fake_status)

    result = run_bridge_operation("live_bridge_status", tmp_path)

    assert result["ok"] is True
    assert result["data"] == {
        "ok": True,
        "ready": True,
        "base_url": "http://127.0.0.1:8188",
    }


def test_bridge_live_bridge_reload_operations(monkeypatch, tmp_path: Path):
    _write_workspace(tmp_path)
    calls = []

    async def fake_reload_client(config, version=None):
        calls.append(("client", config.base_url, version))
        return {"ok": True, "version": version}

    async def fake_reload_backend(config):
        calls.append(("backend", config.base_url))
        return {"ok": True, "generation": 3}

    monkeypatch.setattr(desktop_bridge, "reload_live_bridge_client", fake_reload_client)
    monkeypatch.setattr(desktop_bridge, "reload_live_bridge_backend", fake_reload_backend)

    client = run_bridge_operation(
        "live_bridge_reload_client",
        tmp_path,
        {"version": "manual"},
    )
    backend = run_bridge_operation("live_bridge_reload_backend", tmp_path)

    assert client["ok"] is True
    assert client["data"] == {"ok": True, "version": "manual"}
    assert backend["ok"] is True
    assert backend["data"] == {"ok": True, "generation": 3}
    assert calls == [
        ("client", "http://127.0.0.1:8188", "manual"),
        ("backend", "http://127.0.0.1:8188"),
    ]


def test_bridge_live_bridge_push_workflow_reads_ui_workflow(
    monkeypatch,
    tmp_path: Path,
):
    _write_workspace(tmp_path)
    cfg = _config(tmp_path)
    save_workflow(cfg.workflows_dir, "ui.json", UI_WORKFLOW)
    calls = []

    async def fake_push(config, workflow, **kwargs):
        calls.append((config.base_url, workflow, kwargs))
        return {"ok": True, "acknowledged": True}

    monkeypatch.setattr(desktop_bridge, "push_live_workflow", fake_push)

    result = run_bridge_operation(
        "live_bridge_push_workflow",
        tmp_path,
        {
            "workflow_name": "ui.json",
            "force": True,
            "activate": False,
            "wait_for_ack": False,
        },
    )

    assert result["ok"] is True
    assert result["data"] == {"ok": True, "acknowledged": True}
    assert calls == [
        (
            "http://127.0.0.1:8188",
            UI_WORKFLOW,
            {
                "name": "ui.json",
                "activate": False,
                "force": True,
                "wait_for_ack": False,
            },
        )
    ]


def test_bridge_live_bridge_push_workflow_rejects_api_workflow(tmp_path: Path):
    _write_workspace(tmp_path)

    result = run_bridge_operation(
        "live_bridge_push_workflow",
        tmp_path,
        {"workflow_name": "cat.json"},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "ValueError"
    assert "workflow_not_ui_json" in result["error"]["message"]


def test_bridge_live_bridge_verify_operations(monkeypatch, tmp_path: Path):
    _write_workspace(tmp_path)
    cfg = _config(tmp_path)
    save_workflow(cfg.workflows_dir, "ui.json", UI_WORKFLOW)
    calls = []

    async def fake_verify(config, workflow=None, **kwargs):
        calls.append((config.base_url, workflow, kwargs))
        return {"ok": True, "verified": True}

    monkeypatch.setattr(desktop_bridge, "verify_live_bridge", fake_verify)

    without_workflow = run_bridge_operation("live_bridge_verify", tmp_path)
    with_workflow = run_bridge_operation(
        "live_bridge_verify",
        tmp_path,
        {"workflow_name": "ui.json", "force": True},
    )

    assert without_workflow["ok"] is True
    assert with_workflow["ok"] is True
    assert calls == [
        ("http://127.0.0.1:8188", None, {"force": False}),
        ("http://127.0.0.1:8188", UI_WORKFLOW, {"name": "ui.json", "force": True}),
    ]


def test_bridge_updates_asset_metadata(tmp_path: Path):
    _write_workspace(tmp_path)
    asset_id = _asset_ids(tmp_path)[0]

    result = run_bridge_operation(
        "update_asset_metadata",
        tmp_path,
        {
            "asset_id": asset_id,
            "favorite": True,
            "rating": 5,
            "tags": ["keeper", "cat"],
            "notes": "best frame",
        },
    )

    assert result["ok"] is True
    assert result["data"]["favorite"] is True
    assert result["data"]["rating"] == 5
    assert result["data"]["tags"] == ["cat", "keeper"]
    assert result["data"]["notes"] == "best frame"


def test_bridge_plans_asset_cleanup_without_deleting_by_default(tmp_path: Path):
    _write_workspace(tmp_path)
    asset_id = _asset_ids(tmp_path)[0]
    asset = run_bridge_operation("search_assets", tmp_path, {"limit": 1})["data"]["assets"][0]
    output_path = Path(asset["path"])

    result = run_bridge_operation("plan_asset_cleanup", tmp_path, {"asset_ids": [asset_id]})

    assert result["ok"] is True
    assert result["data"]["dry_run"] is True
    assert len(result["data"]["candidates"]) == 1
    assert output_path.exists()


def test_bridge_exports_asset_library_report(tmp_path: Path):
    _write_workspace(tmp_path)

    result = run_bridge_operation("export_asset_library_report", tmp_path, {})

    assert result["ok"] is True
    assert result["data"]["path"].endswith("asset-library-report.md")
    assert result["data"]["markdown"].startswith("# Comfydex Asset Library Report")


def test_bridge_compares_assets(tmp_path: Path):
    _write_workspace(tmp_path)
    _add_second_asset(tmp_path)
    left_id, right_id = _asset_ids(tmp_path)[:2]

    result = run_bridge_operation(
        "compare_assets",
        tmp_path,
        {"left_asset_id": left_id, "right_asset_id": right_id},
    )

    assert result["ok"] is True
    assert result["data"]["left"]["asset_id"] == left_id
    assert result["data"]["right"]["asset_id"] == right_id
    assert "size_bytes" in result["data"]["differences"]


def test_bridge_lists_and_reads_batches(tmp_path: Path):
    _write_workspace(tmp_path)
    cfg = _config(tmp_path)
    older = create_batch_record(
        cfg.runs_dir,
        "older",
        "cat.json",
        [{"node_id": "4", "inputs": {"text": "one"}}],
        now=datetime(2026, 6, 7, tzinfo=timezone.utc),
    )
    newer = create_batch_record(
        cfg.runs_dir,
        "newer",
        "cat.json",
        [{"node_id": "4", "inputs": {"text": "two"}}],
        now=datetime(2026, 6, 8, tzinfo=timezone.utc),
    )

    listed = run_bridge_operation("list_batches", tmp_path)
    read = run_bridge_operation("read_batch", tmp_path, {"batch_id": older["batch_id"]})

    assert listed["ok"] is True
    assert [batch["batch_id"] for batch in listed["data"][:2]] == [
        newer["batch_id"],
        older["batch_id"],
    ]
    assert listed["data"][0]["run_count"] == 1
    assert read["ok"] is True
    assert read["data"]["batch_id"] == older["batch_id"]


def test_bridge_rejects_malformed_batch_id(tmp_path: Path):
    _write_workspace(tmp_path)

    result = run_bridge_operation("read_batch", tmp_path, {"batch_id": "../bad"})

    assert result["ok"] is False
    assert result["error"]["type"] == "ValueError"


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
