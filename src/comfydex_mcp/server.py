from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .analyzer import analyze_workflow
from .comfy_client import ComfyClient, extract_output_refs
from .config import ComfydexConfig, load_config, redact_config, save_config
from .conversion import (
    conversion_report_path,
    convert_ui_to_api,
    explain_conversion_gaps,
    save_conversion_report,
)
from .paths import safe_json_path, safe_output_path
from .runs import append_event, create_run, list_runs, read_run, register_outputs, update_status
from .ui_workflows import classify_workflow_payload, import_ui_workflow
from .validation import validate_api_workflow
from .workflows import list_workflows, read_workflow, save_workflow
from .ws import wait_for_prompt

mcp = FastMCP("comfydex")


@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    config: ComfydexConfig


def resolve_workspace() -> Path:
    return Path(os.environ.get("CODEX_WORKSPACE", os.getcwd())).resolve()


def tool_context(workspace: Path | None = None) -> ToolContext:
    resolved = (workspace or resolve_workspace()).resolve()
    return ToolContext(workspace=resolved, config=load_config(resolved))


def _resolve_config_dir(workspace: Path, value: str | None, current: Path) -> Path:
    if not value:
        return current
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (workspace / raw).resolve()


def _require_prompt_id(submit_response: Any) -> str:
    prompt_id = (
        submit_response.get("prompt_id")
        if isinstance(submit_response, dict)
        else None
    )
    if not isinstance(prompt_id, str) or not prompt_id.strip():
        raise ValueError(
            f"ComfyUI submit response missing non-empty prompt_id: {submit_response!r}"
        )
    return prompt_id


def _prompt_history(history: Any, prompt_id: str) -> dict[str, Any] | None:
    if not isinstance(history, dict):
        return None
    prompt_history = history.get(prompt_id)
    if isinstance(prompt_history, dict):
        return prompt_history
    if "outputs" in history or "status" in history:
        return history
    return None


def _status_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.lower()]
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(_status_strings(item))
        return strings
    if isinstance(value, (list, tuple)):
        strings = []
        for item in value:
            strings.extend(_status_strings(item))
        return strings
    return []


def _status_indicates_failure(status: Any) -> bool:
    return any(
        marker in value
        for value in _status_strings(status)
        for marker in ("error", "exception", "failed", "failure")
    )


def _status_indicates_success(status: Any) -> bool:
    if isinstance(status, dict) and status.get("completed") is True:
        return True
    return any(
        marker in value
        for value in _status_strings(status)
        for marker in ("success", "completed", "complete")
    )


def _history_status(history: Any, prompt_id: str) -> str | None:
    prompt_history = _prompt_history(history, prompt_id)
    if prompt_history is None:
        return None

    status = prompt_history.get("status")
    if _status_indicates_failure(status):
        return "failed"
    if _status_indicates_success(status):
        return "completed"

    outputs = prompt_history.get("outputs")
    if isinstance(outputs, dict) and bool(outputs):
        return "completed"
    return None


def _fallback_history_status(result: dict[str, Any], prompt_id: str) -> str | None:
    return _history_status(result.get("fallback", {}).get("history", {}), prompt_id)


async def _poll_history_until_terminal(
    *,
    client: ComfyClient,
    prompt_id: str,
    timeout_seconds: int,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(timeout_seconds, 0)
    polls = 0

    while True:
        polls += 1
        queue = await client.get_queue()
        history = await client.get_history(prompt_id)
        status = _history_status(history, prompt_id)
        result = {
            "completed": status == "completed",
            "fallback_used": True,
            "fallback": {
                "queue": queue,
                "history": history,
            },
            "polls": polls,
        }
        if status is not None:
            result["terminal_status"] = status
            return result
        if loop.time() >= deadline:
            result["timeout"] = True
            return result
        await sleep(poll_interval_seconds)


def _safe_output_type(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "output")).strip(".-")
    return cleaned or "output"


@mcp.tool()
async def comfy_check_connection() -> dict[str, Any]:
    ctx = tool_context()
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        return await client.check_connection()


@mcp.tool()
async def comfy_get_config() -> dict[str, Any]:
    return redact_config(tool_context().config)


