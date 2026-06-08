from pathlib import Path
from types import SimpleNamespace

import pytest

from comfydex_mcp.node_scaffold import scaffold_custom_node_package


def test_scaffold_custom_node_package_creates_workspace_local_package(
    tmp_path: Path,
):
    result = scaffold_custom_node_package(tmp_path, "simple_math")
    package_dir = tmp_path / "custom_nodes" / "simple_math"

    assert result["package_dir"] == str(package_dir)
    assert result["mapping_key"] == "SimpleMathNode"
    assert result["class_name"] == "SimpleMathNode"
    assert (package_dir / "__init__.py").exists()
    assert (package_dir / "nodes.py").exists()
    assert (package_dir / "README.md").exists()
    assert (package_dir / "pyproject.toml").exists()
    assert (package_dir / "tests" / "test_nodes.py").exists()


def test_scaffold_custom_node_package_accepts_hyphenated_names(tmp_path: Path):
    result = scaffold_custom_node_package(tmp_path, "simple-math")

    assert result["class_name"] == "SimpleMathNode"
    assert (tmp_path / "custom_nodes" / "simple-math" / "nodes.py").exists()


def test_scaffold_custom_node_package_prefixes_numeric_class_names(tmp_path: Path):
    result = scaffold_custom_node_package(tmp_path, "123_math")

    assert result["class_name"] == "Custom123MathNode"
    nodes_py = tmp_path / "custom_nodes" / "123_math" / "nodes.py"
    assert "class Custom123MathNode:" in nodes_py.read_text(encoding="utf-8")


def test_scaffold_custom_node_package_rejects_existing_package(tmp_path: Path):
    scaffold_custom_node_package(tmp_path, "simple_math")
    nodes_py = tmp_path / "custom_nodes" / "simple_math" / "nodes.py"
    nodes_py.write_text("# user code\n", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        scaffold_custom_node_package(tmp_path, "simple_math")

    assert nodes_py.read_text(encoding="utf-8") == "# user code\n"


def test_scaffold_custom_node_package_rejects_symlinked_custom_nodes_dir(
    monkeypatch,
    tmp_path: Path,
):
    custom_nodes = tmp_path / "custom_nodes"
    custom_nodes.mkdir()

    def fake_is_symlink(path: Path):
        return path == custom_nodes

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(ValueError, match="custom_nodes directory must be workspace-local"):
        scaffold_custom_node_package(tmp_path, "simple_math")

    assert not (custom_nodes / "simple_math").exists()


def test_scaffold_custom_node_package_rejects_reparse_custom_nodes_dir(
    monkeypatch,
    tmp_path: Path,
):
    custom_nodes = tmp_path / "custom_nodes"
    custom_nodes.mkdir()

    original_stat = Path.stat

    def fake_stat(path: Path, *args, **kwargs):
        if path == custom_nodes:
            original = original_stat(path, *args, **kwargs)
            return SimpleNamespace(
                st_file_attributes=0x400,
                st_mode=original.st_mode,
            )
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    with pytest.raises(ValueError, match="custom_nodes directory must be workspace-local"):
        scaffold_custom_node_package(tmp_path, "simple_math")

    assert not (custom_nodes / "simple_math").exists()


@pytest.mark.parametrize(
    "package_name",
    [
        "../bad",
        "nested/name",
        "nested\\name",
        "/tmp/bad",
        "C:\\bad",
        "",
        "bad name",
        "_leading",
        "trailing_",
        "-leading",
        "trailing-",
        "-",
        "___",
    ],
)
def test_scaffold_custom_node_package_rejects_unsafe_package_names(
    tmp_path: Path,
    package_name: str,
):
    with pytest.raises(ValueError, match="package name"):
        scaffold_custom_node_package(tmp_path, package_name)
