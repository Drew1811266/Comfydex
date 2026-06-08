import json
import shutil
from pathlib import Path

from scripts.validate_plugin import validate_plugin
from scripts.validate_release_package import validate_release_package


def test_validate_plugin_accepts_current_repository():
    root = Path(__file__).parents[1]
    assert validate_plugin(root) == []


def test_validate_plugin_reports_missing_manifest(tmp_path):
    errors = validate_plugin(tmp_path)
    assert any(".codex-plugin/plugin.json" in error for error in errors)


def test_validate_release_package_accepts_current_repository():
    root = Path(__file__).parents[1]
    assert validate_release_package(root) == []


def test_validate_release_package_reports_version_mismatch(tmp_path):
    root = Path(__file__).parents[1]
    package_root = tmp_path / "package"
    shutil.copytree(
        root,
        package_root,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            ".pytest_cache",
            "target",
            "node_modules",
            "dist",
            "vite.*.log",
        ),
    )
    manifest_path = package_root / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = "9.9.9"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_release_package(package_root)

    assert any("version mismatch" in error for error in errors)


def test_validate_release_package_requires_install_script(tmp_path):
    root = Path(__file__).parents[1]
    package_root = tmp_path / "package"
    shutil.copytree(
        root,
        package_root,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            ".pytest_cache",
            "target",
            "node_modules",
            "dist",
            "vite.*.log",
        ),
    )
    install_script = package_root / "scripts" / "install_windows.ps1"
    if install_script.exists():
        install_script.unlink()

    errors = validate_release_package(package_root)

    assert any("scripts/install_windows.ps1" in error for error in errors)
