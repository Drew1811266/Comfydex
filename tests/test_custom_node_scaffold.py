from pathlib import Path

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


@pytest.mark.parametrize("package_name", ["../bad", "nested/name", "", "bad name"])
def test_scaffold_custom_node_package_rejects_unsafe_package_names(
    tmp_path: Path,
    package_name: str,
):
    with pytest.raises(ValueError, match="package name"):
        scaffold_custom_node_package(tmp_path, package_name)
