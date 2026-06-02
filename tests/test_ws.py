import json

import pytest

import comfydex_mcp.ws as ws
from comfydex_mcp.ws import event_matches_prompt, is_completion_event, websocket_url


def test_websocket_url_converts_http_to_ws():
    assert websocket_url("http://127.0.0.1:8188", "client-1") == "ws://127.0.0.1:8188/ws?clientId=client-1"


def test_websocket_url_converts_https_to_wss():
    assert websocket_url("https://comfy.example.test/", "client-1") == "wss://comfy.example.test/ws?clientId=client-1"


def test_event_matches_prompt():
    event = {"type": "executing", "data": {"prompt_id": "p1", "node": "3"}}
    assert event_matches_prompt(event, "p1") is True
    assert event_matches_prompt(event, "p2") is False


def test_completion_event_is_executing_with_null_node():
    event = {"type": "executing", "data": {"prompt_id": "p1", "node": None}}
    assert is_completion_event(event, "p1") is True


def test_non_matching_completion_event_is_false():
    event = {"type": "executing", "data": {"prompt_id": "p2", "node": None}}
    assert is_completion_event(event, "p1") is False


def test_completion_event_accepts_execution_success():
    event = {"type": "execution_success", "data": {"prompt_id": "p1"}}
    assert is_completion_event(event, "p1") is True


async def test_wait_for_prompt_ignores_binary_and_invalid_json_before_success(monkeypatch):
    class FakeWebSocket:
        def __init__(self):
            self.frames = iter(
                [
                    b"binary-preview",
                    "not-json",
                    json.dumps({"type": "execution_success", "data": {"prompt_id": "p1"}}),
                ]
            )

        async def recv(self):
            return next(self.frames)

    class FakeConnect:
        async def __aenter__(self):
            return FakeWebSocket()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    def fake_connect(uri, **kwargs):
        return FakeConnect()

    fallback_called = False

    async def on_event(event):
        return None

    async def fallback():
        nonlocal fallback_called
        fallback_called = True
        return {}

    monkeypatch.setattr(ws.websockets, "connect", fake_connect)

    result = await ws.wait_for_prompt(
        base_url="http://127.0.0.1:8188",
        prompt_id="p1",
        client_id="client-1",
        headers={},
        timeout_seconds=1,
        on_event=on_event,
        fallback=fallback,
    )

    assert result == {"completed": True, "fallback_used": False}
    assert fallback_called is False


def test_connect_kwargs_supports_extra_headers_signature():
    headers = {"Authorization": "Bearer secret"}

    def supports_additional(uri, *, additional_headers=None):
        return None

    def supports_extra(uri, *, extra_headers=None):
        return None

    assert ws._websocket_headers_kwargs(supports_additional, headers) == {"additional_headers": headers}
    assert ws._websocket_headers_kwargs(supports_extra, headers) == {"extra_headers": headers}
