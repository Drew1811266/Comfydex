from __future__ import annotations

from pathlib import Path
from typing import Any


MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}


def infer_model_type(path: Path) -> str:
    parts = {part.casefold() for part in path.parts}
    filename = path.name.casefold()

    if {"checkpoints", "checkpoint", "ckpt"} & parts:
        return "checkpoint"
    if {"loras", "lora"} & parts:
        return "lora"
    if {"controlnet", "controlnets", "control_net"} & parts:
        return "controlnet"
    if {"upscale_models", "upscalers", "upscale"} & parts:
        return "upscale"
    if {"vae", "vaes"} & parts:
        return "vae"
    if (
        "ipadapter" in filename
        or "ip-adapter" in filename
        or "ip_adapter" in filename
        or "adapter_ip" in filename
    ):
        return "ipadapter"
    return "unknown"


def scan_model_inventory(model_roots: list[Path]) -> dict[str, Any]:
    roots: list[str] = []
    missing_roots: list[str] = []
    models: list[dict[str, Any]] = []

    for root in model_roots:
        resolved = root.expanduser().resolve()
        if not resolved.is_dir():
            missing_roots.append(str(resolved))
            continue
        roots.append(str(resolved))
        for candidate in sorted(resolved.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.suffix.casefold() not in MODEL_EXTENSIONS:
                continue
            models.append(
                {
                    "filename": candidate.name,
                    "path": str(candidate.resolve()),
                    "model_type": infer_model_type(candidate),
                    "size_bytes": candidate.stat().st_size,
                }
            )

    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in sorted(models, key=lambda model: (model["model_type"], model["filename"])):
        by_type.setdefault(item["model_type"], []).append(item)

    return {
        "roots": roots,
        "missing_roots": missing_roots,
        "model_count": len(models),
        "models": sorted(models, key=lambda model: (model["model_type"], model["filename"])),
        "by_type": by_type,
    }
