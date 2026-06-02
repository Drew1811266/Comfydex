from pathlib import Path

import pytest

from comfydex_mcp import server
from comfydex_mcp.runs import create_run, read_run
from comfydex_mcp.server import resolve_workspace, tool_context
from comfydex_mcp.workflows import save_workflow


API_WORKFLOW = {"1": {"class_type": "SaveImage", "inputs": {}}}


def test_resolve_workspace_uses_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    assert resolve_workspace() == tmp_path.resolve()


def test_tool_context_loads_default_config(tmp_path: Path):
    ctx = tool_context(tmp_path)
    assert ctx.config.base_url == "http://127.0.0.1:8188"
    assert ctx.config.workflows_dir == tmp_path / "workflows"


@pytest.mark.asyncio
async def test_submit_workflow_rejects_missing_prompt_id(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "wf.json", API_WORKFLOW, require_api=True)

    class MissingPromptClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def submit_prompt(self, workflow, client_id):
            return {}

    monkeypatch.setattr(server, "ComfyClient", MissingPromptClient)

    with pytest.raises(ValueError, match="prompt_id"):
        await server.comfy_submit_workflow("wf.json")

    runs_dir = tmp_path / "runs"
    assert not runs_dir.exists() or list(runs_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_wait_for_run_marks_fallback_error_failed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    run = create_run(
        tmp_path / "runs",
        "wf.json",
        API_WORKFLOW,
        "http://127.0.0.1:8188",
        "p1",
        "client-1",
    )

    async def fake_wait_for_prompt(**kwargs):
        return {
            "completed": False,
            "fallback_used": True,
            "fallback": {
                "history": {
                    "p1": {
                        "status": {
                            "status_str": "error",
                        },
                    },
                },
            },
        }

    monkeypatch.setattr(server, "wait_for_prompt", fake_wait_for_prompt)

    result = await server.comfy_wait_for_run(run["run_id"])

    assert result["status"] == "failed"
    assert read_run(tmp_path / "runs", run["run_id"])["status"] == "failed"


@pytest.mark.asyncio
async def test_wait_for_run_marks_fallback_outputs_completed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    run = create_run(
        tmp_path / "runs",
        "wf.json",
        API_WORKFLOW,
        "http://127.0.0.1:8188",
        "p1",
        "client-1",
    )

    async def fake_wait_for_prompt(**kwargs):
        return {
            "completed": False,
            "fallback_used": True,
            "fallback": {
                "history": {
                    "p1": {
                        "outputs": {
                            "9": {
                                "images": [],
                            },
                        },
                    },
                },
            },
        }

    monkeypatch.setattr(server, "wait_for_prompt", fake_wait_for_prompt)

    result = await server.comfy_wait_for_run(run["run_id"])

    assert result["status"] == "completed"
    assert read_run(tmp_path / "runs", run["run_id"])["status"] == "completed"


@pytest.mark.asyncio
async def test_wait_for_run_marks_exception_failed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    run = create_run(
        tmp_path / "runs",
        "wf.json",
        API_WORKFLOW,
        "http://127.0.0.1:8188",
        "p1",
        "client-1",
    )

    async def fake_wait_for_prompt(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "wait_for_prompt", fake_wait_for_prompt)

    with pytest.raises(RuntimeError, match="boom"):
        await server.comfy_wait_for_run(run["run_id"])

    assert read_run(tmp_path / "runs", run["run_id"])["status"] == "failed"


@pytest.mark.asyncio
async def test_fetch_outputs_uses_type_directory_to_avoid_collisions(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    run = create_run(
        tmp_path / "runs",
        "wf.json",
        API_WORKFLOW,
        "http://127.0.0.1:8188",
        "p1",
        "client-1",
    )

    class OutputClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_history(self, prompt_id):
            return {
                "p1": {
                    "outputs": {
                        "9": {
                            "images": [
                                {
                                    "filename": "foo.png",
                                    "subfolder": "",
                                    "type": "output",
                                },
                                {
                                    "filename": "foo.png",
                                    "subfolder": "",
                                    "type": "temp",
                                },
                            ],
                        },
                    },
                },
            }

        async def download_output(self, ref, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(ref["type"], encoding="utf-8")
            return target

    monkeypatch.setattr(server, "ComfyClient", OutputClient)

    result = await server.comfy_fetch_outputs(run["run_id"])

    downloaded_paths = [Path(output["downloaded_path"]) for output in result["outputs"]]
    assert downloaded_paths[0] != downloaded_paths[1]
    assert {path.parts[-2] for path in downloaded_paths} == {"output", "temp"}
    assert {path.read_text(encoding="utf-8") for path in downloaded_paths} == {
        "output",
        "temp",
    }
