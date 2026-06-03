from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import ensure_directory, safe_package_dir


def scaffold_custom_node_package(workspace: Path, package_name: str) -> dict[str, Any]:
    custom_nodes_dir = ensure_directory(workspace / "custom_nodes")
    package_dir = safe_package_dir(custom_nodes_dir, package_name)
    ensure_directory(package_dir)
    ensure_directory(package_dir / "tests")

    class_name = _node_class_name(package_name)
    mapping_key = class_name

    (package_dir / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS\n"
        "__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']\n",
        encoding="utf-8",
    )
    (package_dir / "nodes.py").write_text(
        f"class {class_name}:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {'a': ('INT', {'default': 1}), 'b': ('INT', {'default': 1})}}\n\n"
        "    def run(self, a, b):\n"
        "        return (a + b,)\n\n\n"
        f"NODE_CLASS_MAPPINGS = {{{mapping_key!r}: {class_name}}}\n"
        f"NODE_DISPLAY_NAME_MAPPINGS = {{{mapping_key!r}: '{class_name}'}}\n",
        encoding="utf-8",
    )
    (package_dir / "README.md").write_text(
        f"# {package_name}\n\nGenerated ComfyUI custom node package.\n",
        encoding="utf-8",
    )
    (package_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{package_name}"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (package_dir / "tests" / "test_nodes.py").write_text(
        "from nodes import NODE_CLASS_MAPPINGS\n\n\n"
        "def test_sample_node_runs():\n"
        f"    node = NODE_CLASS_MAPPINGS[{mapping_key!r}]()\n"
        "    assert node.run(2, 3) == (5,)\n",
        encoding="utf-8",
    )

    return {
        "package_dir": str(package_dir),
        "mapping_key": mapping_key,
        "class_name": class_name,
    }


def _node_class_name(package_name: str) -> str:
    parts = package_name.replace("-", "_").split("_")
    class_name = "".join(part.capitalize() for part in parts if part) + "Node"
    if not class_name.isidentifier() or not class_name[0].isalpha():
        class_name = f"Custom{class_name}"
    return class_name
