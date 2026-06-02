from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONFIG_FILENAME = "comfydex.config.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8188"


@dataclass(frozen=True)
class ComfydexConfig:
    workspace: Path
    base_url: str
    workflows_dir: Path
    runs_dir: Path
    headers: dict[str, str]
    request_timeout_seconds: int
    websocket_timeout_seconds: int

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute http(s) URL")
        if self.request_timeout_seconds <= 0 or self.websocket_timeout_seconds <= 0:
            raise ValueError("timeout values must be positive")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in self.headers.items()):
            raise ValueError("headers must be a mapping of strings to strings")


def _resolve_dir(workspace: Path, value: str | None, default_name: str) -> Path:
    raw = Path(value or default_name).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (workspace / raw).resolve()


def load_config(workspace: Path, config_path: Path | None = None) -> ComfydexConfig:
    workspace = workspace.resolve()
    path = config_path or workspace / CONFIG_FILENAME
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("comfydex config must be a JSON object")

    return ComfydexConfig(
        workspace=workspace,
        base_url=str(payload.get("base_url", DEFAULT_BASE_URL)).rstrip("/"),
        workflows_dir=_resolve_dir(workspace, payload.get("workflows_dir"), "workflows"),
        runs_dir=_resolve_dir(workspace, payload.get("runs_dir"), "runs"),
        headers=dict(payload.get("headers", {})),
        request_timeout_seconds=int(payload.get("request_timeout_seconds", 30)),
        websocket_timeout_seconds=int(payload.get("websocket_timeout_seconds", 600)),
    )


def save_config(config: ComfydexConfig, config_path: Path | None = None) -> Path:
    path = config_path or config.workspace / CONFIG_FILENAME
    payload: dict[str, Any] = {
        "base_url": config.base_url,
        "workflows_dir": str(config.workflows_dir),
        "runs_dir": str(config.runs_dir),
        "headers": config.headers,
        "request_timeout_seconds": config.request_timeout_seconds,
        "websocket_timeout_seconds": config.websocket_timeout_seconds,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def redact_config(config: ComfydexConfig) -> dict[str, Any]:
    return {
        "base_url": config.base_url,
        "workflows_dir": str(config.workflows_dir),
        "runs_dir": str(config.runs_dir),
        "headers": {key: "<redacted>" for key in sorted(config.headers)},
        "request_timeout_seconds": config.request_timeout_seconds,
        "websocket_timeout_seconds": config.websocket_timeout_seconds,
    }
