from pathlib import Path

from comfydex_mcp.node_contracts import generate_node_examples


def _write_package(path: Path, nodes_source: str) -> None:
    path.mkdir()
    (path / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS\n",
        encoding="utf-8",
    )
    (path / "nodes.py").write_text(nodes_source, encoding="utf-8")


def test_generate_node_examples_uses_scalar_defaults(tmp_path: Path):
    package = tmp_path / "pkg"
    _write_package(
        package,
        "class GoodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'value': ('INT', {'default': 7})}}\n"
        "    def run(self, value):\n"
        "        return (value,)\n\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
    )

    result = generate_node_examples(package, "GoodNode")

    assert result["status"] == "generated"
    assert result["class_name"] == "GoodNode"
    assert result["examples"] == {"value": 7}
    assert result["unsupported_inputs"] == []


def test_generate_node_examples_uses_enum_first_choice(tmp_path: Path):
    package = tmp_path / "pkg"
    _write_package(
        package,
        "class ChoiceNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('STRING',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'mode': (['fast', 'slow'],)}}\n"
        "    def run(self, mode):\n"
        "        return (mode,)\n\n"
        "NODE_CLASS_MAPPINGS = {'ChoiceNode': ChoiceNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'ChoiceNode': 'Choice Node'}\n",
    )

    result = generate_node_examples(package, "ChoiceNode")

    assert result["status"] == "generated"
    assert result["examples"] == {"mode": "fast"}


def test_generate_node_examples_blocks_runtime_required_inputs(tmp_path: Path):
    package = tmp_path / "pkg"
    _write_package(
        package,
        "class ImageNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('IMAGE',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'image': ('IMAGE',)}}\n"
        "    def run(self, image):\n"
        "        return (image,)\n\n"
        "NODE_CLASS_MAPPINGS = {'ImageNode': ImageNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'ImageNode': 'Image Node'}\n",
    )

    result = generate_node_examples(package, "ImageNode")

    assert result["status"] == "blocked"
    assert result["examples"] == {}
    assert result["unsupported_inputs"] == [
        {
            "name": "image",
            "type": "IMAGE",
            "required": True,
            "reason": "requires_runtime_value",
        }
    ]


def test_generate_node_examples_blocks_invalid_class(tmp_path: Path):
    package = tmp_path / "pkg"
    _write_package(
        package,
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
    )

    result = generate_node_examples(package, "BadNode")

    assert result["status"] == "blocked"
    assert result["reason"] == "invalid_class"
    assert any(error["reason"] == "missing_input_types" for error in result["errors"])
