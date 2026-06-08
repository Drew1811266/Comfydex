from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .assets import search_assets
from .comfy_client import ComfyClient
from .config import ComfydexConfig, load_config, redact_config, save_config
from .core import project_context_from_config, project_status, reindex_project
from .paths import is_redirected_path
from .runs import list_runs
from .workflows import list_workflows


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
    if operation == "list_workflows":
        return list_workflows(config.workflows_dir)
    if operation == "list_runs":
        return list_runs(config.runs_dir)
    if operation == "search_assets":
        return search_assets(project, payload)
    raise ValueError(f"unsupported desktop bridge operation: {operation}")


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
        return await client.check_connection()


def _workspace_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if is_redirected_path(path):
        raise ValueError("workspace must not be redirected")
    return path


if __name__ == "__main__":
    sys.exit(main())
