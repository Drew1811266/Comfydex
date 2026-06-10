import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_nodes.comfydex_live_bridge.backend import LiveBridgeBackend


class FakePromptServer:
    def __init__(self):
        self.sent = []

    def send_sync(self, event, data, sid=None):
        self.sent.append((event, data, sid))


def run(coro):
    return asyncio.run(coro)


def test_status_payload_identifies_bridge_and_routes():
    bridge = LiveBridgeBackend(FakePromptServer())

    payload, status = run(bridge.status({}))

    assert status == 200
    assert payload["ok"] is True
    assert payload["bridge"] == "comfydex_live_bridge"
    assert payload["routes"] == [
        "status",
        "load_workflow",
        "reload_client",
        "reload_backend",
    ]


def test_load_workflow_sends_canvas_event():
    server = FakePromptServer()
    bridge = LiveBridgeBackend(server)
    workflow = {"nodes": [], "links": []}

    payload, status = run(
        bridge.load_workflow(
            {
                "workflow": workflow,
                "name": "Unit Test Workflow",
                "activate": True,
                "force": True,
            }
        )
    )

    assert status == 200
    assert payload == {
        "ok": True,
        "name": "Unit Test Workflow",
        "activate": True,
        "force": True,
    }
    assert server.sent == [
        (
            "comfydex_live_load_workflow",
            {
                "workflow": workflow,
                "name": "Unit Test Workflow",
                "activate": True,
                "force": True,
            },
            None,
        )
    ]


def test_reload_client_sends_reload_event_with_version():
    server = FakePromptServer()
    bridge = LiveBridgeBackend(server)

    payload, status = run(bridge.reload_client({"version": "abc123"}))

    assert status == 200
    assert payload == {"ok": True, "version": "abc123"}
    assert server.sent == [
        (
            "comfydex_live_reload_client",
            {"version": "abc123"},
            None,
        )
    ]


def test_reload_backend_increments_generation_without_readding_routes():
    bridge = LiveBridgeBackend(FakePromptServer())

    first_payload, first_status = run(bridge.reload_backend({}))
    second_payload, second_status = run(bridge.reload_backend({}))

    assert first_status == 200
    assert second_status == 200
    assert first_payload["ok"] is True
    assert second_payload["ok"] is True
    assert first_payload["generation"] == 1
    assert second_payload["generation"] == 2


def test_reload_backend_reloads_runtime_module(monkeypatch):
    bridge = LiveBridgeBackend(FakePromptServer())
    calls = []

    def fake_reload(module):
        calls.append(module)
        module.RELOAD_TEST_TOKEN = "reloaded"
        return module

    monkeypatch.setattr(
        "custom_nodes.comfydex_live_bridge.backend.importlib.reload",
        fake_reload,
    )

    payload, status = run(bridge.reload_backend({}))

    assert status == 200
    assert payload["ok"] is True
    assert payload["generation"] == 1
    assert payload["runtime"] == "custom_nodes.comfydex_live_bridge.runtime"
    assert calls == [bridge.runtime]
    assert bridge.runtime.RELOAD_TEST_TOKEN == "reloaded"


def test_reload_backend_keeps_existing_runtime_when_reload_fails(monkeypatch):
    bridge = LiveBridgeBackend(FakePromptServer())
    original_runtime = bridge.runtime

    def fail_reload(_module):
        raise SyntaxError("broken runtime")

    monkeypatch.setattr(
        "custom_nodes.comfydex_live_bridge.backend.importlib.reload",
        fail_reload,
    )

    payload, status = run(bridge.reload_backend({}))

    assert status == 500
    assert payload["ok"] is False
    assert payload["error"] == "backend_reload_failed"
    assert "broken runtime" in payload["message"]
    assert bridge.runtime is original_runtime
    assert bridge.generation == 0


def test_rpc_dispatches_known_actions_and_rejects_unknown_actions():
    server = FakePromptServer()
    bridge = LiveBridgeBackend(server)

    ok_payload, ok_status = run(
        bridge.rpc({"action": "reload_client", "payload": {"version": "rpc-v1"}})
    )
    bad_payload, bad_status = run(bridge.rpc({"action": "missing", "payload": {}}))

    assert ok_status == 200
    assert ok_payload == {"ok": True, "version": "rpc-v1"}
    assert bad_status == 404
    assert bad_payload == {"ok": False, "error": "unknown_action", "action": "missing"}
