from __future__ import annotations

from pathlib import Path
from typing import Any

from .custom_nodes import inspect_custom_node_package, validate_node_class


def generate_node_docs(package_dir: Path) -> dict[str, Any]:
    inspection = inspect_custom_node_package(package_dir)
    lines = ["# Custom Node Documentation", ""]

    for mapping_key, class_name in sorted(inspection["class_mappings"].items()):
        validation = validate_node_class(package_dir, class_name)
        display_name = inspection["display_name_mappings"].get(
            mapping_key,
            class_name,
        )
        lines.extend(
            [
                f"## {display_name}",
                "",
                f"- Mapping key: `{mapping_key}`",
                f"- Class: `{class_name}`",
                f"- Validation status: `{validation['status']}`",
                "",
            ]
        )

    markdown = "\n".join(lines).rstrip() + "\n"
    path = package_dir / "NODE_DOCS.md"
    path.write_text(markdown, encoding="utf-8")
    return {
        "path": str(path),
        "markdown": markdown,
        "inspection": inspection,
    }
