from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .analyzer import analyze_workflow
from .assets import (
    compare_assets,
    export_asset_library_report,
    plan_asset_cleanup,
    search_assets,
    summarize_asset_library,
    update_asset_metadata,
    write_asset_sidecars,
)
from .builder import (
    build_workflow_from_plan,
    build_workflow_plan as create_workflow_plan,
)
from .batches import (
    create_batch_record,
    read_batch_record,
    update_batch_run,
    variation_to_operations,
)
from .capabilities import (
    append_install_audit,
    create_install_plan,
    read_install_audit,
    resolve_capabilities,
    scan_model_inventory,
)
from .comfy_client import ComfyClient, extract_output_refs
from .config import ComfydexConfig, load_config, redact_config, save_config
from .conversion import (
    conversion_report_path,
    convert_ui_to_api,
    explain_conversion_gaps,
    save_conversion_report,
)
from .core import project_context_from_config, project_status, reindex_project
from .custom_nodes import (
    check_node_imports,
    inspect_custom_node_package,
    validate_node_class,
    validate_node_mappings,
)
from .diagnostics import compare_runs, diagnose_run
from .generation import (
    build_generated_workflow,
    evaluate_submit_policy,
    plan_workflow_generation,
)
from .live_bridge import (
    explain_canvas_replacement,
    get_live_bridge_status,
    push_live_workflow,
    reload_live_bridge_backend,
    reload_live_bridge_client,
    verify_live_bridge,
)
from .node_docs import generate_node_docs
from .node_contracts import (
    custom_node_repair_guidance,
    generate_node_examples,
    run_node_contract_tests,
)
from .node_semantics import (
    get_node_semantics,
    list_node_semantics,
    match_semantics_to_object_info,
    search_node_semantics,
    validate_semantic_registry,
)
from .outputs import cleanup_outputs, list_outputs as list_run_outputs
from .node_scaffold import scaffold_custom_node_package, safe_custom_nodes_dir
from .patching import patch_workflow
from .paths import is_redirected_path, safe_json_path, safe_output_path, safe_package_dir
from .presets import list_generation_presets
from .readiness import build_20_readiness_report, list_first_class_scenarios
from .recipes import (
    get_workflow_recipe,
    list_workflow_recipes,
    resolve_recipe_capabilities,
    search_workflow_recipes,
    suggest_workflow_recipes,
)
from .reports import export_run_report
from .repairs import (
    append_repair_history,
    build_run_repair_plan,
    read_repair_history,
)
from .runs import (
    append_event,
    create_run,
    list_runs,
    read_run,
    register_outputs,
    run_dir_path,
    update_status,
)
from .templates import (
    explain_workflow_plan,
    list_workflow_templates,
    suggest_workflow_template,
)
from .user_guidance import explain_generation_plan_for_user
from .ui_graphs import (
    append_ui_graph_history,
    build_ui_workflow_from_plan,
    read_ui_graph_history,
    save_generated_ui_workflow,
)
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


def _custom_node_package_path(workspace: Path, package_name: str) -> Path:
    custom_nodes_dir = safe_custom_nodes_dir(workspace)
    return safe_package_dir(custom_nodes_dir, package_name)


def _validate_node_import_options(
    timeout_seconds: int,
    max_output_bytes: int,
) -> None:
    if not 1 <= timeout_seconds <= 30:
        raise ValueError("timeout_seconds must be between 1 and 30")
    if not 0 <= max_output_bytes <= 200000:
        raise ValueError("max_output_bytes must be between 0 and 200000")


def _resolve_config_dir(workspace: Path, value: str | None, current: Path) -> Path:
    if not value:
        return current
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (workspace / raw).resolve()


def _resolve_model_roots(workspace: Path, model_roots: list[str] | None) -> list[Path]:
    if model_roots is None:
        return [(workspace / "models").resolve()]
    roots: list[Path] = []
    for value in model_roots:
        raw = Path(str(value)).expanduser()
        roots.append(raw.resolve() if raw.is_absolute() else (workspace / raw).resolve())
    return roots


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


def _short_wait_message(value: str) -> str:
    text = " ".join(value.split())
    return text[:177].rstrip() + "..." if len(text) > 180 else text


def _wait_texts(value: Any, depth: int = 0) -> list[str]:
    if depth > 5:
        return []
    if isinstance(value, str):
        text = _short_wait_message(value)
        return [text] if text else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        texts: list[str] = []
        for item in value.values():
            texts.extend(_wait_texts(item, depth + 1))
        return texts
    if isinstance(value, (list, tuple)):
        texts = []
        for item in value:
            texts.extend(_wait_texts(item, depth + 1))
        return texts
    return []


def _wait_result_event(result: dict[str, Any], prompt_id: str) -> dict[str, Any]:
    history_status = _fallback_history_status(result, prompt_id)
    if history_status is None and isinstance(result.get("terminal_status"), str):
        terminal_status = result["terminal_status"]
        if terminal_status in {"completed", "failed"}:
            history_status = terminal_status
    event: dict[str, Any] = {
        "type": "wait_result",
        "fallback_used": bool(result.get("fallback_used")),
        "completed": bool(result.get("completed")),
    }
    if history_status is not None:
        event["history_status"] = history_status
    if result.get("timeout") is True:
        event["timeout"] = True
    if isinstance(result.get("polls"), int):
        event["polls"] = result["polls"]
    history = result.get("fallback", {}).get("history", {})
    prompt_history = _prompt_history(history, prompt_id)
    messages = _wait_texts(prompt_history if prompt_history is not None else history)
    if messages:
        seen: set[str] = set()
        event["messages"] = []
        for message in messages:
            if message and message not in seen:
                event["messages"].append(message)
                seen.add(message)
            if len(event["messages"]) >= 5:
                break
    return event


def _same_workflow_path(left: Path, right: Path) -> bool:
    left_resolved = left.resolve()
    right_resolved = right.resolve()
    try:
        if left_resolved.samefile(right_resolved):
            return True
    except OSError:
        pass

    left_text = str(left_resolved)
    right_text = str(right_resolved)
    if os.name == "nt":
        left_text = left_text.casefold()
        right_text = right_text.casefold()
    return left_text == right_text


