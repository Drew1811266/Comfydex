from pathlib import Path

from comfydex_mcp.custom_nodes import (
    check_node_imports,
    inspect_custom_node_package,
    validate_node_class,
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


def test_inspect_custom_node_package_does_not_execute_nodes_py(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    sentinel = package / "imported.txt"
    (package / "nodes.py").write_text(
        "from pathlib import Path\n"
        "class GoodNode: pass\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n"
        f"Path({str(sentinel)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = inspect_custom_node_package(package)

    assert result["class_mappings"] == {"GoodNode": "GoodNode"}
    assert not sentinel.exists()


def test_inspect_custom_node_package_reports_missing_nodes_py(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()

    result = inspect_custom_node_package(package)

    assert result["status"] == "invalid"
    assert result["node_classes"] == []
    assert result["class_mappings"] == {}
    assert result["display_name_mappings"] == {}
    assert result["errors"] == [
        {"reason": "missing_nodes_py", "path": str(package / "nodes.py")}
    ]


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


def test_validate_node_mappings_reports_unsupported_class_mapping_value(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n"
        "def build_node():\n"
        "    return GoodNode\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': build_node()}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"] == [
        {
            "mapping_key": "GoodNode",
            "reason": "unsupported_mapping_value",
        }
    ]


def test_validate_node_mappings_reports_missing_nodes_py(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"] == [
        {"reason": "missing_nodes_py", "path": str(package / "nodes.py")}
    ]


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


def test_validate_node_class_reports_missing_input_types(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(error["reason"] == "missing_input_types" for error in result["errors"])


def test_validate_node_class_reports_missing_callable_function(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'missing_run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(
        error["reason"] == "missing_callable_function"
        for error in result["errors"]
    )


def test_validate_node_class_reports_non_string_function(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 123\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(error["reason"] == "invalid_function" for error in result["errors"])


def test_validate_node_class_reports_instance_input_types_method(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    def INPUT_TYPES(self):\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(error["reason"] == "invalid_input_types" for error in result["errors"])


def test_validate_node_class_reports_property_input_types(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @property\n"
        "    def INPUT_TYPES(self):\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(error["reason"] == "invalid_input_types" for error in result["errors"])


def test_check_node_imports_returns_import_error(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS\n",
        encoding="utf-8",
    )
    (package / "nodes.py").write_text(
        "import does_not_exist_here\n",
        encoding="utf-8",
    )

    result = check_node_imports(package)

    assert result["status"] == "failed"
    assert "does_not_exist_here" in result["stderr"]


def test_check_node_imports_returns_timeout_failure(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS\n",
        encoding="utf-8",
    )
    (package / "nodes.py").write_text(
        "while True:\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = check_node_imports(package, timeout_seconds=1)

    assert result["status"] == "failed"
    assert result["reason"] == "timeout"


def test_check_node_imports_returns_missing_package_failure(tmp_path: Path):
    result = check_node_imports(tmp_path / "missing")

    assert result["status"] == "failed"
    assert result["reason"] == "missing_package_dir"
