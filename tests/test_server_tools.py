import json
from pathlib import Path

import pytest

from comfydex_mcp import server
from comfydex_mcp.runs import create_run, read_run
from comfydex_mcp.server import resolve_workspace, tool_context
from comfydex_mcp.workflows import save_workflow


API_WORKFLOW = {"1": {"class_type": "SaveImage", "inputs": {}}}
UI_WORKFLOW = {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []}


def test_resolve_workspace_uses_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    assert resolve_workspace() == tmp_path.resolve()


def test_tool_context_loads_default_config(tmp_path: Path):
    ctx = tool_context(tmp_path)
    assert ctx.config.base_url == "http://127.0.0.1:8188"
    assert ctx.config.workflows_dir == tmp_path / "workflows"


@pytest.mark.asyncio
async def test_comfy_classify_workflow_tool():
    result = await server.comfy_classify_workflow(
        {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []}
    )

    assert result["kind"] == "ui"
    assert "nodes is a list" in result["evidence"]


@pytest.mark.asyncio
async def test_comfy_import_ui_workflow_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    result = await server.comfy_import_ui_workflow(
        "sample.ui.json",
        {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []},
        use_object_info=False,
    )

    assert result["metadata"]["kind"] == "ui"
    assert (tmp_path / "workflows" / "sample.ui.json").exists()


