from __future__ import annotations

from comfydex_mcp.presets import (
    classify_gpu_from_system_stats,
    infer_model_family,
    list_generation_presets,
    resolve_generation_defaults,
)


def test_list_generation_presets_contains_expected_groups():
    result = list_generation_presets()

    assert set(result) == {"quality", "speed", "aspect_ratio", "style"}
    assert "balanced" in result["quality"]
    assert "fast" in result["speed"]
    assert "landscape" in result["aspect_ratio"]
    assert result["style"]["photographic"]["positive"]


def test_classify_gpu_from_system_stats_uses_vram_bytes():
    assert classify_gpu_from_system_stats({"devices": [{"vram_total": 6 * 1024**3}]}) == "low"
    assert classify_gpu_from_system_stats({"devices": [{"vram_total": 12 * 1024**3}]}) == "mid"
    assert classify_gpu_from_system_stats({"devices": [{"vram_total": 24 * 1024**3}]}) == "high"
    assert classify_gpu_from_system_stats({}) == "unknown"


def test_infer_model_family_prefers_z_image_and_sdxl_names():
    assert infer_model_family({"checkpoint_name": "z-image-turbo.safetensors"}) == "z-image"
    assert infer_model_family({"checkpoint_name": "sdxl_base.safetensors"}) == "sdxl"
    assert infer_model_family({"checkpoint_name": "dreamshaper.safetensors"}) == "generic"


def test_resolve_generation_defaults_applies_quality_aspect_and_style():
    result = resolve_generation_defaults(
        {
            "checkpoint_name": "z-image.safetensors",
            "positive_prompt": "a product photo",
            "quality_preset": "high",
            "aspect_ratio": "landscape",
            "style_preset": "photographic",
        },
        gpu_class="mid",
        model_family="z-image",
    )

    assert result["parameters"]["width"] == 1216
    assert result["parameters"]["height"] == 832
    assert result["parameters"]["steps"] == 32
    assert result["parameters"]["cfg"] == 4.0
    assert "photographic" in result["parameters"]["positive_prompt"]
    assert "cartoon" in result["parameters"]["negative_prompt"]
    assert result["resolved_defaults"]["gpu_class"] == "mid"
    assert result["resolved_defaults"]["model_family"] == "z-image"
    assert result["resolved_defaults"]["quality_preset"] == "high"
    assert "style_preset" in result["resolved_defaults"]["applied"]


def test_resolve_generation_defaults_preserves_explicit_values():
    result = resolve_generation_defaults(
        {
            "positive_prompt": "a lake",
            "width": 512,
            "height": 640,
            "steps": 12,
            "cfg": 5.5,
        },
        gpu_class="high",
        model_family="sdxl",
    )

    assert result["parameters"]["width"] == 512
    assert result["parameters"]["height"] == 640
    assert result["parameters"]["steps"] == 12
    assert result["parameters"]["cfg"] == 5.5
    assert "width" not in result["resolved_defaults"]["applied"]
    assert "height" not in result["resolved_defaults"]["applied"]
    assert "steps" not in result["resolved_defaults"]["applied"]


def test_resolve_generation_defaults_uses_low_gpu_safe_canvas_without_aspect():
    result = resolve_generation_defaults(
        {"positive_prompt": "a lake"},
        gpu_class="low",
        model_family="generic",
    )

    assert result["parameters"]["width"] == 768
    assert result["parameters"]["height"] == 768
    assert result["parameters"]["steps"] == 20
