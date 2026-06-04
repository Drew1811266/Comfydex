import json
from pathlib import Path

import pytest

from comfydex_mcp import server
from comfydex_mcp.runs import create_run, read_run
from comfydex_mcp.server import resolve_workspace, tool_context
from comfydex_mcp.workflows import save_workflow


API_WORKFLOW = {"1": {"class_type": "SaveImage", "inputs": {}}}
UI_WORKFLOW = {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []}
PATCH_OBJECT_INFO = {
    "ImageSource": {"input": {"required": {}}, "output": ["IMAGE"]},
    "SaveImage": {
        "input": {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING",),
            }
        },
        "output": [],
    },
}
TEXT_TO_IMAGE_OBJECT_INFO = {
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": ("STRING",)}},
        "output": ["MODEL", "CLIP", "VAE"],
    },
    "CLIPTextEncode": {
        "input": {"required": {"text": ("STRING",), "clip": ("CLIP",)}},
        "output": ["CONDITIONING"],
    },
    "EmptyLatentImage": {
        "input": {
            "required": {
                "width": ("INT",),
                "height": ("INT",),
                "batch_size": ("INT",),
            }
        },
        "output": ["LATENT"],
    },
    "KSampler": {
        "input": {
            "required": {
                "model": ("MODEL",),
                "seed": ("INT",),
                "steps": ("INT",),
                "cfg": ("FLOAT",),
                "sampler_name": ("STRING",),
                "scheduler": ("STRING",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "denoise": ("FLOAT",),
            }
        },
        "output": ["LATENT"],
    },
    "VAEDecode": {
        "input": {"required": {"samples": ("LATENT",), "vae": ("VAE",)}},
        "output": ["IMAGE"],
    },
    "SaveImage": {
        "input": {
            "required": {"images": ("IMAGE",), "filename_prefix": ("STRING",)}
        },
        "output": [],
    },
}


def object_info_client(object_info: dict):
    class ObjectInfoClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_object_info(self):
            return object_info

    return ObjectInfoClient


@pytest.mark.asyncio
async def test_comfy_scaffold_custom_node_package_tool_creates_package(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))

    result = await server.comfy_scaffold_custom_node_package("simple_math")

    package_dir = tmp_path / "custom_nodes" / "simple_math"
    assert result["package_dir"] == str(package_dir)
    assert result["mapping_key"] == "SimpleMathNode"
    assert result["class_name"] == "SimpleMathNode"
    assert (package_dir / "__init__.py").exists()
    assert (package_dir / "nodes.py").exists()