@mcp.tool()
async def comfy_set_config(
    base_url: str | None = None,
    workflows_dir: str | None = None,
    runs_dir: str | None = None,
    headers: dict[str, str] | None = None,
    request_timeout_seconds: int | None = None,
    websocket_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    current = ctx.config
    updated = ComfydexConfig(
        workspace=ctx.workspace,
        base_url=(base_url or current.base_url).rstrip("/"),
        workflows_dir=_resolve_config_dir(
            ctx.workspace,
            workflows_dir,
            current.workflows_dir,
        ),
        runs_dir=_resolve_config_dir(ctx.workspace, runs_dir, current.runs_dir),
        headers=headers if headers is not None else current.headers,
        request_timeout_seconds=request_timeout_seconds
        or current.request_timeout_seconds,
        websocket_timeout_seconds=websocket_timeout_seconds
        or current.websocket_timeout_seconds,
    )
    save_config(updated)
    return redact_config(updated)


@mcp.tool()
async def comfy_get_object_info() -> dict[str, Any]:
    ctx = tool_context()
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        return await client.get_object_info()


@mcp.tool()
async def comfy_list_workflows() -> list[dict[str, Any]]:
    ctx = tool_context()
    return list_workflows(ctx.config.workflows_dir)


@mcp.tool()
async def comfy_read_workflow(name: str) -> dict[str, Any]:
    ctx = tool_context()
    return read_workflow(ctx.config.workflows_dir, name)


@mcp.tool()
async def comfy_validate_api_workflow(name: str) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, name)
    if loaded["kind"] != "api":
        raise ValueError(
            "comfy_validate_api_workflow requires ComfyUI API prompt JSON"
        )

    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    return validate_api_workflow(loaded["json"], object_info)


@mcp.tool()
async def comfy_convert_ui_to_api(
    source_name: str,
    target_name: str,
    allow_draft: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, source_name)
    if loaded["kind"] != "ui":
        raise ValueError("comfy_convert_ui_to_api requires ComfyUI UI workflow JSON")
    safe_json_path(ctx.config.workflows_dir, target_name)

    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()

    result = convert_ui_to_api(
        loaded["json"],
        object_info,
        source_name,
        target_name,
    )
    report_path = save_conversion_report(
        ctx.config.workflows_dir,
        source_name,
        result["report"],
    )
    result["report_path"] = str(report_path)
    result["draft_saved"] = False

    if result["workflow"] is not None:
        save_workflow(
            ctx.config.workflows_dir,
            target_name,
            result["workflow"],
            require_api=True,
            source="converted",
            validation_status="valid",
        )
        result["saved_workflow"] = target_name

    return result


@mcp.tool()
async def comfy_explain_conversion_gaps(source_name: str) -> dict[str, Any]:
    ctx = tool_context()
    report_path = conversion_report_path(ctx.config.workflows_dir, source_name)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return explain_conversion_gaps(report) | {"report_path": str(report_path)}


