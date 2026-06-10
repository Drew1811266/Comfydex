import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_nodes.comfydex_live_bridge.backend import LiveBridgeBackend


CLIENT = ROOT / "custom_nodes" / "comfydex_live_bridge" / "web" / "client.js"


class FakePromptServer:
    def __init__(self):
        self.sent = []

    def send_sync(self, event, data, sid=None):
        self.sent.append((event, data, sid))


def run(coro):
    return asyncio.run(coro)


def test_load_workflow_defaults_force_to_false_in_response_and_event():
    server = FakePromptServer()
    bridge = LiveBridgeBackend(server)

    payload, status = run(
        bridge.load_workflow({"workflow": {"nodes": [], "links": []}, "name": "Safe"})
    )

    assert status == 200
    assert payload["force"] is False
    assert server.sent[0][1]["force"] is False


def test_load_workflow_rejects_non_object_workflow_without_sending_event():
    server = FakePromptServer()
    bridge = LiveBridgeBackend(server)

    payload, status = run(bridge.load_workflow({"workflow": []}))

    assert status == 400
    assert payload == {"ok": False, "error": "workflow_must_be_json_object"}
    assert server.sent == []


def test_client_refuses_to_replace_unsaved_canvas_without_force():
    source = CLIENT.read_text(encoding="utf-8")

    assert "function isCurrentWorkflowDirty" in source
    assert 'document.title.includes("*Unsaved")' in source
    assert "const force = payload?.force === true" in source
    assert "if (isCurrentWorkflowDirty(app) && !force)" in source
    assert "Refused to load workflow because the current canvas is unsaved." in source
