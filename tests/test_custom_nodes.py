from pathlib import Path

from comfydex_mcp.custom_nodes import (
    inspect_custom_node_package,
    validate_node_mappings,
)


def _write_package(path: Path) -> None:
    path.mkdir()
    (path / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS\n",
        encoding="utf-8",
    )
    (path / "nodes.py").write_text(
        "class GoodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'value': ('INT',)}}\n"
        "    def run(self, value):\n"
        "        return (value,)\n\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )


def test_inspect_custom_node_package_reports_classes_and_mappings(tmp_path: Path):
    package = tmp_path / "pkg"
    _write_package(package)

    result = inspect_custom_node_package(package)

    assert "GoodNode" in result["node_classes"]
    assert result["class_mappings"] == {"GoodNode": "GoodNode"}
    assert result["display_name_mappings"] == {"GoodNode": "Good Node"}


def test_validate_node_mappings_reports_missing_class(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "NODE_CLASS_MAPPINGS = {'Missing': MissingClass}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "missing_class"


def test_validate_node_mappings_reports_duplicate_mapping_keys(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class A: pass\n"
        "class B: pass\n"
        "NODE_CLASS_MAPPINGS = {'Node': A, 'Node': B}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'Node': 'Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "duplicate_mapping_key"


def test_validate_node_mappings_reports_missing_display_name(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert any(error["reason"] == "missing_display_name" for error in result["errors"])
