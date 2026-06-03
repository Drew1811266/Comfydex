from __future__ import annotations

import re
from pathlib import Path, PurePosixPath


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_json_path(base_dir: Path, filename: str) -> Path:
    if not filename or filename != Path(filename).name or not filename.endswith(".json"):
        raise ValueError("workflow filename must be a simple .json filename")
    base = base_dir.resolve()
    target = (base / filename).resolve()
    if not _is_relative_to(target, base):
        raise ValueError("workflow path must stay inside workflows_dir")
    return target


def safe_package_dir(base_dir: Path, package_name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", package_name or ""):
        raise ValueError(
            "package name must contain only letters, numbers, underscores, and hyphens"
        )
    base = base_dir.resolve()
    target = (base / package_name).resolve()
    if not _is_relative_to(target, base):
        raise ValueError("package path must stay inside base directory")
    return target


def safe_auxiliary_json_path(base_dir: Path, directory_name: str, filename: str) -> Path:
    if not directory_name or directory_name != Path(directory_name).name:
        raise ValueError("auxiliary directory name must be simple")
    if not filename or filename != Path(filename).name or not filename.endswith(".json"):
        raise ValueError("workflow filename must be a simple .json filename")
    base = base_dir.resolve()
    target = (base_dir / directory_name / filename).resolve()
    if not _is_relative_to(target, base):
        raise ValueError("workflow path must stay inside workflows_dir")
    return target


def safe_output_path(base_dir: Path, relative_name: str) -> Path:
    if not relative_name:
        raise ValueError("output filename must be non-empty")
    candidate = PurePosixPath(relative_name.replace("\\", "/"))
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("output path must stay inside the run output directory")
    base = base_dir.resolve()
    target = (base / candidate.as_posix()).resolve()
    if not _is_relative_to(target, base):
        raise ValueError("output path must stay inside the run output directory")
    return target
