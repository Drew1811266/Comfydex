from __future__ import annotations

from copy import deepcopy
from typing import Any


QUALITY_PRESETS: dict[str, dict[str, int]] = {
    "draft": {"steps": 16},
    "balanced": {"steps": 24},
    "high": {"steps": 32},
}

SPEED_PRESETS: dict[str, dict[str, int]] = {
    "fast": {"steps": 16},
    "balanced": {"steps": 24},
    "quality": {"steps": 30},
}

ASPECT_PRESETS: dict[str, dict[str, int]] = {
    "square": {"width": 1024, "height": 1024},
    "portrait": {"width": 832, "height": 1216},
    "landscape": {"width": 1216, "height": 832},
    "wide": {"width": 1344, "height": 768},
}

STYLE_PRESETS: dict[str, dict[str, str]] = {
    "photographic": {
        "positive": "photographic, natural light, detailed",
        "negative": "cartoon, painting, low detail",
    },
    "cinematic": {
        "positive": "cinematic lighting, rich contrast",
        "negative": "flat lighting, low detail",
    },
    "illustration": {
        "positive": "polished illustration, clean composition",
        "negative": "muddy colors, unfinished",
    },
    "product": {
        "positive": "studio product photo, clean background",
        "negative": "cluttered background, distorted product",
    },
}

GPU_DEFAULTS: dict[str, dict[str, int]] = {
    "low": {"width": 768, "height": 768, "steps": 20},
    "mid": {"width": 1024, "height": 1024, "steps": 24},
    "high": {"width": 1024, "height": 1024, "steps": 28},
    "unknown": {"width": 1024, "height": 1024, "steps": 24},
}

MODEL_CFG_DEFAULTS = {
    "z-image": 4.0,
    "sdxl": 7.0,
    "generic": 7.0,
}


def list_generation_presets() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "quality": deepcopy(QUALITY_PRESETS),
        "speed": deepcopy(SPEED_PRESETS),
        "aspect_ratio": deepcopy(ASPECT_PRESETS),
        "style": deepcopy(STYLE_PRESETS),
    }


def classify_gpu_from_system_stats(system_stats: dict[str, Any] | None) -> str:
    devices = _devices_from_system_stats(system_stats)
    vram_values = [_vram_bytes(device) for device in devices]
    vram_values = [value for value in vram_values if value is not None]
    if not vram_values:
        return "unknown"
    best_vram = max(vram_values)
    if best_vram < 10 * 1024**3:
        return "low"
    if best_vram < 20 * 1024**3:
        return "mid"
    return "high"


def infer_model_family(parameters: dict[str, Any] | None) -> str:
    params = parameters if isinstance(parameters, dict) else {}
    checkpoint_name = str(params.get("checkpoint_name") or "").casefold()
    if "z-image" in checkpoint_name or "z_image" in checkpoint_name or "zimage" in checkpoint_name:
        return "z-image"
    if "sdxl" in checkpoint_name or "xl" in checkpoint_name:
        return "sdxl"
    return "generic"


def resolve_generation_defaults(
    parameters: dict[str, Any] | None,
    *,
    system_stats: dict[str, Any] | None = None,
    gpu_class: str | None = None,
    model_family: str | None = None,
) -> dict[str, Any]:
    resolved_parameters = deepcopy(parameters or {})
    resolved_gpu_class = _known_gpu_class(gpu_class) or classify_gpu_from_system_stats(system_stats)
    resolved_model_family = model_family or infer_model_family(resolved_parameters)
    if resolved_model_family not in MODEL_CFG_DEFAULTS:
        resolved_model_family = "generic"

    quality_preset = _known_key(
        resolved_parameters.get("quality_preset"),
        QUALITY_PRESETS,
    )
    speed_preset = _known_key(
        resolved_parameters.get("speed_preset"),
        SPEED_PRESETS,
    )
    aspect_ratio = _known_key(
        resolved_parameters.get("aspect_ratio"),
        ASPECT_PRESETS,
    )
    style_preset = _known_key(
        resolved_parameters.get("style_preset"),
        STYLE_PRESETS,
    )

    applied: list[str] = []
    base_defaults = GPU_DEFAULTS[resolved_gpu_class]
    size_defaults = ASPECT_PRESETS[aspect_ratio] if aspect_ratio else base_defaults
    _set_if_missing(resolved_parameters, "width", size_defaults["width"], applied)
    _set_if_missing(resolved_parameters, "height", size_defaults["height"], applied)

    step_defaults = (
        SPEED_PRESETS[speed_preset]
        if speed_preset
        else QUALITY_PRESETS[quality_preset]
        if quality_preset
        else base_defaults
    )
    _set_if_missing(resolved_parameters, "steps", step_defaults["steps"], applied)
    _set_if_missing(
        resolved_parameters,
        "cfg",
        MODEL_CFG_DEFAULTS[resolved_model_family],
        applied,
    )

    if style_preset:
        style = STYLE_PRESETS[style_preset]
        if _append_prompt_text(resolved_parameters, "positive_prompt", style["positive"]):
            applied.append("style_preset")
        if _append_prompt_text(resolved_parameters, "negative_prompt", style["negative"]):
            applied.append("negative_style")

    return {
        "parameters": resolved_parameters,
        "resolved_defaults": {
            "gpu_class": resolved_gpu_class,
            "model_family": resolved_model_family,
            "quality_preset": quality_preset,
            "speed_preset": speed_preset,
            "aspect_ratio": aspect_ratio,
            "style_preset": style_preset,
            "applied": applied,
        },
    }


def _devices_from_system_stats(system_stats: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(system_stats, dict):
        return []
    devices = system_stats.get("devices")
    if isinstance(devices, list):
        return [device for device in devices if isinstance(device, dict)]
    system = system_stats.get("system")
    if isinstance(system, dict):
        nested = system.get("devices")
        if isinstance(nested, list):
            return [device for device in nested if isinstance(device, dict)]
    return []


def _vram_bytes(device: dict[str, Any]) -> int | None:
    for key in ("vram_total", "total_vram", "vram_total_bytes"):
        value = device.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


def _known_gpu_class(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().casefold()
    return normalized if normalized in GPU_DEFAULTS else None


def _known_key(
    value: Any,
    options: dict[str, dict[str, Any]],
    *,
    default: str | None = None,
) -> str | None:
    if value is None:
        return default
    normalized = str(value).strip().casefold()
    return normalized if normalized in options else default


def _set_if_missing(
    parameters: dict[str, Any],
    key: str,
    value: Any,
    applied: list[str],
) -> None:
    if key in parameters and parameters[key] not in (None, ""):
        return
    parameters[key] = value
    applied.append(key)


def _append_prompt_text(parameters: dict[str, Any], key: str, addition: str) -> bool:
    current = parameters.get(key)
    if current is None:
        parameters[key] = addition
        return True
    text = " ".join(str(current).split())
    if not text:
        parameters[key] = addition
        return True
    if addition.casefold() in text.casefold():
        parameters[key] = text
        return False
    parameters[key] = f"{text}, {addition}"
    return True
