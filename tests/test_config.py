from pathlib import Path

import pytest

from comfydex_mcp.config import (
    ComfydexConfig,
    load_config,
    redact_config,
    save_config,
)


def test_load_config_defaults_to_local_comfyui(tmp_path: Path):
    cfg = load_config(tmp_path)

    assert cfg.base_url == "http://127.0.0.1:8188"
    assert cfg.workflows_dir == tmp_path / "workflows"
    assert cfg.runs_dir == tmp_path / "runs"
    assert cfg.headers == {}
    assert cfg.request_timeout_seconds == 30
    assert cfg.websocket_timeout_seconds == 600


def test_save_and_load_config_with_headers(tmp_path: Path):
    cfg = ComfydexConfig(
        workspace=tmp_path,
        base_url="https://comfy.example.test",
        workflows_dir=tmp_path / "wf",
        runs_dir=tmp_path / "run-records",
        headers={"Authorization": "Bearer secret"},
        request_timeout_seconds=10,
        websocket_timeout_seconds=120,
    )

    save_config(cfg)
    loaded = load_config(tmp_path)

    assert loaded.base_url == "https://comfy.example.test"
    assert loaded.headers == {"Authorization": "Bearer secret"}
    assert loaded.workflows_dir == tmp_path / "wf"
    assert loaded.runs_dir == tmp_path / "run-records"


def test_redact_config_hides_header_values(tmp_path: Path):
    cfg = ComfydexConfig(
        workspace=tmp_path,
        base_url="http://127.0.0.1:8188",
        workflows_dir=tmp_path / "workflows",
        runs_dir=tmp_path / "runs",
        headers={"Authorization": "Bearer secret", "X-Gateway": "abc"},
        request_timeout_seconds=30,
        websocket_timeout_seconds=600,
    )

    redacted = redact_config(cfg)

    assert redacted["headers"] == {
        "Authorization": "<redacted>",
        "X-Gateway": "<redacted>",
    }


@pytest.mark.parametrize("base_url", ["ftp://example.test", "example.test", ""])
def test_invalid_base_url_rejected(tmp_path: Path, base_url: str):
    with pytest.raises(ValueError, match="base_url"):
        ComfydexConfig(
            workspace=tmp_path,
            base_url=base_url,
            workflows_dir=tmp_path / "workflows",
            runs_dir=tmp_path / "runs",
            headers={},
            request_timeout_seconds=30,
            websocket_timeout_seconds=600,
        )


def test_timeout_must_be_positive(tmp_path: Path):
    with pytest.raises(ValueError, match="timeout"):
        ComfydexConfig(
            workspace=tmp_path,
            base_url="http://127.0.0.1:8188",
            workflows_dir=tmp_path / "workflows",
            runs_dir=tmp_path / "runs",
            headers={},
            request_timeout_seconds=0,
            websocket_timeout_seconds=600,
        )
