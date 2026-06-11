from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assets import (
    compare_assets,
    export_asset_library_report,
    plan_asset_cleanup,
    search_assets,
    update_asset_metadata,
)
from .batches import read_batch_record
from .comfy_client import ComfyClient
from .config import ComfydexConfig, load_config, redact_config, save_config
from .core import project_context_from_config, project_status, reindex_project
from .live_bridge import (
    get_live_bridge_status,
    push_live_workflow,
    reload_live_bridge_backend,
    reload_live_bridge_client,
    verify_live_bridge,
)
from .paths import is_redirected_path
from .runs import list_runs
from .workflows import list_workflows, read_workflow


def run_bridge_operation(
    operation: str,
    workspace: str | Path,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        data = _dispatch(operation, _workspace_path(workspace), payload or {})
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }
    return {"ok": True, "data": data}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="comfydex-desktop-bridge")
    parser.add_argument("operation")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--payload-json", default="{}")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.payload_json)
    except json.JSONDecodeError as exc:
        result = {
            "ok": False,
            "error": {"type": "JSONDecodeError", "message": str(exc)},
        }
    else:
        result = run_bridge_operation(args.operation, args.workspace, payload)
    print(json.dumps(result, sort_keys=True))
    return 0


def _dispatch(
    operation: str,
    workspace: Path,
    payload: dict[str, Any],
) -> Any:
    config = load_config(workspace)
    project = project_context_from_config(config)

    if operation == "project_status":
        return project_status(project)
    if operation == "reindex_project":
        include_outputs = bool(payload.get("include_outputs", True))
        return reindex_project(project, include_outputs=include_outputs)
    if operation == "get_config":
        return redact_config(config)
    if operation == "set_config":
        updated = _updated_config(config, payload)
        save_config(updated)
        return redact_config(updated)
    if operation == "check_connection":
        return asyncio.run(_check_connection(config))
    if operation == "live_bridge_status":
        return asyncio.run(get_live_bridge_status(config))
    if operation == "live_bridge_reload_client":
        return asyncio.run(
            reload_live_bridge_client(config, _optional_string(payload.get("version")))
        )
    if operation == "live_bridge_reload_backend":
        return asyncio.run(reload_live_bridge_backend(config))
    if operation == "live_bridge_push_workflow":
        workflow_name = str(payload.get("workflow_name", ""))
        workflow = _read_ui_workflow_for_live_bridge(config, workflow_name)
        return asyncio.run(
            push_live_workflow(
                config,
                workflow,
                name=workflow_name,
                activate=bool(payload.get("activate", True)),
                force=bool(payload.get("force", False)),
                wait_for_ack=bool(payload.get("wait_for_ack", True)),
            )
        )
    if operation == "live_bridge_verify":
        workflow_name = _optional_string(payload.get("workflow_name"))
        force = bool(payload.get("force", False))
        if workflow_name is None:
            return asyncio.run(verify_live_bridge(config, None, force=force))
        workflow = _read_ui_workflow_for_live_bridge(config, workflow_name)
        return asyncio.run(
            verify_live_bridge(
                config,
                workflow,
                name=workflow_name,
                force=force,
            )
        )
    if operation == "list_workflows":
        return list_workflows(config.workflows_dir)
    if operation == "list_runs":
        return list_runs(config.runs_dir)
    if operation == "search_assets":
        return search_assets(project, payload)
    if operation == "update_asset_metadata":
        return _update_asset_metadata(project, payload)
    if operation == "plan_asset_cleanup":
        return plan_asset_cleanup(
            project,
            filters=payload.get("filters"),
            asset_ids=payload.get("asset_ids"),
            confirm=bool(payload.get("confirm", False)),
        )
    if operation == "export_asset_library_report":
        filters = payload.get("filters") if "filters" in payload else payload
        return export_asset_library_report(project, filters=filters)
    if operation == "compare_assets":
        return compare_assets(
            project,
            str(payload.get("left_asset_id", "")),
            str(payload.get("right_asset_id", "")),
        )
    if operation == "list_batches":
        return _list_batches(config.runs_dir)
    if operation == "read_batch":
        return read_batch_record(config.runs_dir, str(payload.get("batch_id", "")))
    raise ValueError(f"unsupported desktop bridge operation: {operation}")


