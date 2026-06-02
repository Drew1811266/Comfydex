from __future__ import annotations

import asyncio
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
    return urlunparse((scheme, parsed.netloc, "/ws", "", f"clientId={quote(client_id)}", ""))


def event_matches_prompt(event: dict[str, Any], prompt_id: str) -> bool:
    data = event.get("data", {})
    if not isinstance(data, dict):
        return False
    return data.get("prompt_id") == prompt_id


def is_completion_event(event: dict[str, Any], prompt_id: str) -> bool:
    data = event.get("data", {})
    return (
        event.get("type") == "executing"
        and isinstance(data, dict)
        and data.get("prompt_id") == prompt_id
        and data.get("node") is None
    )


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
        async with websockets.connect(uri, additional_headers=headers or None) as websocket:
            while True:
                raw = await asyncio.wait_for(websocket.recv(), timeout=timeout_seconds)
                event = json.loads(raw)
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
