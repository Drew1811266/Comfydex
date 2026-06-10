from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from .comfy_client import ComfyClient
from .config import ComfydexConfig


BRIDGE_NAME = "comfydex_live_bridge"
BRIDGE_STATUS_PATH = "/comfydex/live/status"
EXTENSIONS_PATH = "/extensions"
LOAD_WORKFLOW_PATH = "/comfydex/live/load_workflow"
RELOAD_CLIENT_PATH = "/comfydex/live/reload_client"
RELOAD_BACKEND_PATH = "/comfydex/live/reload_backend"

DIAGNOSTIC_MESSAGES = {
    "comfyui_unreachable": "ComfyUI did not respond to /system_stats.",
    "bridge_not_loaded": "The Comfydex live bridge status route is not loaded.",
    "bridge_status_not_ok": "The Comfydex live bridge status route did not report ok=true.",
    "bridge_frontend_not_listed": "The Comfydex live bridge frontend extension is not listed by ComfyUI.",
    "frontend_not_connected": "The Comfydex live bridge frontend client is not connected.",
    "frontend_stale": "The Comfydex live bridge frontend client is stale.",
    "unsaved_canvas": "The ComfyUI canvas has unsaved changes.",
    "stale_client": "The Comfydex live bridge frontend client needs refresh.",
    "workflow_ack_timeout": "Timed out waiting for the frontend workflow acknowledgement.",
    "workflow_must_be_json_object": "Workflow must be a JSON object.",
    "workflow_not_ui_json": "Workflow must be a ComfyUI UI workflow JSON object.",
}


async def get_live_bridge_status(config: ComfydexConfig) -> dict[str, Any]:
    async with _client(config) as client:
        system_call = await _get_json_with_status(client, "/system_stats")
        bridge_call = await _get_json_with_status(client, BRIDGE_STATUS_PATH)
        extensions_call = await _get_json_with_status(client, EXTENSIONS_PATH)

    bridge_payload = _dict_payload(bridge_call.get("payload"))
    bridge = _normalize_bridge(bridge_call, bridge_payload)
    frontend = _normalize_frontend(
        bridge_payload.get("frontend"),
        extensions_call.get("payload"),
    )
    server = _normalize_server(system_call)

    diagnostics = _status_diagnostics(server, bridge_call, bridge_payload, frontend)
    ready = (
        server["reachable"]
        and bridge_payload.get("ok") is True
        and frontend["listed"]
        and frontend["connected"]
        and not frontend["stale"]
    )
    diagnostic_codes = {diagnostic["code"] for diagnostic in diagnostics}

    return {
        "ok": ready,
        "ready": ready,
        "base_url": config.base_url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "server": server,
        "bridge": bridge,
        "frontend": frontend,
        "can_push": ready,
        "needs_restart": bool(
            diagnostic_codes
            & {
                "bridge_not_loaded",
                "bridge_status_not_ok",
                "bridge_frontend_not_listed",
            }
        ),
        "needs_refresh": bool(
            diagnostic_codes
            & {
                "frontend_not_connected",
                "frontend_stale",
                "stale_client",
            }
        ),
        "diagnostics": diagnostics,
    }


