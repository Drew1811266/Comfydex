import pytest

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
