from pathlib import Path

from comfydex_mcp.capabilities import infer_model_type, scan_model_inventory


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
