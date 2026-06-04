from pathlib import Path

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
