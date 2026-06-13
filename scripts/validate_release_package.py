from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_plugin import validate_plugin


JSON_OBJECT_FILES = (
    Path(".codex-plugin/plugin.json"),
    Path(".mcp.json"),
    Path("desktop/package.json"),
    Path("desktop/package-lock.json"),
    Path("desktop/src-tauri/tauri.conf.json"),
)

REQUIRED_FILES = (
    Path("README.md"),
    Path("pyproject.toml"),
    Path("src/comfydex_mcp/__init__.py"),
    Path("src/comfydex_mcp/readiness.py"),
    Path("src/comfydex_mcp/server.py"),
    Path("scripts/validate_plugin.py"),
    Path("scripts/validate_release_package.py"),
    Path("scripts/install_windows.ps1"),
    Path(".codex-plugin/plugin.json"),
    Path(".mcp.json"),
    Path("docs/release/windows-install.md"),
    Path("docs/release/1.0-release-checklist.md"),
    Path("docs/release/1.9-release-checklist.md"),
    Path("docs/release/2.0-release-checklist.md"),
    Path("docs/release/security-path-review.md"),
    Path("docs/usage/2.0-readiness-gate.md"),
    Path("docs/usage/conversational-workflow-system.md"),
    Path("desktop/package.json"),
    Path("desktop/package-lock.json"),
    Path("desktop/src/App.tsx"),
    Path("desktop/src/lib/api.ts"),
    Path("desktop/src/views/AssetsView.tsx"),
    Path("desktop/src/views/BatchesView.tsx"),
    Path("desktop/src-tauri/Cargo.toml"),
    Path("desktop/src-tauri/Cargo.lock"),
    Path("desktop/src-tauri/src/main.rs"),
    Path("desktop/src-tauri/tauri.conf.json"),
)


def _load_json_object(root: Path, relative_path: Path, errors: list[str]) -> dict[str, Any] | None:
    path = root / relative_path
    if not path.is_file():
        errors.append(f"Missing required JSON file: {relative_path.as_posix()}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {relative_path.as_posix()}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{relative_path.as_posix()} must contain a JSON object")
        return None
    return data


def _load_toml_object(root: Path, relative_path: Path, errors: list[str]) -> dict[str, Any] | None:
    path = root / relative_path
    if not path.is_file():
        errors.append(f"Missing required TOML file: {relative_path.as_posix()}")
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"Invalid TOML in {relative_path.as_posix()}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def _init_version(root: Path, errors: list[str]) -> str | None:
    path = root / "src/comfydex_mcp/__init__.py"
    if not path.is_file():
        errors.append("Missing required file: src/comfydex_mcp/__init__.py")
        return None
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if not match:
        errors.append("src/comfydex_mcp/__init__.py is missing __version__")
        return None
    return match.group(1)


def _cargo_lock_version(root: Path, errors: list[str]) -> str | None:
    data = _load_toml_object(root, Path("desktop/src-tauri/Cargo.lock"), errors)
    packages = data.get("package", []) if isinstance(data, dict) else []
    if not isinstance(packages, list):
        errors.append("desktop/src-tauri/Cargo.lock package section must be a list")
        return None
    for package in packages:
        if isinstance(package, dict) and package.get("name") == "comfydex-desktop":
            version = package.get("version")
            if isinstance(version, str):
                return version
    errors.append("desktop/src-tauri/Cargo.lock is missing comfydex-desktop package")
    return None


