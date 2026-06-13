import json
import tomllib
from pathlib import Path

import comfydex_mcp


ROOT = Path(__file__).parents[1]


EXPECTED_VERSION = "1.9.0"


def test_versions_match_expected_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    desktop_package = json.loads(
        (ROOT / "desktop" / "package.json").read_text(encoding="utf-8")
    )
    desktop_lock = json.loads(
        (ROOT / "desktop" / "package-lock.json").read_text(encoding="utf-8")
    )
    cargo = tomllib.loads(
        (ROOT / "desktop" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    )
    tauri_config = json.loads(
        (ROOT / "desktop" / "src-tauri" / "tauri.conf.json").read_text(
            encoding="utf-8"
        )
    )
    cargo_lock = tomllib.loads(
        (ROOT / "desktop" / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8")
    )
    cargo_package = next(
        package
        for package in cargo_lock["package"]
        if package["name"] == "comfydex-desktop"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert manifest["version"] == EXPECTED_VERSION
    assert comfydex_mcp.__version__ == EXPECTED_VERSION
    assert desktop_package["version"] == EXPECTED_VERSION
    assert desktop_lock["version"] == EXPECTED_VERSION
    assert desktop_lock["packages"][""]["version"] == EXPECTED_VERSION
    assert cargo["package"]["version"] == EXPECTED_VERSION
    assert tauri_config["version"] == EXPECTED_VERSION
    assert cargo_package["version"] == EXPECTED_VERSION
    assert f"Current version: `{EXPECTED_VERSION}`" in readme