@mcp.tool()
async def comfy_save_workflow(
    name: str,
    workflow: dict[str, Any],
    require_api: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    path = save_workflow(
        ctx.config.workflows_dir,
        name,
        workflow,
        require_api=require_api,
    )
    return read_workflow(path.parent, path.name)


@mcp.tool()
async def comfy_classify_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    return classify_workflow_payload(workflow)


@mcp.tool()
async def comfy_import_ui_workflow(
    name: str,
    workflow: dict[str, Any],
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    classification = classify_workflow_payload(workflow)
    if classification["kind"] != "ui":
        raise ValueError(
            "comfy_import_ui_workflow requires ComfyUI UI workflow JSON"
        )

    object_info = None
    if use_object_info:
        async with ComfyClient(
            ctx.config.base_url,
            ctx.config.headers,
            ctx.config.request_timeout_seconds,
        ) as client:
            object_info = await client.get_object_info()
    return import_ui_workflow(
        ctx.config.workflows_dir,
        name,
        workflow,
        object_info=object_info,
    )


@mcp.tool()
async def comfy_analyze_workflow(
    name: str,
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    workflow = read_workflow(ctx.config.workflows_dir, name)["json"]
    object_info = None
    if use_object_info:
        async with ComfyClient(
            ctx.config.base_url,
            ctx.config.headers,
            ctx.config.request_timeout_seconds,
        ) as client:
            object_info = await client.get_object_info()
    return analyze_workflow(workflow, object_info)


@mcp.tool()
async def comfy_submit_workflow(
    name: str,
    run_label: str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, name)
    if loaded["kind"] != "api":
        raise ValueError("comfy_submit_workflow requires ComfyUI API prompt JSON")

    actual_client_id = client_id or f"comfydex-{uuid.uuid4()}"
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        try:
            submitted = await client.submit_prompt(loaded["json"], actual_client_id)
        except Exception as exc:
            failed_run = create_run(
                ctx.config.runs_dir,
                name,
                loaded["json"],
                ctx.config.base_url,
                None,
                actual_client_id,
                run_label or Path(name).stem,
            )
            append_event(
                ctx.config.runs_dir,
                failed_run["run_id"],
                {
                    "type": "submission_error",
                    "error": str(exc),
                },
            )
            update_status(ctx.config.runs_dir, failed_run["run_id"], "failed")
            raise

    prompt_id = _require_prompt_id(submitted)
    return create_run(
        ctx.config.runs_dir,
        name,
        loaded["json"],
        ctx.config.base_url,
        prompt_id,
        actual_client_id,
        run_label or Path(name).stem,
    )


@mcp.tool()
async def comfy_wait_for_run(run_id: str) -> dict[str, Any]:
    ctx = tool_context()
    record = read_run(ctx.config.runs_dir, run_id)
    prompt_id = record.get("prompt_id")
    client_id = record.get("client_id") or f"comfydex-{uuid.uuid4()}"
    if not prompt_id:
        raise ValueError("run does not have a prompt_id")

    update_status(ctx.config.runs_dir, run_id, "running")

    async def on_event(event: dict[str, Any]) -> None:
        append_event(ctx.config.runs_dir, run_id, event)

    async def fallback() -> dict[str, Any]:
        async with ComfyClient(
            ctx.config.base_url,
            ctx.config.headers,
            ctx.config.request_timeout_seconds,
        ) as client:
            return {
                "queue": await client.get_queue(),
                "history": await client.get_history(prompt_id),
            }

    try:
        result = await wait_for_prompt(
            base_url=ctx.config.base_url,
            prompt_id=prompt_id,
            client_id=client_id,
            headers=ctx.config.headers,
            timeout_seconds=ctx.config.websocket_timeout_seconds,
            on_event=on_event,
            fallback=fallback,
        )
        fallback_status = _fallback_history_status(result, prompt_id)
        if result.get("fallback_used") and fallback_status is None:
            async with ComfyClient(
                ctx.config.base_url,
                ctx.config.headers,
                ctx.config.request_timeout_seconds,
            ) as client:
                poll_result = await _poll_history_until_terminal(
                    client=client,
                    prompt_id=prompt_id,
                    timeout_seconds=ctx.config.websocket_timeout_seconds,
                )
            result = {
                **result,
                **poll_result,
                "initial_fallback": result.get("fallback"),
            }
    except Exception:
        update_status(ctx.config.runs_dir, run_id, "failed")
        raise

    fallback_status = _fallback_history_status(result, prompt_id)
    if result.get("completed") or fallback_status == "completed":
        update_status(ctx.config.runs_dir, run_id, "completed")
    elif fallback_status == "failed":
        update_status(ctx.config.runs_dir, run_id, "failed")
    elif result.get("fallback_used"):
        update_status(ctx.config.runs_dir, run_id, "unknown")
    return read_run(ctx.config.runs_dir, run_id) | {"wait_result": result}


@mcp.tool()
async def comfy_get_queue() -> dict[str, Any]:
    ctx = tool_context()
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        return await client.get_queue()


@mcp.tool()
async def comfy_get_history(prompt_id: str | None = None) -> dict[str, Any]:
    ctx = tool_context()
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        return await client.get_history(prompt_id)


@mcp.tool()
async def comfy_list_runs() -> list[dict[str, Any]]:
    return list_runs(tool_context().config.runs_dir)


@mcp.tool()
async def comfy_read_run(run_id: str) -> dict[str, Any]:
    return read_run(tool_context().config.runs_dir, run_id)


@mcp.tool()
async def comfy_fetch_outputs(
    run_id: str,
    download: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    record = read_run(ctx.config.runs_dir, run_id)
    prompt_id = record.get("prompt_id")
    if not prompt_id:
        raise ValueError("run does not have a prompt_id")

    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        history = await client.get_history(prompt_id)
        refs = extract_output_refs(history, prompt_id)
        registered: list[dict[str, Any]] = []
        output_dir = ctx.config.runs_dir / run_id / "outputs"
        for ref in refs:
            output = dict(ref)
            if download:
                output_type = _safe_output_type(ref.get("type", "output"))
                filename = (
                    ref["filename"]
                    if not ref.get("subfolder")
                    else f"{ref['subfolder']}/{ref['filename']}"
                )
                target = safe_output_path(output_dir, f"{output_type}/{filename}")
                await client.download_output(ref, target)
                output["downloaded_path"] = str(target)
            registered.append(output)
    return register_outputs(ctx.config.runs_dir, run_id, registered)


if __name__ == "__main__":
    mcp.run()