def _version_tuple(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return (0, 0, 0)
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def _require_markers(
    root: Path,
    relative_path: Path,
    markers: tuple[str, ...],
    errors: list[str],
) -> None:
    path = root / relative_path
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            errors.append(f"{relative_path.as_posix()} must mention {marker}")


def validate_release_package(root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve()

    errors.extend(validate_plugin(root))

    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).is_file():
            errors.append(f"Missing required file: {relative_path.as_posix()}")

    json_objects = {
        relative_path: _load_json_object(root, relative_path, errors)
        for relative_path in JSON_OBJECT_FILES
    }
    pyproject = _load_toml_object(root, Path("pyproject.toml"), errors)
    cargo = _load_toml_object(root, Path("desktop/src-tauri/Cargo.toml"), errors)

    versions: dict[str, str] = {}
    if pyproject is not None:
        version = pyproject.get("project", {}).get("version")
        if isinstance(version, str):
            versions["pyproject.toml"] = version
        else:
            errors.append("pyproject.toml is missing project.version")
    init_version = _init_version(root, errors)
    if init_version is not None:
        versions["src/comfydex_mcp/__init__.py"] = init_version

    manifest = json_objects.get(Path(".codex-plugin/plugin.json"))
    if manifest is not None and isinstance(manifest.get("version"), str):
        versions[".codex-plugin/plugin.json"] = manifest["version"]

    package_json = json_objects.get(Path("desktop/package.json"))
    if package_json is not None and isinstance(package_json.get("version"), str):
        versions["desktop/package.json"] = package_json["version"]

    package_lock = json_objects.get(Path("desktop/package-lock.json"))
    if package_lock is not None:
        if isinstance(package_lock.get("version"), str):
            versions["desktop/package-lock.json"] = package_lock["version"]
        root_package = package_lock.get("packages", {}).get("")
        if isinstance(root_package, dict) and isinstance(root_package.get("version"), str):
            versions['desktop/package-lock.json packages[""]'] = root_package["version"]

    tauri_conf = json_objects.get(Path("desktop/src-tauri/tauri.conf.json"))
    if tauri_conf is not None and isinstance(tauri_conf.get("version"), str):
        versions["desktop/src-tauri/tauri.conf.json"] = tauri_conf["version"]

    if cargo is not None:
        version = cargo.get("package", {}).get("version")
        if isinstance(version, str):
            versions["desktop/src-tauri/Cargo.toml"] = version
        else:
            errors.append("desktop/src-tauri/Cargo.toml is missing package.version")

    cargo_lock_version = _cargo_lock_version(root, errors)
    if cargo_lock_version is not None:
        versions["desktop/src-tauri/Cargo.lock"] = cargo_lock_version

    unique_versions = sorted(set(versions.values()))
    if len(unique_versions) > 1:
        detail = ", ".join(f"{name}={version}" for name, version in sorted(versions.items()))
        errors.append(f"version mismatch: {detail}")

    current_version = versions.get("pyproject.toml")
    readme_path = root / "README.md"
    if readme_path.is_file() and current_version is not None:
        readme = readme_path.read_text(encoding="utf-8")
        if current_version not in readme:
            errors.append(f"README.md must mention current version {current_version}")
        if _version_tuple(current_version) >= (0, 9, 0):
            if "comfy_generate_run_fetch" not in readme:
                errors.append("README.md must mention comfy_generate_run_fetch for 0.9+")
            if "validate_release_package.py" not in readme:
                errors.append("README.md must mention validate_release_package.py for 0.9+")
        if _version_tuple(current_version) >= (1, 0, 0):
            if "Usable Developer Release" not in readme:
                errors.append("README.md must mention Usable Developer Release for 1.0+")
            if "scripts/install_windows.ps1" not in readme:
                errors.append("README.md must mention scripts/install_windows.ps1 for 1.0+")

    if current_version is not None and _version_tuple(current_version) >= (0, 9, 0):
        automation_doc = root / "docs/usage/end-to-end-automation.md"
        if not automation_doc.is_file():
            errors.append("Missing required file: docs/usage/end-to-end-automation.md")
        else:
            text = automation_doc.read_text(encoding="utf-8")
            for marker in (
                "comfy_generate_run_fetch",
                "confirm_risky_actions",
                "wait_for_completion",
                "fetch_outputs",
                "object_info_unavailable",
                "reindex",
            ):
                if marker not in text:
                    errors.append(
                        f"docs/usage/end-to-end-automation.md must mention {marker}"
                    )

    _require_markers(
        root,
        Path("docs/release/windows-install.md"),
        (
            "python -m pip install -e",
            "npm --prefix desktop install",
            "comfy_check_connection",
            "validate_release_package.py",
        ),
        errors,
    )
    _require_markers(
        root,
        Path("docs/release/1.0-release-checklist.md"),
        (
            "python -m pytest tests -q",
            "python scripts\\validate_release_package.py",
            "git ls-remote origin refs/heads/main refs/tags/v1.0.0",
        ),
        errors,
    )
    _require_markers(
        root,
        Path("docs/release/security-path-review.md"),
        (
            "path traversal",
            "header redaction",
            "cleanup confirmation",
            "desktop bridge",
        ),
        errors,
    )
    _require_markers(
        root,
        Path("docs/usage/2.0-readiness-gate.md"),
        (
            "2.0.0",
            "2.0 Readiness Gate",
            "comfy_list_20_scenarios",
            "comfy_20_readiness_report",
            "ready_for_2_0",
            "Desktop",
        ),
        errors,
    )
    _require_markers(
        root,
        Path("docs/usage/conversational-workflow-system.md"),
        (
            "2.0.0",
            "ready_for_2_0",
            "portrait",
            "character consistency",
            "product image",
            "inpainting",
            "background replacement",
            "no automatic downloads",
        ),
        errors,
    )
    _require_markers(
        root,
        Path("docs/release/2.0-release-checklist.md"),
        (
            "2.0.0",
            "ready_for_2_0",
            "tests/test_readiness.py",
            "npm run typecheck",
            "npm run build",
            "cargo check",
            "v2.0.0",
            "git push origin main v2.0.0",
        ),
        errors,
    )
    _require_markers(
        root,
        Path("docs/release/1.9-release-checklist.md"),
        (
            "1.9.0",
            "2.0 Readiness Gate",
            "tests/test_readiness.py",
            "npm run typecheck",
            "npm run build",
            "cargo check",
            "v1.9.0",
        ),
        errors,
    )
    _require_markers(
        root,
        Path("scripts/install_windows.ps1"),
        (
            "python -m pip install -e",
            "npm --prefix desktop install",
            "comfy_check_connection",
            "validate_release_package.py",
        ),
        errors,
    )

    return errors


def main() -> int:
    errors = validate_release_package(Path.cwd())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Comfydex release package validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