def _automation_next_actions(
    *,
    status: str,
    policy: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> list[str]:
    actions: list[str] = []
    if status == "requires_confirmation":
        reasons = []
        if isinstance(policy, dict):
            raw_reasons = policy.get("reasons", [])
            if isinstance(raw_reasons, list):
                reasons = [str(reason) for reason in raw_reasons]
        if "workflow_overwrite" in reasons:
            actions.append(
                "Set confirm_risky_actions=true after reviewing policy.reasons to overwrite the existing workflow."
            )
        else:
            actions.append(
                "Set confirm_risky_actions=true only after reviewing policy.reasons and generation.validation."
            )
    elif status == "submitted" and run_id:
        actions.append(f"Run comfy_wait_for_run with run_id {run_id}.")
        actions.append(f"Run comfy_fetch_outputs with run_id {run_id} after completion.")
    elif status == "failed" and run_id:
        actions.append(f"Run comfy_read_run with run_id {run_id}.")
        actions.append(f"Run comfy_diagnose_run with run_id {run_id}.")
    return actions


def _read_run_if_available(runs_dir: Path, run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    try:
        return read_run(runs_dir, run_id)
    except Exception:
        return None


def _failure_repair_payload(
    ctx: ToolContext,
    *,
    run: dict[str, Any] | None,
    stage: str,
    error: str | None = None,
    workflow_name: str | None = None,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return {}

    snapshot = _read_workflow_snapshot(ctx.config.runs_dir, run_id, required=False)
    workflow = snapshot if isinstance(snapshot, dict) else None
    workflow_analysis = (
        analyze_workflow(workflow, object_info) if isinstance(workflow, dict) else None
    )
    diagnosis = diagnose_run(
        run,
        workflow,
        object_info,
        workflow_analysis=workflow_analysis,
    )
    actual_workflow_name = run.get("workflow_name")
    if not isinstance(actual_workflow_name, str) or not actual_workflow_name:
        actual_workflow_name = workflow_name
    repair_plan = build_run_repair_plan(
        run_id,
        diagnosis,
        workflow_name=actual_workflow_name,
        stage=stage,
        error=error,
    )
    diagnosis = {
        **diagnosis,
        "failure_class": repair_plan["failure_class"],
        "repair_summary": repair_plan["summary"],
        "retryable": bool(repair_plan.get("retry", {}).get("supported")),
    }
    history_record = _append_repair_history(
        ctx,
        run_id=run_id,
        workflow_name=actual_workflow_name,
        status=f"{stage}_failed",
        repair_plan=repair_plan,
    )
    return {
        "diagnosis": diagnosis,
        "repair_plan": repair_plan,
        "repair_history_record": history_record,
    }


def _try_reindex(ctx: ToolContext) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return reindex_project(project_context_from_config(ctx.config)), None
    except Exception as exc:
        return None, str(exc)


def _structural_object_info_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    template = plan.get("template", {})
    nodes = template.get("nodes", []) if isinstance(template, dict) else []
    links = template.get("links", []) if isinstance(template, dict) else []
    class_by_key: dict[str, str] = {}
    output_slots_by_class: dict[str, int] = {}

    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            key = node.get("key")
            class_type = node.get("class_type")
            if isinstance(key, str) and isinstance(class_type, str):
                class_by_key[key] = class_type
                output_slots_by_class.setdefault(class_type, 1)

    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            source_class = class_by_key.get(str(link.get("from")))
            output_slot = link.get("output_slot")
            if source_class is not None and isinstance(output_slot, int):
                output_slots_by_class[source_class] = max(
                    output_slots_by_class.get(source_class, 1),
                    output_slot + 1,
                )

    return {
        class_type: {
            "input": {"required": {}},
            "output": ["ANY"] * max(output_slots, 1),
        }
        for class_type, output_slots in sorted(output_slots_by_class.items())
    }


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


def _batch_child_workflow_name(workflow_name: str, batch_id: str, index: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(workflow_name).stem).strip(".-")
    return f"{stem or 'workflow'}.{batch_id}-{index}.json"


def _run_dir_after_read(runs_dir: Path, run_id: str) -> Path:
    return run_dir_path(runs_dir, run_id)


def _run_file_after_read(runs_dir: Path, run_id: str, filename: str) -> Path:
    base = runs_dir.resolve()
    path = _run_dir_after_read(runs_dir, run_id) / filename
    label = "workflow snapshot" if filename == "workflow.json" else f"{filename} snapshot"
    if is_redirected_path(path):
        raise ValueError(f"{label} must stay inside runs_dir")
    try:
        exists = path.exists()
    except OSError as exc:
        raise ValueError(f"{label} could not be inspected") from exc
    if exists:
        try:
            path.resolve().relative_to(base)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f"{label} must stay inside runs_dir") from exc
    return path


def _read_workflow_snapshot(
    runs_dir: Path,
    run_id: str,
    *,
    required: bool,
) -> Any:
    path = _run_file_after_read(runs_dir, run_id, "workflow.json")
    if not path.exists():
        if required:
            raise ValueError(f"workflow snapshot missing for run_id: {run_id}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


async def _diagnose_run_record(
    ctx: ToolContext,
    record: dict[str, Any],
    *,
    use_object_info: bool = True,
) -> dict[str, Any]:
    run_id = str(record.get("run_id") or "")
    workflow = _read_workflow_snapshot(ctx.config.runs_dir, run_id, required=False)
    object_info = None
    if use_object_info:
        async with ComfyClient(
            ctx.config.base_url,
            ctx.config.headers,
            ctx.config.request_timeout_seconds,
        ) as client:
            object_info = await client.get_object_info()
    workflow_analysis = (
        analyze_workflow(workflow, object_info) if isinstance(workflow, dict) else None
    )
    return diagnose_run(record, workflow, object_info, workflow_analysis=workflow_analysis)


def _append_repair_history(
    ctx: ToolContext,
    *,
    run_id: str,
    workflow_name: str | None,
    status: str,
    repair_plan: dict[str, Any],
) -> dict[str, Any]:
    retry = repair_plan.get("retry")
    actions = repair_plan.get("actions")
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "workflow_name": workflow_name,
        "status": status,
        "failure_class": repair_plan.get("failure_class"),
        "retry_supported": bool(isinstance(retry, dict) and retry.get("supported")),
        "action_count": len(actions) if isinstance(actions, list) else 0,
    }
    return append_repair_history(ctx.workspace, record)


def _read_ui_workflow_for_live_bridge(
    config: ComfydexConfig,
    workflow_name: str,
) -> dict[str, Any]:
    workflow_record = read_workflow(config.workflows_dir, workflow_name)
    workflow = workflow_record.get("json")
    if not _is_ui_workflow_json(workflow):
        raise ValueError("workflow_not_ui_json")
    return workflow


def _is_ui_workflow_json(workflow: Any) -> bool:
    return (
        isinstance(workflow, dict)
        and isinstance(workflow.get("nodes"), list)
        and isinstance(workflow.get("links"), list)
    )


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
async def comfy_project_status() -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return project_status(project)


@mcp.tool()
async def comfy_live_bridge_status() -> dict[str, Any]:
    ctx = tool_context()
    return await get_live_bridge_status(ctx.config)


@mcp.tool()
async def comfy_live_bridge_reload_client(
    version: str | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    return await reload_live_bridge_client(ctx.config, version)


@mcp.tool()
async def comfy_live_bridge_reload_backend() -> dict[str, Any]:
    ctx = tool_context()
    return await reload_live_bridge_backend(ctx.config)


@mcp.tool()
async def comfy_live_bridge_push_workflow(
    workflow_name: str,
    force: bool = False,
    activate: bool = True,
    wait_for_ack: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    workflow = _read_ui_workflow_for_live_bridge(ctx.config, workflow_name)
    return await push_live_workflow(
        ctx.config,
        workflow,
        name=workflow_name,
        activate=activate,
        force=force,
        wait_for_ack=wait_for_ack,
    )


@mcp.tool()
async def comfy_live_bridge_verify(
    workflow_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    if workflow_name is None:
        return await verify_live_bridge(ctx.config, None, force=force)
    workflow = _read_ui_workflow_for_live_bridge(ctx.config, workflow_name)
    return await verify_live_bridge(
        ctx.config,
        workflow,
        name=workflow_name,
        force=force,
    )


@mcp.tool()
async def comfy_reindex_project(include_outputs: bool = True) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return reindex_project(project, include_outputs=include_outputs)


@mcp.tool()
async def comfy_reindex_assets(include_sidecars: bool = False) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    result = reindex_project(project, include_outputs=True)
    sidecars = (
        write_asset_sidecars(project)
        if include_sidecars
        else {"written_count": 0, "written": [], "errors": []}
    )
    return {
        **result,
        "asset_count": result["counts"].get("assets", 0),
        "sidecar_count": sidecars["written_count"],
        "sidecars": sidecars,
    }


@mcp.tool()
async def comfy_search_assets(
    query: str | None = None,
    run_id: str | None = None,
    workflow_name: str | None = None,
    status: str | None = None,
    type: str | None = None,
    tags: list[str] | None = None,
    favorite: bool | None = None,
    min_rating: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    filters = {
        "query": query,
        "run_id": run_id,
        "workflow_name": workflow_name,
        "status": status,
        "type": type,
        "tags": tags,
        "favorite": favorite,
        "min_rating": min_rating,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "offset": offset,
    }
    return search_assets(project, filters)


@mcp.tool()
async def comfy_summarize_assets(
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return summarize_asset_library(project, filters)


@mcp.tool()
async def comfy_update_asset_metadata(
    asset_id: str,
    tags: list[str] | None = None,
    rating: int | None = None,
    favorite: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return update_asset_metadata(
        project,
        asset_id,
        tags=tags,
        rating=rating,
        favorite=favorite,
        notes=notes,
    )


@mcp.tool()
async def comfy_write_asset_sidecars(
    asset_ids: list[str] | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return write_asset_sidecars(project, asset_ids=asset_ids)


@mcp.tool()
async def comfy_plan_asset_cleanup(
    filters: dict[str, Any] | None = None,
    asset_ids: list[str] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return plan_asset_cleanup(
        project,
        filters=filters,
        asset_ids=asset_ids,
        confirm=confirm,
    )


@mcp.tool()
async def comfy_export_asset_library_report(
    filters: dict[str, Any] | None = None,
) -> dict[str, str]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return export_asset_library_report(project, filters=filters)


@mcp.tool()
async def comfy_compare_assets(
    left_asset_id: str,
    right_asset_id: str,
) -> dict[str, Any]:
    ctx = tool_context()
    project = project_context_from_config(ctx.config)
    return compare_assets(project, left_asset_id, right_asset_id)


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
async def comfy_model_inventory(
    model_roots: list[str] | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    return scan_model_inventory(_resolve_model_roots(ctx.workspace, model_roots))


@mcp.tool()
async def comfy_resolve_capabilities(
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    model_roots: list[str] | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    model_inventory = scan_model_inventory(
        _resolve_model_roots(ctx.workspace, model_roots)
    )
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    return resolve_capabilities(
        intent,
        parameters,
        object_info,
        model_inventory,
        template_id=template_id,
    )


@mcp.tool()
async def comfy_create_install_plan(
    capability_report: dict[str, Any],
) -> dict[str, Any]:
    return create_install_plan(capability_report)


@mcp.tool()
async def comfy_record_install_audit(
    install_plan: dict[str, Any],
    decision: str,
) -> dict[str, Any]:
    ctx = tool_context()
    return append_install_audit(ctx.workspace, install_plan, decision)


@mcp.tool()
async def comfy_read_install_audit(limit: int = 20) -> dict[str, Any]:
    ctx = tool_context()
    return read_install_audit(ctx.workspace, limit)


@mcp.tool()
async def comfy_list_workflow_recipes() -> dict[str, Any]:
    recipes = list_workflow_recipes()
    return {"recipe_count": len(recipes), "recipes": recipes}


@mcp.tool()
async def comfy_search_workflow_recipes(query: str) -> dict[str, Any]:
    recipes = search_workflow_recipes(query)
    return {"query": query, "recipe_count": len(recipes), "recipes": recipes}


@mcp.tool()
async def comfy_explain_workflow_recipe(recipe_id: str) -> dict[str, Any]:
    recipe = get_workflow_recipe(recipe_id)
    if recipe is None:
        return {"status": "unsupported", "recipe_id": recipe_id}
    return {"status": "supported", "recipe": recipe}


@mcp.tool()
async def comfy_suggest_workflow_recipes(
    intent: str,
    parameters: dict[str, Any] | None = None,
    recipe_id: str | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    suggestions = suggest_workflow_recipes(
        intent,
        parameters,
        recipe_id=recipe_id,
        limit=limit,
    )
    return {
        "intent": intent,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
    }


@mcp.tool()
async def comfy_resolve_recipe_capabilities(
    recipe_id: str,
    parameters: dict[str, Any] | None = None,
    model_roots: list[str] | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    model_inventory = scan_model_inventory(
        _resolve_model_roots(ctx.workspace, model_roots)
    )
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    return resolve_recipe_capabilities(
        recipe_id,
        parameters,
        object_info,
        model_inventory,
    )


@mcp.tool()
async def comfy_list_20_scenarios() -> dict[str, Any]:
    scenarios = list_first_class_scenarios()
    return {"scenario_count": len(scenarios), "scenarios": scenarios}


@mcp.tool()
async def comfy_20_readiness_report() -> dict[str, Any]:
    return build_20_readiness_report()


@mcp.tool()
async def comfy_list_node_semantics() -> dict[str, Any]:
    entries = list_node_semantics()
    return {"entry_count": len(entries), "entries": entries}


@mcp.tool()
async def comfy_explain_node_semantics(node_type: str) -> dict[str, Any]:
    entry = get_node_semantics(node_type)
    if entry is None:
        return {
            "status": "unsupported",
            "node_type": node_type,
            "message": "Comfydex does not have first-class semantic support for this node.",
        }
    return {"status": "supported", "entry": entry}


@mcp.tool()
async def comfy_search_node_semantics(query: str) -> dict[str, Any]:
    entries = search_node_semantics(query)
    return {"query": query, "entry_count": len(entries), "entries": entries}


@mcp.tool()
async def comfy_validate_node_semantics() -> dict[str, Any]:
    ctx = tool_context()
    registry_report = validate_semantic_registry()
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    object_report = match_semantics_to_object_info(object_info)
    return {"registry": registry_report, **object_report}


@mcp.tool()
async def comfy_scaffold_custom_node_package(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return scaffold_custom_node_package(ctx.workspace, package_name)


@mcp.tool()
async def comfy_inspect_custom_node_package(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return inspect_custom_node_package(
        _custom_node_package_path(ctx.workspace, package_name)
    )


@mcp.tool()
async def comfy_validate_node_mappings(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return validate_node_mappings(_custom_node_package_path(ctx.workspace, package_name))


@mcp.tool()
async def comfy_validate_node_class(
    package_name: str,
    class_name: str,
) -> dict[str, Any]:
    ctx = tool_context()
    return validate_node_class(
        _custom_node_package_path(ctx.workspace, package_name),
        class_name,
    )


@mcp.tool()
async def comfy_generate_node_docs(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return generate_node_docs(_custom_node_package_path(ctx.workspace, package_name))


@mcp.tool()
async def comfy_check_node_imports(
    package_name: str,
    timeout_seconds: int = 5,
    max_output_bytes: int = 20000,
) -> dict[str, Any]:
    ctx = tool_context()
    package_dir = _custom_node_package_path(ctx.workspace, package_name)
    _validate_node_import_options(timeout_seconds, max_output_bytes)
    return check_node_imports(
        package_dir,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


@mcp.tool()
async def comfy_generate_node_examples(
    package_name: str,
    class_name: str,
) -> dict[str, Any]:
    ctx = tool_context()
    return generate_node_examples(
        _custom_node_package_path(ctx.workspace, package_name),
        class_name,
    )


@mcp.tool()
async def comfy_run_node_contract_tests(
    package_name: str,
    class_name: str,
    timeout_seconds: int = 5,
    max_output_bytes: int = 20000,
) -> dict[str, Any]:
    ctx = tool_context()
    _validate_node_import_options(timeout_seconds, max_output_bytes)
    return run_node_contract_tests(
        _custom_node_package_path(ctx.workspace, package_name),
        class_name,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


@mcp.tool()
async def comfy_custom_node_repair_guidance(package_name: str) -> dict[str, Any]:
    ctx = tool_context()
    return custom_node_repair_guidance(
        _custom_node_package_path(ctx.workspace, package_name)
    )


@mcp.tool()
async def comfy_list_workflow_templates() -> list[dict[str, Any]]:
    return list_workflow_templates()


@mcp.tool()
async def comfy_suggest_workflow_template(intent: str) -> dict[str, Any]:
    return suggest_workflow_template(intent)


@mcp.tool()
async def comfy_build_workflow_plan(
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    return create_workflow_plan(intent, template_id, parameters or {})


@mcp.tool()
async def comfy_explain_workflow_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return explain_workflow_plan(plan)


@mcp.tool()
async def comfy_plan_workflow_generation(
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return plan_workflow_generation(intent, parameters, template_id, constraints)


@mcp.tool()
async def comfy_list_generation_presets() -> dict[str, Any]:
    return list_generation_presets()


@mcp.tool()
async def comfy_explain_user_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return explain_generation_plan_for_user(plan)


@mcp.tool()
async def comfy_generate_workflow(
    name: str,
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    constraints: dict[str, Any] | None = None,
    allow_draft: bool = False,
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    target_path = safe_json_path(ctx.config.workflows_dir, name)
    plan = plan_workflow_generation(intent, parameters, template_id, constraints)
    object_info: dict[str, Any] = {}
    if use_object_info:
        async with ComfyClient(
            ctx.config.base_url,
            ctx.config.headers,
            ctx.config.request_timeout_seconds,
        ) as client:
            object_info = await client.get_object_info()

    result = build_generated_workflow(
        plan,
        object_info,
        target_exists=target_path.exists(),
        allow_draft=allow_draft,
    )
    if result.get("workflow") is not None and result["policy"]["decision"] == "allowed":
        path = save_workflow(
            ctx.config.workflows_dir,
            name,
            result["workflow"],
            require_api=True,
            source="generated",
            validation_status=result["status"],
        )
        result["saved_workflow"] = path.name
        try:
            reindex_project(project_context_from_config(ctx.config))
        except Exception as exc:
            result["index_warning"] = str(exc)
    elif (
        allow_draft
        and result.get("draft_workflow") is not None
        and (not target_path.exists() or bool(plan["constraints"].get("allow_overwrite")))
    ):
        path = save_workflow(
            ctx.config.workflows_dir,
            name,
            result["draft_workflow"],
            require_api=True,
            source="generated",
            validation_status=result["status"],
        )
        result["saved_workflow"] = path.name
        result["draft_saved"] = True
    elif allow_draft and result.get("draft_workflow") is not None:
        result["draft_saved"] = False
        result["draft_save_blocked"] = "workflow_overwrite"
    return result


@mcp.tool()
async def comfy_build_ui_workflow(
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    ctx = tool_context()
    plan = plan_workflow_generation(intent, parameters, template_id)
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    result = build_ui_workflow_from_plan(plan, object_info=object_info)
    result["plan"] = plan
    return result


@mcp.tool()
async def comfy_generate_ui_workflow(
    name: str,
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    confirm_overwrite: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    target_path = safe_json_path(ctx.config.workflows_dir, name)
    if target_path.exists() and not confirm_overwrite:
        return {
            "status": "requires_confirmation",
            "workflow_name": name,
            "policy": {
                "decision": "requires_confirmation",
                "reasons": ["workflow_overwrite"],
            },
        }

    plan = plan_workflow_generation(intent, parameters, template_id)
    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()
    result = save_generated_ui_workflow(
        ctx.workspace,
        ctx.config.workflows_dir,
        name,
        plan,
        object_info=object_info,
    )
    result["plan"] = plan
    if result["status"] == "saved":
        index_result, index_warning = _try_reindex(ctx)
        if index_result is not None:
            result["index"] = index_result
        if index_warning is not None:
            result["index_warning"] = index_warning
    return result


@mcp.tool()
async def comfy_read_ui_graph_history(limit: int = 20) -> dict[str, Any]:
    ctx = tool_context()
    return read_ui_graph_history(ctx.workspace, limit)


@mcp.tool()
async def comfy_generate_push_ui_workflow(
    name: str,
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    confirm_overwrite: bool = False,
    force: bool = False,
    activate: bool = True,
    wait_for_ack: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    saved = await comfy_generate_ui_workflow(
        name,
        intent,
        parameters,
        template_id,
        confirm_overwrite=confirm_overwrite,
    )
    if saved.get("status") != "saved":
        return saved

    workflow = saved["workflow"]
    push_result = await push_live_workflow(
        ctx.config,
        workflow,
        name=name,
        activate=activate,
        force=force,
        wait_for_ack=wait_for_ack,
    )
    canvas_replacement = explain_canvas_replacement(
        push_result,
        workflow_name=name,
        force=force,
    )
    summary = saved.get("summary", {})
    history_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow_name": name,
        "path": saved.get("path"),
        "status": "pushed",
        "template_id": summary.get("template_id"),
        "recipe_id": summary.get("recipe_id"),
        "node_count": summary.get("node_count"),
        "link_count": summary.get("link_count"),
        "push_result": push_result,
    }
    append_ui_graph_history(ctx.workspace, history_record)
    saved["status"] = "pushed" if push_result.get("ok") else "push_failed"
    saved["push_result"] = push_result
    saved["canvas_replacement"] = canvas_replacement
    saved["push_history_record"] = history_record
    return saved


@mcp.tool()
async def comfy_evaluate_submit_policy(
    name: str,
    constraints: dict[str, Any] | None = None,
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, name)
    if loaded["kind"] != "api":
        return evaluate_submit_policy(
            validation={"status": "invalid", "errors": [], "warnings": []},
            submit_ready=False,
            constraints=constraints or {},
            issues=["workflow_not_api"],
        )

    if use_object_info:
        try:
            async with ComfyClient(
                ctx.config.base_url,
                ctx.config.headers,
                ctx.config.request_timeout_seconds,
            ) as client:
                object_info = await client.get_object_info()
            validation = validate_api_workflow(loaded["json"], object_info)
        except Exception as exc:
            return evaluate_submit_policy(
                validation={
                    "status": "not_run",
                    "errors": [],
                    "warnings": [{"reason": "object_info_unavailable", "error": str(exc)}],
                },
                submit_ready=False,
                constraints=constraints or {},
                issues=["unknown_validation"],
            )
    else:
        validation = validate_api_workflow(loaded["json"], {})
    return evaluate_submit_policy(
        validation=validation,
        submit_ready=validation["status"] == "valid",
        constraints=constraints or {},
    )


@mcp.tool()
async def comfy_generate_run_fetch(
    name: str,
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    constraints: dict[str, Any] | None = None,
    run_label: str | None = None,
    confirm_risky_actions: bool = False,
    wait_for_completion: bool = True,
    fetch_outputs: bool = True,
    download_outputs: bool = True,
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    target_path = safe_json_path(ctx.config.workflows_dir, name)
    plan = plan_workflow_generation(intent, parameters, template_id, constraints)
    object_info: dict[str, Any] = {}
    policy_issues: list[str] = []
    object_info_warning: dict[str, str] | None = None

    if use_object_info:
        try:
            async with ComfyClient(
                ctx.config.base_url,
                ctx.config.headers,
                ctx.config.request_timeout_seconds,
            ) as client:
                object_info = await client.get_object_info()
        except Exception as exc:
            object_info_warning = {
                "reason": "object_info_unavailable",
                "error": str(exc),
            }
            policy_issues.append("object_info_unavailable")
            object_info = _structural_object_info_from_plan(plan)

    generation = build_generated_workflow(
        plan,
        object_info,
        target_exists=target_path.exists(),
        allow_draft=False,
    )
    if policy_issues:
        generation["policy"] = evaluate_submit_policy(
            validation=generation["validation"],
            submit_ready=bool(generation["submit_ready"]),
            constraints=generation["plan"]["constraints"],
            target_exists=target_path.exists(),
            issues=policy_issues,
        )
    policy = generation["policy"]
    response: dict[str, Any] = {
        "status": "blocked",
        "stage": "policy",
        "workflow_name": name,
        "policy": policy,
        "generation": generation,
        "user_guidance": generation.get("plan", {}).get("user_guidance"),
        "next_actions": [],
    }
    if object_info_warning is not None:
        response["object_info_warning"] = object_info_warning

    if policy["decision"] == "blocked" or generation.get("workflow") is None:
        response["status"] = "blocked"
        response["next_actions"] = [
            "Review generation.validation, generation.gaps, and policy.reasons before trying again."
        ]
        return response

    if policy["decision"] == "requires_confirmation" and not confirm_risky_actions:
        response["status"] = "requires_confirmation"
        response["next_actions"] = _automation_next_actions(
            status="requires_confirmation",
            policy=policy,
        )
        return response

    saved = save_workflow(
        ctx.config.workflows_dir,
        name,
        generation["workflow"],
        require_api=True,
        source="generated",
        validation_status=generation["status"],
    )
    response["stage"] = "save"
    response["saved_workflow"] = saved.name
    index_result, index_warning = _try_reindex(ctx)
    if index_result is not None:
        response["index"] = index_result
    if index_warning is not None:
        response["index_warning"] = index_warning

    try:
        submitted = await comfy_submit_workflow(
            saved.name,
            run_label=run_label or Path(name).stem,
        )
    except Exception as exc:
        run_id = getattr(exc, "run_id", None)
        run = _read_run_if_available(ctx.config.runs_dir, run_id)
        repair_payload = _failure_repair_payload(
            ctx,
            run=run,
            stage="submit",
            error=str(exc),
            workflow_name=saved.name,
            object_info=object_info,
        )
        response.update(
            {
                "status": "failed",
                "stage": "submit",
                "error": str(exc),
                "run": run,
                **repair_payload,
                "next_actions": _automation_next_actions(
                    status="failed",
                    run_id=run_id if isinstance(run_id, str) else None,
                ),
            }
        )
        return response

    response["run"] = submitted
    run_id = submitted.get("run_id") if isinstance(submitted, dict) else None
    if not isinstance(run_id, str) or not run_id:
        response.update(
            {
                "status": "failed",
                "stage": "submit",
                "error": "comfy_submit_workflow returned no run_id",
            }
        )
        return response

    if not wait_for_completion:
        response.update(
            {
                "status": "submitted",
                "stage": "submit",
                "next_actions": _automation_next_actions(
                    status="submitted",
                    run_id=run_id,
                ),
            }
        )
        return response

    try:
        waited = await comfy_wait_for_run(run_id)
    except Exception as exc:
        run = _read_run_if_available(ctx.config.runs_dir, run_id)
        repair_payload = _failure_repair_payload(
            ctx,
            run=run,
            stage="wait",
            error=str(exc),
            workflow_name=saved.name,
            object_info=object_info,
        )
        response.update(
            {
                "status": "failed",
                "stage": "wait",
                "error": str(exc),
                "run": run,
                **repair_payload,
                "next_actions": _automation_next_actions(
                    status="failed",
                    run_id=run_id,
                ),
            }
        )
        return response

    response["run"] = waited
    run_status = waited.get("status") if isinstance(waited, dict) else None
    if run_status != "completed":
        repair_payload = (
            _failure_repair_payload(
                ctx,
                run=waited,
                stage="wait",
                workflow_name=saved.name,
                object_info=object_info,
            )
            if run_status == "failed"
            else {}
        )
        response.update(
            {
                "status": "failed" if run_status == "failed" else "submitted",
                "stage": "wait",
                **repair_payload,
                "next_actions": _automation_next_actions(
                    status="failed" if run_status == "failed" else "submitted",
                    run_id=run_id,
                ),
            }
        )
        return response

    if fetch_outputs:
        try:
            response["outputs"] = await comfy_fetch_outputs(
                run_id,
                download=download_outputs,
            )
        except Exception as exc:
            run = _read_run_if_available(ctx.config.runs_dir, run_id) or waited
            repair_payload = _failure_repair_payload(
                ctx,
                run=run,
                stage="fetch",
                error=str(exc),
                workflow_name=saved.name,
                object_info=object_info,
            )
            response.update(
                {
                    "status": "failed",
                    "stage": "fetch",
                    "error": str(exc),
                    "run": run,
                    **repair_payload,
                    "next_actions": [
                        f"Run comfy_fetch_outputs with run_id {run_id} after resolving the fetch error.",
                        f"Run comfy_read_run with run_id {run_id}.",
                    ],
                }
            )
            return response

    index_result, index_warning = _try_reindex(ctx)
    if index_result is not None:
        response["index"] = index_result
    if index_warning is not None:
        response["index_warning"] = index_warning
    if fetch_outputs:
        try:
            response["output_summary"] = summarize_asset_library(
                project_context_from_config(ctx.config),
                {"run_id": run_id, "limit": 50, "offset": 0},
            )["summary"]
        except Exception as exc:
            response["output_summary_warning"] = str(exc)
    response.update(
        {
            "status": "completed",
            "stage": "completed",
            "next_actions": [],
        }
    )
    return response


@mcp.tool()
async def comfy_build_workflow(
    name: str,
    intent: str,
    parameters: dict[str, Any] | None = None,
    template_id: str | None = None,
    allow_draft: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    safe_json_path(ctx.config.workflows_dir, name)

    plan = create_workflow_plan(intent, template_id, parameters or {})
    if plan.get("missing_information"):
        return build_workflow_from_plan(plan, {})

    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()

    result = build_workflow_from_plan(plan, object_info)
    workflow_to_save = result["workflow"]
    draft_saved = False
    if workflow_to_save is None and allow_draft:
        workflow_to_save = result.get("draft_workflow")
        draft_saved = workflow_to_save is not None

    if workflow_to_save is not None and (result["submit_ready"] or draft_saved):
        validation = result.get("validation")
        validation_status = (
            validation["status"]
            if isinstance(validation, dict) and isinstance(validation.get("status"), str)
            else result["status"]
        )
        save_workflow(
            ctx.config.workflows_dir,
            name,
            workflow_to_save,
            require_api=True,
            source="generated",
            validation_status=validation_status,
        )
        result["saved_workflow"] = name
        if draft_saved:
            result["draft_saved"] = True

    return result


@mcp.tool()
async def comfy_patch_workflow(
    name: str,
    operations: Any,
    target_name: str | None = None,
    allow_draft: bool = False,
) -> dict[str, Any]:
    ctx = tool_context()
    loaded = read_workflow(ctx.config.workflows_dir, name)
    if loaded["kind"] != "api":
        raise ValueError("comfy_patch_workflow requires ComfyUI API prompt JSON")
    source_path = safe_json_path(ctx.config.workflows_dir, name)
    if target_name is not None:
        target_path = safe_json_path(ctx.config.workflows_dir, target_name)
        if _same_workflow_path(source_path, target_path):
            raise ValueError(
                "target workflow name must differ from source workflow name"
            )

    preflight = patch_workflow(
        loaded["json"],
        operations,
        object_info=None,
        raise_on_error=False,
    )
    if preflight["status"] == "failed":
        return preflight

    async with ComfyClient(
        ctx.config.base_url,
        ctx.config.headers,
        ctx.config.request_timeout_seconds,
    ) as client:
        object_info = await client.get_object_info()

    result = patch_workflow(
        loaded["json"],
        operations,
        object_info,
        raise_on_error=False,
    )
    if result["submit_ready"] or (allow_draft and result["status"] == "invalid"):
        validation = result.get("validation")
        validation_status = (
            validation["status"]
            if isinstance(validation, dict) and isinstance(validation.get("status"), str)
            else result["status"]
        )
        saved_name = target_name or name
        save_workflow(
            ctx.config.workflows_dir,
            saved_name,
            result["workflow"],
            require_api=True,
            source="patched",
            validation_status=validation_status,
        )
        result["saved_workflow"] = saved_name
        if not result["submit_ready"]:
            result["draft_saved"] = True

    return result


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
async def comfy_validate_workflow_against_object_info(name: str) -> dict[str, Any]:
    return await comfy_validate_api_workflow(name)


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
    source_path = safe_json_path(ctx.config.workflows_dir, source_name)
    try:
        target_path = safe_json_path(ctx.config.workflows_dir, target_name)
    except ValueError:
        candidate_path = ctx.config.workflows_dir / target_name
        if (
            target_name
            and target_name == Path(target_name).name
            and _same_workflow_path(source_path, candidate_path)
        ):
            raise ValueError(
                "target workflow name must differ from source workflow name"
            ) from None
        raise
    if _same_workflow_path(source_path, target_path):
        raise ValueError("target workflow name must differ from source workflow name")
    draft_name = f"{Path(target_name).stem}.converted-draft.json"
    if allow_draft:
        draft_path = safe_json_path(ctx.config.workflows_dir, draft_name)
        if _same_workflow_path(source_path, draft_path) or _same_workflow_path(
            target_path,
            draft_path,
        ):
            raise ValueError(
                "draft workflow name must differ from source and target workflow names"
            )

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
    elif allow_draft and result["draft_workflow"] is not None:
        save_workflow(
            ctx.config.workflows_dir,
            draft_name,
            result["draft_workflow"],
            require_api=True,
            source="converted",
            validation_status=result["report"]["status"],
        )
        result["draft_saved"] = True
        result["draft_workflow_name"] = draft_name

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
    safe_json_path(ctx.config.workflows_dir, name)

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
    if loaded.get("metadata", {}).get("submit_ready", True) is False:
        raise ValueError(
            "comfy_submit_workflow requires a submit-ready API workflow"
        )

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
            try:
                setattr(exc, "run_id", failed_run["run_id"])
            except Exception:
                pass
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
async def comfy_batch_submit(
    workflow_name: str,
    variations: list[dict[str, Any]],
    batch_label: str = "batch",
) -> dict[str, Any]:
    ctx = tool_context()
    batch = create_batch_record(
        ctx.config.runs_dir,
        batch_label,
        workflow_name,
        variations,
    )
    batch_id = batch["batch_id"]

    for index, variation in enumerate(variations):
        run_id: str | None = None
        try:
            loaded = read_workflow(ctx.config.workflows_dir, workflow_name)
            if loaded["kind"] != "api":
                raise ValueError("comfy_batch_submit requires ComfyUI API prompt JSON")

            operations = variation_to_operations(variation)
            patched = patch_workflow(
                loaded["json"],
                operations,
                object_info=None,
                raise_on_error=False,
            )
            if patched["status"] != "patched":
                raise ValueError(f"workflow patch failed: {patched['report']!r}")

            child_name = _batch_child_workflow_name(workflow_name, batch_id, index)
            save_workflow(
                ctx.config.workflows_dir,
                child_name,
                patched["workflow"],
                require_api=True,
                source="patched",
                validation_status="unknown",
            )
            submitted = await comfy_submit_workflow(
                child_name,
                run_label=f"{batch_id}-{index}",
            )
            submitted_run_id = (
                submitted.get("run_id") if isinstance(submitted, dict) else None
            )
            if not isinstance(submitted_run_id, str) or not submitted_run_id:
                raise ValueError("comfy_submit_workflow returned no run_id")
            run_id = submitted_run_id
            submitted_status = (
                submitted.get("status") if isinstance(submitted, dict) else None
            )
            if submitted_status is None:
                submitted_status = "queued"
            if not isinstance(submitted_status, str):
                raise ValueError("comfy_submit_workflow returned invalid status")
            batch = update_batch_run(
                ctx.config.runs_dir,
                batch_id,
                index,
                run_id,
                submitted_status,
            )
        except Exception as exc:
            exc_run_id = getattr(exc, "run_id", None)
            if isinstance(exc_run_id, str) and exc_run_id:
                run_id = exc_run_id
            batch = update_batch_run(
                ctx.config.runs_dir,
                batch_id,
                index,
                run_id,
                "failed",
                error=str(exc),
            )
            continue

    return batch


@mcp.tool()
async def comfy_read_batch(batch_id: str) -> dict[str, Any]:
    return read_batch_record(tool_context().config.runs_dir, batch_id)


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
        result: dict[str, Any] | None = None
        try:
            initial_fallback = await fallback()
        except Exception:
            initial_fallback = None
        if initial_fallback is not None:
            initial_status = _history_status(initial_fallback.get("history", {}), prompt_id)
            if initial_status in {"completed", "failed"}:
                result = {
                    "completed": initial_status == "completed",
                    "fallback_used": True,
                    "terminal_status": initial_status,
                    "fallback": initial_fallback,
                    "preflight": True,
                }
        if result is None:
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
    append_event(ctx.config.runs_dir, run_id, _wait_result_event(result, prompt_id))
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
async def comfy_diagnose_run(
    run_id: str,
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    record = read_run(ctx.config.runs_dir, run_id)
    return await _diagnose_run_record(ctx, record, use_object_info=use_object_info)


@mcp.tool()
async def comfy_plan_run_repair(
    run_id: str,
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    record = read_run(ctx.config.runs_dir, run_id)
    diagnosis = await _diagnose_run_record(ctx, record, use_object_info=use_object_info)
    workflow_name = record.get("workflow_name")
    repair_plan = build_run_repair_plan(
        run_id,
        diagnosis,
        workflow_name=workflow_name if isinstance(workflow_name, str) else None,
    )
    history_record = _append_repair_history(
        ctx,
        run_id=run_id,
        workflow_name=workflow_name if isinstance(workflow_name, str) else None,
        status="planned",
        repair_plan=repair_plan,
    )
    return {
        "status": "planned",
        "run_id": run_id,
        "diagnosis": diagnosis,
        "repair_plan": repair_plan,
        "history_record": history_record,
    }


@mcp.tool()
async def comfy_read_repair_history(limit: int = 20) -> dict[str, Any]:
    return read_repair_history(tool_context().workspace, limit)


@mcp.tool()
async def comfy_retry_run_repair(
    run_id: str,
    confirm: bool = False,
    use_object_info: bool = True,
) -> dict[str, Any]:
    ctx = tool_context()
    planned = await comfy_plan_run_repair(run_id, use_object_info=use_object_info)
    repair_plan = planned["repair_plan"]
    retry = repair_plan.get("retry", {})
    if not isinstance(retry, dict) or not retry.get("supported"):
        return {
            "status": "blocked",
            "run_id": run_id,
            "diagnosis": planned["diagnosis"],
            "repair_plan": repair_plan,
            "next_actions": ["Review repair_plan.actions before retrying."],
        }
    if retry.get("requires_confirmation") and not confirm:
        return {
            "status": "requires_confirmation",
            "run_id": run_id,
            "diagnosis": planned["diagnosis"],
            "repair_plan": repair_plan,
        }

    operation = retry.get("operation")
    if operation == "fetch_outputs":
        retry_result = await comfy_fetch_outputs(run_id)
    elif operation == "resubmit_workflow":
        workflow_name = repair_plan.get("workflow_name")
        if not isinstance(workflow_name, str) or not workflow_name:
            return {
                "status": "blocked",
                "run_id": run_id,
                "diagnosis": planned["diagnosis"],
                "repair_plan": repair_plan,
                "next_actions": ["Repair retry requires a workflow_name."],
            }
        retry_result = await comfy_submit_workflow(
            workflow_name,
            run_label=f"{run_id}-repair",
        )
    else:
        return {
            "status": "blocked",
            "run_id": run_id,
            "diagnosis": planned["diagnosis"],
            "repair_plan": repair_plan,
            "next_actions": [f"Unsupported repair retry operation: {operation}"],
        }

    history_record = _append_repair_history(
        ctx,
        run_id=run_id,
        workflow_name=repair_plan.get("workflow_name")
        if isinstance(repair_plan.get("workflow_name"), str)
        else None,
        status="retried",
        repair_plan=repair_plan,
    )
    return {
        "status": "retried",
        "run_id": run_id,
        "diagnosis": planned["diagnosis"],
        "repair_plan": repair_plan,
        "retry_result": retry_result,
        "history_record": history_record,
    }


@mcp.tool()
async def comfy_export_run_report(run_id: str) -> dict[str, Any]:
    ctx = tool_context()
    record = read_run(ctx.config.runs_dir, run_id)
    workflow = _read_workflow_snapshot(ctx.config.runs_dir, run_id, required=True)
    analysis = analyze_workflow(workflow)
    diagnosis = diagnose_run(record, workflow, workflow_analysis=analysis)
    workflow_summary = (
        analysis.get("summary", {"node_count": 0})
        if isinstance(analysis, dict)
        else {"node_count": 0}
    )
    run_dir = _run_dir_after_read(ctx.config.runs_dir, run_id)
    return export_run_report(run_dir, record, workflow_summary, diagnosis)


@mcp.tool()
async def comfy_compare_runs(left_run_id: str, right_run_id: str) -> dict[str, Any]:
    ctx = tool_context()
    left_run = read_run(ctx.config.runs_dir, left_run_id)
    right_run = read_run(ctx.config.runs_dir, right_run_id)
    left_workflow = _read_workflow_snapshot(
        ctx.config.runs_dir,
        left_run_id,
        required=True,
    )
    right_workflow = _read_workflow_snapshot(
        ctx.config.runs_dir,
        right_run_id,
        required=True,
    )
    return compare_runs(left_run, right_run, left_workflow, right_workflow)


@mcp.tool()
async def comfy_list_outputs() -> list[dict[str, Any]]:
    return list_run_outputs(tool_context().config.runs_dir)


@mcp.tool()
async def comfy_cleanup_outputs(
    confirm: bool = False,
    failed_run_ids: list[str] | None = None,
    older_than_seconds: int | None = None,
) -> dict[str, Any]:
    return cleanup_outputs(
        tool_context().config.runs_dir,
        confirm=confirm,
        failed_run_ids=failed_run_ids,
        older_than_seconds=older_than_seconds,
    )


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
