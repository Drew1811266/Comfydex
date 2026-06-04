from __future__ import annotations

from pathlib import Path
from typing import Any

from .custom_nodes import (
    inspect_custom_node_package,
    validate_node_class,
    validate_node_mappings,
)


def generate_node_docs(package_dir: Path) -> dict[str, Any]:
    inspection = inspect_custom_node_package(package_dir)
    mapping_validation = validate_node_mappings(package_dir)
    lines = ["# Custom Node Documentation", ""]

    if mapping_validation["status"] == "invalid":
        lines.extend(["## Mapping Validation", ""])
        for error in mapping_validation["errors"]:
            mapping_key = error.get("mapping_key", "package")
            lines.append(f"- `{mapping_key}`: {error['reason']}")
        lines.append("")

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
        "mapping_validation": mapping_validation,
    }
