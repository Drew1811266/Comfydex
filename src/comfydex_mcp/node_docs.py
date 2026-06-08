from __future__ import annotations

from pathlib import Path
from typing import Any

from .custom_nodes import (
    inspect_custom_node_package,
    node_class_details,
    validate_node_mappings,
)
from .paths import safe_package_file_path


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
        details = node_class_details(package_dir, class_name)
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
                f"- Validation status: `{details['status']}`",
                f"- Category: `{details['category'] or 'unknown'}`",
                "",
            ]
        )
        lines.extend(_input_lines(details["input_types"]))
        lines.extend(_output_lines(details["return_types"]))
        lines.extend(_example_lines(class_name, details))

    markdown = "\n".join(lines).rstrip() + "\n"
    path = safe_package_file_path(package_dir, "NODE_DOCS.md")
    path.write_text(markdown, encoding="utf-8")
    return {
        "path": str(path),
        "markdown": markdown,
        "inspection": inspection,
        "mapping_validation": mapping_validation,
    }


def _input_lines(input_types: dict[str, Any]) -> list[str]:
    lines = ["### Inputs", ""]
    if not input_types:
        return lines + ["- None", ""]

    ordered_sections = [
        section
        for section in ("required", "optional", "hidden")
        if section in input_types
    ]
    ordered_sections.extend(
        sorted(section for section in input_types if section not in ordered_sections)
    )
    for section in ordered_sections:
        fields = input_types.get(section)
        if not isinstance(fields, dict):
            continue
        lines.extend([f"#### {section.title()}", ""])
        if not fields:
            lines.extend(["- None", ""])
            continue
        for input_name, input_spec in sorted(fields.items()):
            lines.append(f"- `{input_name}`: {_format_input_spec(input_spec)}")
        lines.append("")
    return lines


def _output_lines(return_types: list[str]) -> list[str]:
    lines = ["### Outputs", ""]
    if not return_types:
        return lines + ["- None", ""]
    lines.extend(f"- `{return_type}`" for return_type in return_types)
    lines.append("")
    return lines


def _example_lines(class_name: str, details: dict[str, Any]) -> list[str]:
    function = details.get("function") or "run"
    required_inputs = details.get("input_types", {}).get("required", {})
    if isinstance(required_inputs, dict):
        args = ", ".join(f"{name}=None" for name in sorted(required_inputs))
    else:
        args = ""
    lines = [
        "### Examples",
        "",
        "```python",
        f"node = {class_name}()",
        f"result = node.{function}({args})",
        "```",
        "",
    ]
    return lines


def _format_input_spec(input_spec: Any) -> str:
    if isinstance(input_spec, (tuple, list)) and input_spec:
        input_type = input_spec[0]
        if isinstance(input_type, str):
            return f"`{input_type}`"
    if isinstance(input_spec, str):
        return f"`{input_spec}`"
    return f"`{input_spec!r}`"
