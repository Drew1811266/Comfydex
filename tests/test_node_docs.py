from pathlib import Path

import pytest

from comfydex_mcp.node_docs import generate_node_docs


def test_generate_node_docs_is_deterministic(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'value': ('INT',)}}\n"
        "    def run(self, value):\n"
        "        return (value,)\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )

    result = generate_node_docs(package)

    assert result["path"] == str(package / "NODE_DOCS.md")
    assert "# Custom Node Documentation" in result["markdown"]
    assert "GoodNode" in result["markdown"]
    assert "- Mapping key: `GoodNode`" in result["markdown"]
    assert "- Validation status: `valid`" in result["markdown"]
    assert "- Category: `Comfydex`" in result["markdown"]
    assert "### Inputs" in result["markdown"]
    assert "#### Required" in result["markdown"]
    assert "- `value`: `INT`" in result["markdown"]
    assert "### Outputs" in result["markdown"]
    assert "- `INT`" in result["markdown"]
    assert "### Examples" in result["markdown"]
    assert "node = GoodNode()" in result["markdown"]
    assert "result = node.run(value=None)" in result["markdown"]
    assert (package / "NODE_DOCS.md").read_text(encoding="utf-8") == result["markdown"]


def test_generate_node_docs_sorts_mapping_keys(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "class ANode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BNode': BNode, 'ANode': ANode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BNode': 'B Node', 'ANode': 'A Node'}\n",
        encoding="utf-8",
    )

    result = generate_node_docs(package)

    assert result["markdown"].index("## A Node") < result["markdown"].index("## B Node")


def test_generate_node_docs_surfaces_mapping_validation_errors(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n"
        "def build_node():\n"
        "    return GoodNode\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': build_node()}\n",
        encoding="utf-8",
    )

    result = generate_node_docs(package)

    assert result["mapping_validation"]["status"] == "invalid"
    assert result["mapping_validation"]["errors"] == [
        {"mapping_key": "GoodNode", "reason": "unsupported_mapping_value"}
    ]
    assert "## Mapping Validation" in result["markdown"]
    assert "- `GoodNode`: unsupported_mapping_value" in result["markdown"]


def test_generate_node_docs_rejects_redirected_docs_path_before_writing(
    monkeypatch,
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    docs_path = package / "NODE_DOCS.md"
    (package / "nodes.py").write_text(
        "class GoodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )
    docs_path.write_text("outside target contents\n", encoding="utf-8")

    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path: Path):
        if path == docs_path:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(ValueError, match="NODE_DOCS.md"):
        generate_node_docs(package)

    assert docs_path.read_text(encoding="utf-8") == "outside target contents\n"


def test_generate_node_docs_surfaces_parse_invalid_package_without_crashing(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode(:\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = generate_node_docs(package)

    assert result["inspection"]["status"] == "invalid"
    assert result["mapping_validation"]["status"] == "invalid"
    assert result["mapping_validation"]["errors"][0]["reason"] == (
        "invalid_nodes_py_syntax"
    )
    assert "- `package`: invalid_nodes_py_syntax" in result["markdown"]
