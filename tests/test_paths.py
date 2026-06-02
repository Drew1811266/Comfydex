from pathlib import Path

import pytest

from comfydex_mcp.paths import ensure_directory, safe_json_path, safe_output_path


def test_safe_json_path_accepts_simple_filename(tmp_path: Path):
    target = safe_json_path(tmp_path, "text2img.json")
    assert target == tmp_path / "text2img.json"


@pytest.mark.parametrize("name", ["../secret.json", "nested/file.json", "bad.txt", ""])
def test_safe_json_path_rejects_unsafe_names(tmp_path: Path, name: str):
    with pytest.raises(ValueError):
        safe_json_path(tmp_path, name)


def test_safe_output_path_allows_nested_history_subfolder(tmp_path: Path):
    target = safe_output_path(tmp_path, "images/example.png")
    assert target == tmp_path / "images" / "example.png"


@pytest.mark.parametrize("relative_name", ["../escape.png", "/tmp/x.png", "a/../../x.png"])
def test_safe_output_path_rejects_traversal(tmp_path: Path, relative_name: str):
    with pytest.raises(ValueError):
        safe_output_path(tmp_path, relative_name)


def test_ensure_directory_creates_directory(tmp_path: Path):
    target = tmp_path / "workflows"
    ensure_directory(target)
    assert target.is_dir()