@pytest.mark.asyncio
async def test_comfy_custom_node_tools_use_package_name(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    scaffolded = await server.comfy_scaffold_custom_node_package("simple_math")

    inspected = await server.comfy_inspect_custom_node_package("simple_math")
    mappings = await server.comfy_validate_node_mappings("simple_math")
    node_class = await server.comfy_validate_node_class(
        "simple_math",
        scaffolded["class_name"],
    )
    docs = await server.comfy_generate_node_docs("simple_math")
    imports = await server.comfy_check_node_imports("simple_math")

    assert inspected["package_dir"] == scaffolded["package_dir"]
    assert inspected["class_mappings"] == {
        scaffolded["mapping_key"]: scaffolded["class_name"]
    }
    assert mappings["status"] == "valid"
    assert node_class["status"] == "valid"
    assert docs["path"] == str(Path(scaffolded["package_dir"]) / "NODE_DOCS.md")
    assert imports["status"] == "passed"


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout_seconds", [0, -1, 31])
async def test_comfy_check_node_imports_rejects_invalid_timeout_before_import_check(
    monkeypatch,
    tmp_path: Path,
    timeout_seconds: int,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    import_check_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal import_check_called
        import_check_called = True
        raise AssertionError("import check should not run")

    monkeypatch.setattr(server, "check_node_imports", fail_if_called)

    with pytest.raises(ValueError, match="timeout_seconds must be between 1 and 30"):
        await server.comfy_check_node_imports(
            "simple_math",
            timeout_seconds=timeout_seconds,
        )

    assert import_check_called is False


@pytest.mark.asyncio
@pytest.mark.parametrize("max_output_bytes", [-1, 200001])
async def test_comfy_check_node_imports_rejects_invalid_output_limit_before_import_check(
    monkeypatch,
    tmp_path: Path,
    max_output_bytes: int,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    import_check_called = False

    def fail_if_called(*args, **kwargs):
        nonlocal import_check_called
        import_check_called = True
        raise AssertionError("import check should not run")

    monkeypatch.setattr(server, "check_node_imports", fail_if_called)

    with pytest.raises(ValueError, match="max_output_bytes must be between 0 and 200000"):
        await server.comfy_check_node_imports(
            "simple_math",
            max_output_bytes=max_output_bytes,
        )

    assert import_check_called is False


@pytest.mark.asyncio
async def test_comfy_custom_node_tool_rejects_unsafe_package_name(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))

    with pytest.raises(ValueError, match="package name"):
        await server.comfy_inspect_custom_node_package("../escape")


@pytest.mark.asyncio
async def test_comfy_custom_node_tool_rejects_redirected_custom_nodes_dir(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    custom_nodes = tmp_path / "custom_nodes"
    custom_nodes.mkdir()

    def fake_is_symlink(path: Path):
        return path == custom_nodes

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(ValueError, match="custom_nodes directory must be workspace-local"):
        await server.comfy_inspect_custom_node_package("simple_math")


@pytest.mark.asyncio
async def test_comfy_custom_node_tool_is_registered_with_mcp(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    await server.comfy_scaffold_custom_node_package("simple_math")

    _content, structured = await server.mcp.call_tool(
        "comfy_validate_node_mappings",
        {"package_name": "simple_math"},
    )

    assert structured["status"] == "valid"


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
async def test_comfy_validate_workflow_against_object_info_alias(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "wf.json", API_WORKFLOW)
    monkeypatch.setattr(
        server,
        "ComfyClient",
        object_info_client({"SaveImage": {"input": {"required": {}}}}),
    )

    result = await server.comfy_validate_workflow_against_object_info("wf.json")

    assert result["status"] == "valid"


@pytest.mark.asyncio
async def test_comfy_list_workflow_templates_tool():
    result = await server.comfy_list_workflow_templates()

    assert any(template["id"] == "basic-text-to-image" for template in result)


@pytest.mark.asyncio
async def test_comfy_suggest_workflow_template_tool():
    result = await server.comfy_suggest_workflow_template("upscale this image")

    assert result["id"] == "upscale"


@pytest.mark.asyncio
async def test_comfy_build_workflow_plan_tool_does_not_write_or_call_remote(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("plan should not call remote object_info")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    result = await server.comfy_build_workflow_plan(
        "Create text to image",
        {"positive_prompt": "a quiet studio", "width": 512},
    )

    assert result["template"]["id"] == "basic-text-to-image"
    assert result["parameters"]["width"] == 512
    assert "checkpoint_name" in result["missing_information"]
    assert not (tmp_path / "workflows").exists()


@pytest.mark.asyncio
async def test_comfy_explain_workflow_plan_tool():
    plan = await server.comfy_build_workflow_plan(
        "Create text to image",
        {"positive_prompt": "a quiet studio"},
    )

    result = await server.comfy_explain_workflow_plan(plan)

    assert result["selected_template"]["id"] == "basic-text-to-image"
    assert "checkpoint_name" in result["missing_information"]


@pytest.mark.asyncio
async def test_comfy_build_workflow_saves_valid_generated_workflow(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        server,
        "ComfyClient",
        object_info_client(TEXT_TO_IMAGE_OBJECT_INFO),
    )

    result = await server.comfy_build_workflow(
        "generated.json",
        "Create text to image",
        {
            "checkpoint_name": "dream.safetensors",
            "positive_prompt": "a quiet studio",
        },
    )

    assert result["status"] == "valid"
    assert result["submit_ready"] is True
    assert result["saved_workflow"] == "generated.json"
    loaded = server.read_workflow(tmp_path / "workflows", "generated.json")
    assert loaded["metadata"]["source"] == "generated"
    assert loaded["metadata"]["validation_status"] == "valid"
    assert loaded["metadata"]["submit_ready"] is True


@pytest.mark.asyncio
async def test_comfy_build_workflow_missing_information_does_not_save(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("missing information should not call remote object_info")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    result = await server.comfy_build_workflow(
        "missing.json",
        "Create text to image",
        {"positive_prompt": "a quiet studio"},
    )

    assert result["status"] == "missing_information"
    assert result["submit_ready"] is False
    assert "saved_workflow" not in result
    assert not (tmp_path / "workflows" / "missing.json").exists()


@pytest.mark.asyncio
async def test_comfy_build_workflow_allow_draft_saves_invalid_non_submit_ready_workflow(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        server,
        "ComfyClient",
        object_info_client(TEXT_TO_IMAGE_OBJECT_INFO),
    )

    result = await server.comfy_build_workflow(
        "draft.json",
        "Create text to image",
        {
            "checkpoint_name": "dream.safetensors",
            "positive_prompt": "a quiet studio",
            "width": "wide",
        },
        allow_draft=True,
    )

    assert result["status"] == "invalid"
    assert result["submit_ready"] is False
    assert result["workflow"] is None
    assert result["draft_saved"] is True
    loaded = server.read_workflow(tmp_path / "workflows", "draft.json")
    assert loaded["metadata"]["source"] == "generated"
    assert loaded["metadata"]["validation_status"] == "invalid"
    assert loaded["metadata"]["submit_ready"] is False


@pytest.mark.asyncio
async def test_comfy_patch_workflow_saves_valid_patch_to_target(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    original = {
        "1": {"class_type": "ImageSource", "inputs": {}},
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "old"},
        },
    }
    save_workflow(tmp_path / "workflows", "source.json", original, require_api=True)
    monkeypatch.setattr(server, "ComfyClient", object_info_client(PATCH_OBJECT_INFO))

    result = await server.comfy_patch_workflow(
        "source.json",
        [{"op": "set_input", "node_id": "2", "input": "filename_prefix", "value": "new"}],
        target_name="patched.json",
    )

    assert result["status"] == "patched"
    assert result["submit_ready"] is True
    assert result["saved_workflow"] == "patched.json"
    assert server.read_workflow(tmp_path / "workflows", "source.json")["json"] == original
    patched = server.read_workflow(tmp_path / "workflows", "patched.json")
    assert patched["json"]["2"]["inputs"]["filename_prefix"] == "new"
    assert patched["metadata"]["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_comfy_patch_workflow_invalid_patch_does_not_save_without_draft(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    workflow = {
        "1": {"class_type": "ImageSource", "inputs": {}},
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "old"},
        },
    }
    save_workflow(tmp_path / "workflows", "source.json", workflow, require_api=True)
    monkeypatch.setattr(server, "ComfyClient", object_info_client(PATCH_OBJECT_INFO))

    result = await server.comfy_patch_workflow(
        "source.json",
        [{"op": "remove_input", "node_id": "2", "input": "images"}],
        target_name="invalid.json",
    )

    assert result["status"] == "invalid"
    assert result["submit_ready"] is False
    assert "saved_workflow" not in result
    assert not (tmp_path / "workflows" / "invalid.json").exists()


@pytest.mark.asyncio
async def test_comfy_patch_workflow_allow_draft_saves_invalid_non_submit_ready_workflow(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    workflow = {
        "1": {"class_type": "ImageSource", "inputs": {}},
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "old"},
        },
    }
    save_workflow(tmp_path / "workflows", "source.json", workflow, require_api=True)
    monkeypatch.setattr(server, "ComfyClient", object_info_client(PATCH_OBJECT_INFO))

    result = await server.comfy_patch_workflow(
        "source.json",
        [{"op": "remove_input", "node_id": "2", "input": "images"}],
        target_name="draft.json",
        allow_draft=True,
    )

    assert result["status"] == "invalid"
    assert result["submit_ready"] is False
    assert result["saved_workflow"] == "draft.json"
    assert result["draft_saved"] is True
    draft = server.read_workflow(tmp_path / "workflows", "draft.json")
    assert draft["json"]["2"]["inputs"] == {"filename_prefix": "old"}
    assert draft["metadata"]["source"] == "patched"
    assert draft["metadata"]["validation_status"] == "invalid"
    assert draft["metadata"]["submit_ready"] is False


@pytest.mark.asyncio
async def test_comfy_patch_workflow_rejects_ui_before_object_info(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "ui.json", UI_WORKFLOW)

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("ui workflow should be rejected before object_info")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(ValueError, match="requires ComfyUI API prompt JSON"):
        await server.comfy_patch_workflow(
            "ui.json",
            [{"op": "set_input", "node_id": "1", "input": "seed", "value": 1}],
        )


@pytest.mark.asyncio
async def test_comfy_patch_workflow_returns_structured_failure_without_saving(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "source.json", API_WORKFLOW, require_api=True)

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("malformed operations should not call remote object_info")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    result = await server.comfy_patch_workflow(
        "source.json",
        {"op": "set_input"},
        target_name="failed.json",
    )

    assert result["status"] == "failed"
    assert result["report"]["errors"] == [{"message": "operations must be a list"}]
    assert not (tmp_path / "workflows" / "failed.json").exists()


@pytest.mark.asyncio
async def test_comfy_patch_workflow_mcp_call_returns_structured_failure_for_bad_operations(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    save_workflow(tmp_path / "workflows", "source.json", API_WORKFLOW, require_api=True)

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("malformed operations should not call remote object_info")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    _content, structured = await server.mcp.call_tool(
        "comfy_patch_workflow",
        {
            "name": "source.json",
            "operations": {"op": "set_input"},
            "target_name": "failed.json",
        },
    )

    assert structured["status"] == "failed"
    assert structured["report"]["errors"] == [{"message": "operations must be a list"}]
    assert not (tmp_path / "workflows" / "failed.json").exists()


@pytest.mark.asyncio
async def test_comfy_patch_workflow_rejects_path_equivalent_target_before_remote_call(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    workflow = {
        "1": {"class_type": "ImageSource", "inputs": {}},
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "old"},
        },
    }
    save_workflow(tmp_path / "workflows", "source.json", workflow, require_api=True)

    if not (tmp_path / "workflows" / "SOURCE.json").exists():
        pytest.skip("filesystem treats case-variant workflow names as distinct")

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("same-path target should not call remote object_info")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(ValueError, match="target workflow name must differ"):
        await server.comfy_patch_workflow(
            "source.json",
            [
                {
                    "op": "set_input",
                    "node_id": "2",
                    "input": "filename_prefix",
                    "value": "new",
                }
            ],
            target_name="SOURCE.json",
        )

    assert server.read_workflow(tmp_path / "workflows", "source.json")["json"] == workflow


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
async def test_comfy_convert_ui_to_api_rejects_same_name_before_remote_call(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    original_workflow = {
        "nodes": [{"id": 1, "type": "SaveImage", "widgets_values": []}],
        "links": [],
    }
    save_workflow(tmp_path / "workflows", "same.ui.json", original_workflow)

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("remote called before same-name validation")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(
        ValueError,
        match="target workflow name must differ from source workflow name",
    ):
        await server.comfy_convert_ui_to_api("same.ui.json", "same.ui.json")

    loaded = server.read_workflow(tmp_path / "workflows", "same.ui.json")
    assert loaded["kind"] == "ui"
    assert loaded["json"] == original_workflow


@pytest.mark.asyncio
async def test_comfy_convert_ui_to_api_rejects_case_variant_target_before_remote_call(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    original_workflow = {
        "nodes": [{"id": 1, "type": "SaveImage", "widgets_values": []}],
        "links": [],
    }
    save_workflow(tmp_path / "workflows", "same.ui.json", original_workflow)
    if not (tmp_path / "workflows" / "SAME.UI.JSON").exists():
        pytest.skip("filesystem treats case-variant workflow names as distinct")

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("remote called before same-path validation")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(
        ValueError,
        match="target workflow name must differ from source workflow name",
    ):
        await server.comfy_convert_ui_to_api("same.ui.json", "SAME.UI.JSON")

    loaded = server.read_workflow(tmp_path / "workflows", "same.ui.json")
    assert loaded["kind"] == "ui"
    assert loaded["json"] == original_workflow


def test_same_workflow_path_only_casefolds_on_windows(monkeypatch, tmp_path: Path):
    lower_path = tmp_path / "same.ui.json"
    upper_path = tmp_path / "SAME.UI.json"

    monkeypatch.setattr(server.os, "name", "posix")
    assert server._same_workflow_path(lower_path, upper_path) is False

    monkeypatch.setattr(server.os, "name", "nt")
    assert server._same_workflow_path(lower_path, upper_path) is True


def test_same_workflow_path_uses_samefile_on_case_insensitive_filesystems(
    monkeypatch,
    tmp_path: Path,
):
    lower_path = tmp_path / "same.ui.json"
    upper_path = tmp_path / "SAME.UI.json"

    def samefile(_self, _other):
        return True

    monkeypatch.setattr(server.os, "name", "posix")
    monkeypatch.setattr(Path, "samefile", samefile)

    assert server._same_workflow_path(lower_path, upper_path) is True


@pytest.mark.asyncio
async def test_comfy_convert_ui_to_api_rejects_generated_draft_collision_before_remote_call(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    original_workflow = {
        "nodes": [{"id": 1, "type": "SaveImage", "widgets_values": []}],
        "links": [],
    }
    save_workflow(
        tmp_path / "workflows",
        "partial.api.converted-draft.json",
        original_workflow,
    )

    class RemoteShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("remote called before draft-name validation")

    monkeypatch.setattr(server, "ComfyClient", RemoteShouldNotBeCalled)

    with pytest.raises(
        ValueError,
        match="draft workflow name must differ from source and target workflow names",
    ):
        await server.comfy_convert_ui_to_api(
            "partial.api.converted-draft.json",
            "partial.api.json",
            allow_draft=True,
        )

    loaded = server.read_workflow(
        tmp_path / "workflows",
        "partial.api.converted-draft.json",
    )
    assert loaded["kind"] == "ui"
    assert loaded["json"] == original_workflow


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


@pytest.mark.asyncio
async def test_comfy_read_batch_tool_reads_batch_record(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    batch_id = "2026-06-04T01-02-03_batch"
    batch_dir = tmp_path / "runs" / ".batches" / batch_id
    batch_dir.mkdir(parents=True)
    record = {
        "batch_id": batch_id,
        "label": "batch",
        "workflow_name": "source.json",
        "status": "queued",
        "created_at": "2026-06-04T01:02:03+00:00",
        "updated_at": "2026-06-04T01:02:03+00:00",
        "runs": [
            {
                "index": 0,
                "parameters": {"node_id": "1", "inputs": {"seed": 42}},
                "status": "queued",
                "run_id": None,
            }
        ],
    }
    (batch_dir / "batch.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    direct = await server.comfy_read_batch(batch_id)
    _content, structured = await server.mcp.call_tool(
        "comfy_read_batch",
        {"batch_id": batch_id},
    )

    assert direct == record
    assert structured == record


@pytest.mark.asyncio
async def test_comfy_batch_submit_saves_children_submits_and_records_completed(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    source = {
        "1": {
            "class_type": "SaveImage",
            "inputs": {"seed": 0, "filename_prefix": "old"},
        }
    }
    save_workflow(tmp_path / "workflows", "source.json", source, require_api=True)
    submissions = []

    async def fake_submit_workflow(name, run_label=None, client_id=None):
        submissions.append((name, run_label, client_id))
        return {"run_id": f"run-{len(submissions) - 1}", "workflow_name": name}

    monkeypatch.setattr(server, "comfy_submit_workflow", fake_submit_workflow)

    result = await server.comfy_batch_submit(
        "source.json",
        [
            {"node_id": "1", "inputs": {"seed": 111}},
            {
                "changes": [
                    {
                        "op": "set_input",
                        "node_id": "1",
                        "input": "filename_prefix",
                        "value": "new",
                    }
                ]
            },
        ],
        batch_label="Night Batch",
    )

    assert result["status"] == "completed"
    assert [run["status"] for run in result["runs"]] == ["completed", "completed"]
    assert [run["run_id"] for run in result["runs"]] == ["run-0", "run-1"]
    assert len(submissions) == 2
    batch_id = result["batch_id"]
    for index, (child_name, run_label, client_id) in enumerate(submissions):
        assert child_name == Path(child_name).name
        assert child_name.endswith(".json")
        assert run_label == f"{batch_id}-{index}"
        assert client_id is None

    first_child = server.read_workflow(tmp_path / "workflows", submissions[0][0])
    second_child = server.read_workflow(tmp_path / "workflows", submissions[1][0])
    assert first_child["json"]["1"]["inputs"]["seed"] == 111
    assert second_child["json"]["1"]["inputs"]["filename_prefix"] == "new"
    assert await server.comfy_read_batch(batch_id) == result


@pytest.mark.asyncio
async def test_comfy_batch_submit_continues_after_patch_and_submit_failures(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    source = {"1": {"class_type": "SaveImage", "inputs": {"seed": 0}}}
    save_workflow(tmp_path / "workflows", "source.json", source, require_api=True)
    submissions = []

    async def fake_submit_workflow(name, run_label=None, client_id=None):
        submissions.append((name, run_label, client_id))
        if len(submissions) == 1:
            raise RuntimeError("submit exploded")
        return {"run_id": "run-ok", "workflow_name": name}

    monkeypatch.setattr(server, "comfy_submit_workflow", fake_submit_workflow)

    result = await server.comfy_batch_submit(
        "source.json",
        [
            {"node_id": "missing", "inputs": {"seed": 1}},
            {"node_id": "1", "inputs": {"seed": 2}},
            {"node_id": "1", "inputs": {"seed": 3}},
        ],
        batch_label="Mixed",
    )

    assert result["status"] == "partial"
    assert [run["status"] for run in result["runs"]] == [
        "failed",
        "failed",
        "completed",
    ]
    assert [run["run_id"] for run in result["runs"]] == [None, None, "run-ok"]
    assert len(submissions) == 2
    assert server.read_workflow(tmp_path / "workflows", submissions[1][0])["json"]["1"]["inputs"]["seed"] == 3
