from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import websockets

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]
FallbackCallback = Callable[[], Awaitable[dict[str, Any]]]


def websocket_url(base_url: str, client_id: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base_path = parsed.path.rstrip("/")
    ws_path = f"{base_path}/ws" if base_path else "/ws"
    return urlunparse((scheme, parsed.netloc, ws_path, "", f"clientId={quote(client_id)}", ""))


def event_matches_prompt(event: dict[str, Any], prompt_id: str) -> bool:
    data = event.get("data", {})
    if not isinstance(data, dict):
        return False
    return data.get("prompt_id") == prompt_id


def is_completion_event(event: dict[str, Any], prompt_id: str) -> bool:
    data = event.get("data", {})
    if not isinstance(data, dict) or data.get("prompt_id") != prompt_id:
        return False
    if event.get("type") == "execution_success":
        return True
    return (
        event.get("type") == "executing"
        and data.get("node") is None
    )


def _websocket_headers_kwargs(connect_callable: Callable[..., Any], headers: dict[str, str]) -> dict[str, dict[str, str] | None]:
    try:
        parameters = inspect.signature(connect_callable).parameters
    except (TypeError, ValueError):
        parameters = {}
    header_value = headers or None
    if "additional_headers" in parameters:
        return {"additional_headers": header_value}
    return {"extra_headers": header_value}


async def wait_for_prompt(
    *,
    base_url: str,
    prompt_id: str,
    client_id: str,
    headers: dict[str, str],
    timeout_seconds: int,
    on_event: EventCallback,
    fallback: FallbackCallback,
) -> dict[str, Any]:
    uri = websocket_url(base_url, client_id)
    try:
        async with websockets.connect(uri, **_websocket_headers_kwargs(websockets.connect, headers)) as websocket:
            while True:
                raw = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
                if isinstance(raw, bytes):
                    continue
                try:
                    event = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(event, dict):
                    continue
                if event_matches_prompt(event, prompt_id) or event.get("type") == "status":
                    await on_event(event)
                if is_completion_event(event, prompt_id):
                    return {"completed": True, "fallback_used": False}
    except Exception as exc:
        fallback_result = await fallback()
        return {
            "completed": False,
            "fallback_used": True,
            "websocket_error": str(exc),
            "fallback": fallback_result,
        }