async def push_live_workflow(
    config: ComfydexConfig,
    workflow: dict[str, Any],
    *,
    name: str,
    activate: bool = True,
    force: bool = False,
    wait_for_ack: bool = True,
    ack_timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    if not isinstance(workflow, dict):
        return _workflow_failure("workflow_must_be_json_object")
    if not _is_ui_workflow(workflow):
        return _workflow_failure("workflow_not_ui_json")

    payload = {
        "workflow": workflow,
        "name": name,
        "activate": activate,
        "force": force,
    }
    async with _client(config) as client:
        post_result = await _post_json_result(client, LOAD_WORKFLOW_PATH, payload)
        request_id = _request_id(post_result)
        if not wait_for_ack or not request_id:
            result = dict(post_result)
            result["acknowledged"] = False
            result.setdefault("diagnostics", _diagnostics_from_payload(result))
            return result

        return await _wait_for_workflow_ack(
            client,
            post_result,
            request_id,
            ack_timeout_seconds,
        )


async def reload_live_bridge_client(
    config: ComfydexConfig,
    version: str | None = None,
) -> dict[str, Any]:
    resolved_version = version or _generated_version()
    async with _client(config) as client:
        result = await _post_json_result(
            client,
            RELOAD_CLIENT_PATH,
            {"version": resolved_version},
        )
    result["version"] = str(result.get("version") or resolved_version)
    return result


async def reload_live_bridge_backend(config: ComfydexConfig) -> dict[str, Any]:
    async with _client(config) as client:
        return await _post_json_result(client, RELOAD_BACKEND_PATH, {})


async def verify_live_bridge(
    config: ComfydexConfig,
    workflow: dict[str, Any] | None = None,
    *,
    name: str = "Comfydex Verification Workflow",
    force: bool = False,
) -> dict[str, Any]:
    status = await get_live_bridge_status(config)
    reload_client = await reload_live_bridge_client(config)
    reload_backend = await reload_live_bridge_backend(config)
    push_workflow = None
    if workflow is not None:
        push_workflow = await push_live_workflow(
            config,
            workflow,
            name=name,
            force=force,
        )

    ok = (
        bool(status.get("ready"))
        and bool(reload_client.get("ok"))
        and bool(reload_backend.get("ok"))
        and (push_workflow is None or bool(push_workflow.get("ok")))
    )
    return {
        "ok": ok,
        "status": status,
        "reload_client": reload_client,
        "reload_backend": reload_backend,
        "push_workflow": push_workflow,
    }


def _client(config: ComfydexConfig) -> ComfyClient:
    return ComfyClient(
        config.base_url,
        config.headers,
        config.request_timeout_seconds,
    )


async def _get_json_with_status(
    client: ComfyClient,
    path: str,
) -> dict[str, Any]:
    try:
        response = await client.client.get(path)
        status_code = response.status_code
        response.raise_for_status()
        return {
            "ok": True,
            "status_code": status_code,
            "payload": _response_json(response),
        }
    except httpx.HTTPStatusError as exc:
        return {
            "ok": False,
            "status_code": exc.response.status_code,
            "payload": _response_json(exc.response),
            "error_type": exc.__class__.__name__,
            "error": str(exc) or exc.__class__.__name__,
        }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "error_type": exc.__class__.__name__,
            "error": str(exc) or exc.__class__.__name__,
        }


def _response_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _normalize_server(system_call: dict[str, Any]) -> dict[str, Any]:
    server = {
        "reachable": bool(system_call.get("ok")),
        "status_code": system_call.get("status_code"),
    }
    if not server["reachable"]:
        if system_call.get("error_type"):
            server["error_type"] = system_call["error_type"]
        if system_call.get("error"):
            server["error"] = system_call["error"]
    return server


def _normalize_bridge(
    bridge_call: dict[str, Any],
    bridge_payload: dict[str, Any],
) -> dict[str, Any]:
    bridge_info = bridge_payload.get("bridge")
    bridge_dict = bridge_info if isinstance(bridge_info, dict) else {}
    bridge_name = _string_or_none(bridge_dict.get("name"))
    if bridge_name is None and isinstance(bridge_info, str):
        bridge_name = bridge_info
    if bridge_name is None:
        bridge_name = _string_or_none(bridge_payload.get("name"))

    routes = _string_list(bridge_dict.get("routes"))
    if not routes:
        routes = _string_list(bridge_payload.get("routes"))

    return {
        "loaded": bool(
            bridge_call.get("ok")
            and (
                bridge_name == BRIDGE_NAME
                or bool(routes)
                or bridge_payload.get("ok") is True
            )
        ),
        "name": bridge_name,
        "version": _string_or_none(
            bridge_dict.get("version", bridge_payload.get("version"))
        ),
        "generation": _int_or_none(
            bridge_dict.get("generation", bridge_payload.get("generation"))
        ),
        "routes": routes,
    }


def _normalize_frontend(
    frontend_payload: Any,
    extensions_payload: Any,
) -> dict[str, Any]:
    frontend = _dict_payload(frontend_payload)
    return {
        "listed": _contains_bridge_extension(extensions_payload),
        "connected": frontend.get("connected") is True,
        "stale": frontend.get("stale") is True,
        "version": _string_or_none(frontend.get("version")),
        "client_id": _string_or_none(frontend.get("client_id")),
        "last_seen_at": _string_or_none(frontend.get("last_seen_at")),
        "last_seen_age_ms": _number_or_none(frontend.get("last_seen_age_ms")),
    }