def _update_asset_metadata(project: Any, payload: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(payload.get("asset_id", ""))
    kwargs = {
        key: payload[key]
        for key in ("tags", "rating", "favorite", "notes")
        if key in payload
    }
    return update_asset_metadata(project, asset_id, **kwargs)


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


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _updated_config(
    config: ComfydexConfig,
    payload: dict[str, Any],
) -> ComfydexConfig:
    return ComfydexConfig(
        workspace=config.workspace,
        base_url=str(payload.get("base_url", config.base_url)).rstrip("/"),
        workflows_dir=_config_dir(
            config.workspace,
            payload.get("workflows_dir"),
            config.workflows_dir,
        ),
        runs_dir=_config_dir(config.workspace, payload.get("runs_dir"), config.runs_dir),
        headers=payload.get("headers", config.headers),
        request_timeout_seconds=int(
            payload.get(
                "request_timeout_seconds",
                config.request_timeout_seconds,
            )
        ),
        websocket_timeout_seconds=int(
            payload.get(
                "websocket_timeout_seconds",
                config.websocket_timeout_seconds,
            )
        ),
    )


def _config_dir(workspace: Path, value: Any, current: Path) -> Path:
    if value is None:
        return current
    raw = Path(str(value)).expanduser()
    return raw.resolve() if raw.is_absolute() else (workspace / raw).resolve()


async def _check_connection(config: ComfydexConfig) -> dict[str, Any]:
    async with ComfyClient(
        config.base_url,
        config.headers,
        config.request_timeout_seconds,
    ) as client:
        result = await client.check_connection()

    reachable = bool(result.get("reachable"))
    message = "Connected" if reachable else _connection_error_message(result)
    return {
        "ok": reachable,
        "base_url": result.get("base_url", config.base_url),
        "message": message,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "details": result,
    }


def _connection_error_message(result: dict[str, Any]) -> str:
    error_type = str(result.get("error_type") or "ConnectionError")
    error = str(result.get("error") or error_type)
    return f"{error_type}: {error}"


def _list_batches(runs_dir: Path) -> list[dict[str, Any]]:
    runs_base = runs_dir.resolve()
    batches_dir = (runs_base / ".batches").resolve()
    if not batches_dir.exists():
        return []
    if is_redirected_path(batches_dir) or not _is_relative_to(batches_dir, runs_base):
        raise ValueError(".batches directory must stay inside runs_dir")

    batches: list[dict[str, Any]] = []
    for record_path in sorted(batches_dir.glob("*/batch.json")):
        try:
            if is_redirected_path(record_path) or not _is_relative_to(
                record_path.resolve(),
                batches_dir,
            ):
                continue
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if isinstance(record, dict):
                batches.append(_batch_summary(record))
        except (OSError, json.JSONDecodeError, ValueError):
            continue

    batches.sort(
        key=lambda batch: (
            str(batch.get("updated_at") or ""),
            str(batch.get("batch_id") or ""),
        ),
        reverse=True,
    )
    return batches


def _batch_summary(record: dict[str, Any]) -> dict[str, Any]:
    runs = record.get("runs") if isinstance(record.get("runs"), list) else []
    completed = sum(1 for run in runs if isinstance(run, dict) and run.get("status") == "completed")
    failed = sum(1 for run in runs if isinstance(run, dict) and run.get("status") == "failed")
    return {
        "batch_id": str(record.get("batch_id", "")),
        "label": str(record.get("label", "")),
        "workflow_name": str(record.get("workflow_name", "")),
        "status": str(record.get("status", "unknown")),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "run_count": len(runs),
        "completed_count": completed,
        "failed_count": failed,
    }


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _workspace_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if is_redirected_path(path):
        raise ValueError("workspace must not be redirected")
    return path


if __name__ == "__main__":
    sys.exit(main())
