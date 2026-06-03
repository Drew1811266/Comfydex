from pathlib import Path

from scripts.validate_plugin import validate_plugin


def test_validate_plugin_accepts_current_repository():
    root = Path(__file__).parents[1]
    assert validate_plugin(root) == []


def test_validate_plugin_reports_missing_manifest(tmp_path):
    errors = validate_plugin(tmp_path)
    assert any(".codex-plugin/plugin.json" in error for error in errors)