def _status_diagnostics(
    server: dict[str, Any],
    bridge_call: dict[str, Any],
    bridge_payload: dict[str, Any],
    frontend: dict[str, Any],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    if not server["reachable"]:
        diagnostics.append(
            _diagnostic(
                "comfyui_unreachable",
                error=server.get("error"),
                error_type=server.get("error_type"),
                status_code=server.get("status_code"),
            )
        )
        return diagnostics

    bridge_status_code = bridge_call.get("status_code")
    if not bridge_call.get("ok"):
        code = (
            "bridge_not_loaded"
            if bridge_status_code == 404
            else "bridge_status_not_ok"
        )
        diagnostics.append(
            _diagnostic(
                code,
                status_code=bridge_status_code,
                error=bridge_call.get("error"),
            )
        )
    elif bridge_payload.get("ok") is not True:
        diagnostics.append(_diagnostic("bridge_status_not_ok"))

    if not frontend["listed"]:
        diagnostics.append(_diagnostic("bridge_frontend_not_listed"))
        return diagnostics

    if not frontend["connected"]:
        diagnostics.append(_diagnostic("frontend_not_connected"))
    if frontend["stale"]:
        diagnostics.append(_diagnostic("frontend_stale"))

    raw_frontend = _dict_payload(bridge_payload.get("frontend"))
    if raw_frontend.get("unsaved_canvas") is True:
        diagnostics.append(_diagnostic("unsaved_canvas"))
    if raw_frontend.get("stale_client") is True:
        diagnostics.append(_diagnostic("stale_client"))

    return diagnostics


async def _post_json_result(
    client: ComfyClient,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        result = await client.post_json(path, payload)
        if isinstance(result, dict):
            normalized = dict(result)
        else:
            normalized = {"ok": False, "payload": result}
    except httpx.HTTPStatusError as exc:
        response_payload = _response_json(exc.response)
        normalized = (
            dict(response_payload)
            if isinstance(response_payload, dict)
            else {"error": str(exc) or exc.__class__.__name__}
        )
        normalized.setdefault("ok", False)
        normalized["status_code"] = exc.response.status_code
    except httpx.HTTPError as exc:
        normalized = {
            "ok": False,
            "error_type": exc.__class__.__name__,
            "error": str(exc) or exc.__class__.__name__,
        }

    normalized.setdefault("ok", False)
    normalized.setdefault("diagnostics", _diagnostics_from_payload(normalized))
    return normalized


async def _wait_for_workflow_ack(
    client: ComfyClient,
    post_result: dict[str, Any],
    request_id: str,
    ack_timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, ack_timeout_seconds)
    poll_delay = min(0.1, max(0.001, ack_timeout_seconds / 10))

    while True:
        try:
            status_payload = await client.get_json(BRIDGE_STATUS_PATH)
        except httpx.HTTPError:
            status_payload = {}

        last_result = _last_workflow_result(status_payload)
        if last_result and _request_id(last_result) == request_id:
            diagnostics = _diagnostics_from_payload(last_result)
            result = dict(post_result)
            result["ok"] = bool(post_result.get("ok")) and last_result.get("ok") is not False
            result["acknowledged"] = True
            result["last_workflow_result"] = last_result
            result["diagnostics"] = diagnostics
            return result

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            result = dict(post_result)
            result["ok"] = False
            result["acknowledged"] = False
            result["diagnostics"] = [_diagnostic("workflow_ack_timeout")]
            return result

        await asyncio.sleep(min(poll_delay, remaining))


def _last_workflow_result(status_payload: Any) -> dict[str, Any] | None:
    if not isinstance(status_payload, dict):
        return None
    for key in ("last_workflow_result", "workflow_result", "last_result"):
        value = status_payload.get(key)
        if isinstance(value, dict):
            return value
    frontend = status_payload.get("frontend")
    if isinstance(frontend, dict):
        value = frontend.get("last_workflow_result")
        if isinstance(value, dict):
            return value
    return None


def _request_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("request_id")
    if isinstance(value, str) and value:
        return value
    return None


def _workflow_failure(code: str) -> dict[str, Any]:
    return {
        "ok": False,
        "acknowledged": False,
        "diagnostics": [_diagnostic(code)],
    }


def _diagnostics_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_code = payload.get("error") or payload.get("code")
    code = raw_code if isinstance(raw_code, str) else None
    if code in DIAGNOSTIC_MESSAGES:
        return [_diagnostic(code)]
    return []


def _diagnostic(code: str, **details: Any) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "code": code,
        "message": DIAGNOSTIC_MESSAGES[code],
    }
    clean_details = {
        key: value
        for key, value in details.items()
        if value is not None and value != ""
    }
    if clean_details:
        diagnostic["details"] = clean_details
    return diagnostic


def _is_ui_workflow(workflow: dict[str, Any]) -> bool:
    return isinstance(workflow.get("nodes"), list)


def _contains_bridge_extension(payload: Any) -> bool:
    if isinstance(payload, str):
        normalized = payload.lower()
        return BRIDGE_NAME in normalized or "comfydex.live_bridge" in normalized
    if isinstance(payload, list):
        return any(_contains_bridge_extension(value) for value in payload)
    if isinstance(payload, dict):
        return any(
            _contains_bridge_extension(key) or _contains_bridge_extension(value)
            for key, value in payload.items()
        )
    return False


def _dict_payload(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number_or_none(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _generated_version() -> str:
    return f"codex-{uuid.uuid4().hex}"