@pytest.mark.asyncio
async def test_comfy_import_ui_workflow_rejects_api_before_object_info(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("remote called before payload validation")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(ValueError, match="requires ComfyUI UI workflow JSON"):
        await server.comfy_import_ui_workflow(
            "bad.ui.json",
            API_WORKFLOW,
            use_object_info=True,
        )


@pytest.mark.asyncio
async def test_comfy_import_ui_workflow_rejects_bad_name_before_object_info(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("remote called before path validation")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(ValueError, match="simple .json filename"):
        await server.comfy_import_ui_workflow(
            "../escape.json",
            UI_WORKFLOW,
            use_object_info=True,
        )


@pytest.mark.asyncio
async def test_comfy_import_ui_workflow_uses_object_info_for_readiness(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    calls = []

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            calls.append("get_object_info")
            return {"SaveImage": {}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)

    result = await server.comfy_import_ui_workflow(
        "sample.ui.json",
        {
            "nodes": [
                {"id": 1, "type": "SaveImage"},
                {"id": 2, "type": "CustomNode"},
            ],
            "links": [],
        },
        use_object_info=True,
    )

    assert calls == ["get_object_info"]
    assert result["readiness"]["known_node_types"] == ["SaveImage"]
    assert result["readiness"]["unknown_node_types"] == ["CustomNode"]
    assert result["readiness"]["conversion_ready"] is False


@pytest.mark.asyncio
async def test_comfy_validate_api_workflow_tool(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "wf.json", API_WORKFLOW)

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            return {"SaveImage": {"input": {"required": {}}}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    result = await server.comfy_validate_api_workflow("wf.json")
    assert result["status"] == "valid"


@pytest.mark.asyncio
async def test_comfy_validate_api_workflow_rejects_ui_before_object_info(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "ui.json", UI_WORKFLOW)

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("remote called before payload validation")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(ValueError, match="requires ComfyUI API prompt JSON"):
        await server.comfy_validate_api_workflow("ui.json")


@pytest.mark.asyncio
async def test_comfy_convert_ui_to_api_writes_api_when_valid(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(
        tmp_path / "workflows",
        "sample.ui.json",
        {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": []}], "links": []},
    )

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            return {"SaveImage": {"input": {"required": {}}}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    result = await server.comfy_convert_ui_to_api("sample.ui.json", "sample.api.json")

    assert result["report"]["status"] == "converted"
    assert (tmp_path / "workflows" / "sample.api.json").exists()
    loaded = server.read_workflow(tmp_path / "workflows", "sample.api.json")
    assert loaded["metadata"]["source"] == "converted"
    assert loaded["metadata"]["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_comfy_convert_ui_to_api_failure_writes_report_not_api(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(
        tmp_path / "workflows",
        "bad.ui.json",
        {"nodes": [{"id": 1, "type": "CustomNode"}], "links": []},
    )

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            return {"SaveImage": {"input": {"required": {}}}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    result = await server.comfy_convert_ui_to_api("bad.ui.json", "bad.api.json")

    assert result["report"]["status"] == "failed"
    assert (tmp_path / "workflows" / ".reports" / "bad.ui.conversion.json").exists()
    assert not (tmp_path / "workflows" / "bad.api.json").exists()


@pytest.mark.asyncio
async def test_comfy_convert_ui_to_api_allow_draft_saves_non_submit_ready_draft(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(
        tmp_path / "workflows",
        "partial.ui.json",
        {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": []}], "links": []},
    )

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            return {"SaveImage": {"input": {"required": {"images": ("IMAGE",)}}}}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    result = await server.comfy_convert_ui_to_api(
        "partial.ui.json",
        "partial.api.json",
        allow_draft=True,
    )

    assert result["report"]["status"] == "partial"
    assert result["draft_workflow"] is not None
    assert result["draft_saved"] is True
    assert result["draft_workflow_name"] == "partial.api.converted-draft.json"
    assert (tmp_path / "workflows" / ".reports" / "partial.ui.conversion.json").exists()
    assert not (tmp_path / "workflows" / "partial.api.json").exists()
    assert (tmp_path / "workflows" / "partial.api.converted-draft.json").exists()

    draft = server.read_workflow(
        tmp_path / "workflows", "partial.api.converted-draft.json"
    )
    assert draft["metadata"]["source"] == "converted"
    assert draft["metadata"]["validation_status"] == "partial"
    assert draft["metadata"]["submit_ready"] is False

    class DraftShouldNotBeSubmitted:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("draft should not be submitted")

    monkeypatch.setattr(server, "ComfyClient", DraftShouldNotBeSubmitted)
    with pytest.raises(
        ValueError,
        match="comfy_submit_workflow requires a submit-ready API workflow",
    ):
        await server.comfy_submit_workflow("partial.api.converted-draft.json")

    draft_metadata = (
        tmp_path
        / "workflows"
        / ".metadata"
        / "partial.api.converted-draft.metadata.json"
    )
    draft_metadata.unlink()
    with pytest.raises(
        ValueError,
        match="comfy_submit_workflow requires a submit-ready API workflow",
    ):
        await server.comfy_submit_workflow("partial.api.converted-draft.json")

    draft_metadata.write_text("{", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match="comfy_submit_workflow requires a submit-ready API workflow",
    ):
        await server.comfy_submit_workflow("partial.api.converted-draft.json")


@pytest.mark.asyncio
async def test_comfy_explain_conversion_gaps_reads_saved_report(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(
        tmp_path / "workflows",
        "bad.ui.json",
        {"nodes": [{"id": 1, "type": "CustomNode"}], "links": []},
    )

    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            return {}

    monkeypatch.setattr(server, "ComfyClient", ObjectInfoClient)
    await server.comfy_convert_ui_to_api("bad.ui.json", "bad.api.json")

    result = await server.comfy_explain_conversion_gaps("bad.ui.json")

    assert result["gap_count"] >= 1
    assert "CustomNode" in result["summary"]


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
async def test_wait_for_run_polls_fallback_until_outputs_completed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    run = create_run(
        tmp_path / "runs",
        "wf.json",
        API_WORKFLOW,
        "http://127.0.0.1:8188",
        "p1",
        "client-1",
    )
    history_calls = 0

    class PollingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_queue(self):
            return {"queue_running": [], "queue_pending": [["p1"]]}

        async def get_history(self, prompt_id):
            nonlocal history_calls
            history_calls += 1
            if history_calls == 1:
                return {"p1": {"status": {"status_str": "running"}}}
            return {"p1": {"outputs": {"9": {"images": []}}}}

    async def fake_wait_for_prompt(**kwargs):
        return {
            "completed": False,
            "fallback_used": True,
            "fallback": await kwargs["fallback"](),
        }

    monkeypatch.setattr(server, "ComfyClient", PollingClient)
    monkeypatch.setattr(server, "wait_for_prompt", fake_wait_for_prompt)

    result = await server.comfy_wait_for_run(run["run_id"])

    assert result["status"] == "completed"
    assert history_calls >= 2
    assert read_run(tmp_path / "runs", run["run_id"])["status"] == "completed"


@pytest.mark.asyncio
async def test_wait_for_run_polls_fallback_until_error_failed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    run = create_run(
        tmp_path / "runs",
        "wf.json",
        API_WORKFLOW,
        "http://127.0.0.1:8188",
        "p1",
        "client-1",
    )
    history_calls = 0

    class PollingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_queue(self):
            return {"queue_running": [], "queue_pending": [["p1"]]}

        async def get_history(self, prompt_id):
            nonlocal history_calls
            history_calls += 1
            if history_calls == 1:
                return {"p1": {"status": {"status_str": "running"}}}
            return {"p1": {"status": {"status_str": "error"}}}

    async def fake_wait_for_prompt(**kwargs):
        return {
            "completed": False,
            "fallback_used": True,
            "fallback": await kwargs["fallback"](),
        }

    monkeypatch.setattr(server, "ComfyClient", PollingClient)
    monkeypatch.setattr(server, "wait_for_prompt", fake_wait_for_prompt)

    result = await server.comfy_wait_for_run(run["run_id"])

    assert result["status"] == "failed"
    assert history_calls >= 2
    assert read_run(tmp_path / "runs", run["run_id"])["status"] == "failed"


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
async def test_submit_workflow_records_failed_run_on_http_error(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "wf.json", API_WORKFLOW, require_api=True)

    class FailingSubmitClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def submit_prompt(self, workflow, client_id):
            raise RuntimeError("submit exploded")

    monkeypatch.setattr(server, "ComfyClient", FailingSubmitClient)

    with pytest.raises(RuntimeError, match="submit exploded"):
        await server.comfy_submit_workflow("wf.json")

    run_paths = list((tmp_path / "runs").glob("*/run.json"))
    assert len(run_paths) == 1
    record = json.loads(run_paths[0].read_text(encoding="utf-8"))
    workflow_snapshot = json.loads(
        (run_paths[0].parent / "workflow.json").read_text(encoding="utf-8")
    )
    assert record["status"] == "failed"
    assert record["prompt_id"] is None
    assert record["workflow_name"] == "wf.json"
    assert workflow_snapshot == API_WORKFLOW
    assert any("submit exploded" in json.dumps(event) for event in record["events"])


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
