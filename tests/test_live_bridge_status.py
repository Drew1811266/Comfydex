from __future__ import annotations

import importlib
import json
from pathlib import Path

import httpx
import pytest
import respx

from comfydex_mcp.config import ComfydexConfig


UI_WORKFLOW = {"nodes": [], "links": []}


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


def _live_bridge():
    return importlib.import_module("comfydex_mcp.live_bridge")


def _ready_bridge_status() -> dict:
    return {
        "ok": True,
        "bridge": {
            "name": "comfydex_live_bridge",
            "version": "1.2.0",
            "generation": 2,
            "routes": ["status", "load_workflow", "frontend_status"],
        },
        "frontend": {
            "connected": True,
            "stale": False,
            "version": "bootstrap",
            "client_id": "client-1",
            "last_seen_at": "2026-06-10T00:00:00+00:00",
            "last_seen_age_ms": 500,
        },
    }


def _mock_ready_status_routes() -> None:
    respx.get("http://127.0.0.1:8188/system_stats").mock(
        return_value=httpx.Response(200, json={"system": {"os": "nt"}})
    )
    respx.get("http://127.0.0.1:8188/comfydex/live/status").mock(
        return_value=httpx.Response(200, json=_ready_bridge_status())
    )
    respx.get("http://127.0.0.1:8188/extensions").mock(
        return_value=httpx.Response(
            200,
            json=["custom_nodes/comfydex_live_bridge/web/comfydex_live_bridge.js"],
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_live_bridge_status_ready_when_server_bridge_and_frontend_are_ready(
    tmp_path: Path,
):
    _mock_ready_status_routes()

    result = await _live_bridge().get_live_bridge_status(_config(tmp_path))

    assert result["ok"] is True
    assert result["ready"] is True
    assert result["can_push"] is True
    assert result["server"]["reachable"] is True
    assert result["server"]["status_code"] == 200
    assert result["bridge"]["loaded"] is True
    assert result["bridge"]["version"] == "1.2.0"
    assert result["frontend"]["listed"] is True
    assert result["frontend"]["connected"] is True
    assert result["diagnostics"] == []


@pytest.mark.asyncio
@respx.mock
async def test_live_bridge_status_reports_missing_bridge_route_as_restart_needed(
    tmp_path: Path,
):
    respx.get("http://127.0.0.1:8188/system_stats").mock(
        return_value=httpx.Response(200, json={"system": {"os": "nt"}})
    )
    respx.get("http://127.0.0.1:8188/comfydex/live/status").mock(
        return_value=httpx.Response(404, json={"error": "not_found"})
    )
    respx.get("http://127.0.0.1:8188/extensions").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await _live_bridge().get_live_bridge_status(_config(tmp_path))

    assert result["ready"] is False
    assert result["needs_restart"] is True
    assert result["diagnostics"][0]["code"] == "bridge_not_loaded"


@pytest.mark.asyncio
@respx.mock
async def test_live_bridge_status_reports_frontend_listed_but_not_connected(
    tmp_path: Path,
):
    status = _ready_bridge_status()
    status["frontend"] = {
        "connected": False,
        "stale": False,
        "version": "bootstrap",
    }
    respx.get("http://127.0.0.1:8188/system_stats").mock(
        return_value=httpx.Response(200, json={"system": {"os": "nt"}})
    )
    respx.get("http://127.0.0.1:8188/comfydex/live/status").mock(
        return_value=httpx.Response(200, json=status)
    )
    respx.get("http://127.0.0.1:8188/extensions").mock(
        return_value=httpx.Response(
            200,
            json=["custom_nodes/comfydex_live_bridge/web/comfydex_live_bridge.js"],
        )
    )

    result = await _live_bridge().get_live_bridge_status(_config(tmp_path))

    assert result["ready"] is False
    assert result["needs_refresh"] is True
    assert any(
        diagnostic["code"] == "frontend_not_connected"
        for diagnostic in result["diagnostics"]
    )


@pytest.mark.asyncio
@respx.mock
async def test_push_live_workflow_waits_for_matching_acknowledgement(tmp_path: Path):
    post_route = respx.post(
        "http://127.0.0.1:8188/comfydex/live/load_workflow"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "request_id": "request-1", "name": "Acked"},
        )
    )
    respx.get("http://127.0.0.1:8188/comfydex/live/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "last_workflow_result": {
                    "ok": True,
                    "request_id": "request-1",
                    "name": "Acked",
                },
            },
        )
    )

    result = await _live_bridge().push_live_workflow(
        _config(tmp_path),
        UI_WORKFLOW,
        name="Acked",
        force=True,
    )

    sent_payload = json.loads(post_route.calls.last.request.content)
    assert sent_payload == {
        "workflow": UI_WORKFLOW,
        "name": "Acked",
        "activate": True,
        "force": True,
    }
    assert result["ok"] is True
    assert result["acknowledged"] is True
    assert result["last_workflow_result"]["request_id"] == "request-1"


@pytest.mark.asyncio
@respx.mock
async def test_push_live_workflow_reports_timeout_when_ack_never_matches(
    tmp_path: Path,
):
    respx.post("http://127.0.0.1:8188/comfydex/live/load_workflow").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "request_id": "request-1", "name": "Timeout"},
        )
    )
    respx.get("http://127.0.0.1:8188/comfydex/live/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "last_workflow_result": {
                    "ok": True,
                    "request_id": "other-request",
                },
            },
        )
    )

    result = await _live_bridge().push_live_workflow(
        _config(tmp_path),
        UI_WORKFLOW,
        name="Timeout",
        ack_timeout_seconds=0.01,
    )

    assert result["ok"] is False
    assert result["acknowledged"] is False
    assert result["diagnostics"][0]["code"] == "workflow_ack_timeout"


@pytest.mark.asyncio
@respx.mock
async def test_reload_live_bridge_client_uses_supplied_and_generated_versions(
    tmp_path: Path,
):
    route = respx.post("http://127.0.0.1:8188/comfydex/live/reload_client").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    supplied = await _live_bridge().reload_live_bridge_client(
        _config(tmp_path),
        version="manual-version",
    )
    generated = await _live_bridge().reload_live_bridge_client(_config(tmp_path))

    supplied_payload = json.loads(route.calls[0].request.content)
    generated_payload = json.loads(route.calls[1].request.content)
    assert supplied["ok"] is True
    assert supplied["version"] == "manual-version"
    assert supplied_payload == {"version": "manual-version"}
    assert generated["ok"] is True
    assert isinstance(generated["version"], str)
    assert generated["version"]
    assert generated_payload == {"version": generated["version"]}


@pytest.mark.asyncio
@respx.mock
async def test_verify_live_bridge_skip_push_returns_status_and_reload_results(
    tmp_path: Path,
):
    _mock_ready_status_routes()
    respx.post("http://127.0.0.1:8188/comfydex/live/reload_client").mock(
        return_value=httpx.Response(200, json={"ok": True, "version": "verify"})
    )
    respx.post("http://127.0.0.1:8188/comfydex/live/reload_backend").mock(
        return_value=httpx.Response(200, json={"ok": True, "generation": 3})
    )

    result = await _live_bridge().verify_live_bridge(
        _config(tmp_path),
        workflow=None,
    )

    assert result["ok"] is True
    assert result["status"]["ready"] is True
    assert result["reload_client"]["ok"] is True
    assert result["reload_backend"]["ok"] is True
    assert result["push_workflow"] is None
