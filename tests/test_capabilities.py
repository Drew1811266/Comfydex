from pathlib import Path

from comfydex_mcp.capabilities import (
    infer_model_type,
    node_inventory_from_object_info,
    resolve_capabilities,
    scan_model_inventory,
)


TEXT_TO_IMAGE_OBJECT_INFO = {
    "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ("STRING",)}}},
    "CLIPTextEncode": {"input": {"required": {"text": ("STRING",), "clip": ("CLIP",)}}},
    "EmptyLatentImage": {"input": {"required": {}}},
    "KSampler": {"input": {"required": {}}},
    "VAEDecode": {"input": {"required": {}}},
    "SaveImage": {"input": {"required": {}}},
}


def test_infer_model_type_from_parent_folder_and_filename():
    assert infer_model_type(Path("models/checkpoints/sdxl.safetensors")) == "checkpoint"
    assert infer_model_type(Path("models/loras/style.safetensors")) == "lora"
    assert infer_model_type(Path("models/controlnet/pose.safetensors")) == "controlnet"
    assert infer_model_type(Path("models/upscale_models/4x.pth")) == "upscale"
    assert infer_model_type(Path("models/vae/vae.safetensors")) == "vae"
    assert infer_model_type(Path("models/misc/adapter_ip.bin")) == "ipadapter"
    assert infer_model_type(Path("models/misc/unknown-model.safetensors")) == "unknown"


def test_scan_model_inventory_finds_supported_model_files(tmp_path):
    (tmp_path / "models" / "checkpoints").mkdir(parents=True)
    (tmp_path / "models" / "loras").mkdir(parents=True)
    (tmp_path / "models" / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "models" / "checkpoints" / "sdxl.safetensors").write_text(
        "x",
        encoding="utf-8",
    )
    (tmp_path / "models" / "loras" / "style.safetensors").write_text(
        "x",
        encoding="utf-8",
    )

    result = scan_model_inventory([tmp_path / "models"])

    assert result["model_count"] == 2
    assert result["by_type"]["checkpoint"][0]["filename"] == "sdxl.safetensors"
    assert result["by_type"]["lora"][0]["filename"] == "style.safetensors"
    assert result["roots"] == [str((tmp_path / "models").resolve())]


def test_scan_model_inventory_skips_missing_roots(tmp_path):
    result = scan_model_inventory([tmp_path / "missing"])

    assert result["model_count"] == 0
    assert result["by_type"] == {}
    assert result["missing_roots"] == [str((tmp_path / "missing").resolve())]


def test_node_inventory_from_object_info_includes_semantic_match():
    result = node_inventory_from_object_info(
        {
            "KSampler": {"input": {"required": {}}},
            "UnknownCustomNode": {"input": {"required": {}}},
        }
    )

    assert result["node_count"] == 2
    assert result["node_types"] == ["KSampler", "UnknownCustomNode"]
    assert result["semantic_match"]["supported_node_types"] == ["KSampler"]
    assert result["semantic_match"]["unknown_node_types"] == ["UnknownCustomNode"]


def test_resolve_capabilities_returns_ready_when_nodes_and_models_exist():
    model_inventory = {
        "models": [{"filename": "sdxl.safetensors", "model_type": "checkpoint"}],
        "by_type": {"checkpoint": [{"filename": "sdxl.safetensors"}]},
    }

    report = resolve_capabilities(
        "text to image",
        {"checkpoint_name": "sdxl.safetensors", "positive_prompt": "a lake"},
        TEXT_TO_IMAGE_OBJECT_INFO,
        model_inventory,
    )

    assert report["status"] == "ready"
    assert report["can_run_now"] is True
    assert report["missing_nodes"] == []
    assert report["missing_models"] == []
    assert report["plan"]["semantic_coverage"]["status"] == "supported"


def test_resolve_capabilities_reports_missing_models_and_nodes():
    object_info = dict(TEXT_TO_IMAGE_OBJECT_INFO)
    object_info.pop("KSampler")
    model_inventory = {"models": [], "by_type": {}}

    report = resolve_capabilities(
        "text to image",
        {"checkpoint_name": "missing.safetensors", "positive_prompt": "a lake"},
        object_info,
        model_inventory,
    )

    assert report["status"] == "missing_requirements"
    assert report["can_run_now"] is False
    assert report["missing_nodes"] == [
        {"node_type": "KSampler", "reason": "missing_object_info"}
    ]
    assert report["missing_models"] == [
        {
            "parameter": "checkpoint_name",
            "filename": "missing.safetensors",
            "model_type": "checkpoint",
            "reason": "missing_model",
        }
    ]
