from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def inspect_custom_node_package(package_dir: Path) -> dict[str, Any]:
    nodes_py = package_dir / "nodes.py"
    if not nodes_py.exists():
        return _inspection_result(
            package_dir,
            node_classes=[],
            class_mappings={},
            display_name_mappings={},
            errors=[{"reason": "missing_nodes_py", "path": str(nodes_py)}],
        )

    tree = _parse_nodes(package_dir)
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    return _inspection_result(
        package_dir,
        node_classes=classes,
        class_mappings=_dict_name_mappings(tree, "NODE_CLASS_MAPPINGS"),
        display_name_mappings=_dict_name_mappings(
            tree,
            "NODE_DISPLAY_NAME_MAPPINGS",
        ),
        errors=[],
    )


def validate_node_mappings(package_dir: Path) -> dict[str, Any]:
    inspected = inspect_custom_node_package(package_dir)
    if inspected["status"] == "invalid":
        return {
            "status": "invalid",
            "errors": inspected["errors"],
            "inspection": inspected,
        }

    tree = _parse_nodes(package_dir)
    errors: list[dict[str, Any]] = []
    classes = set(inspected["node_classes"])
    display_names = inspected["display_name_mappings"]

    for duplicate in _duplicate_dict_keys(tree, "NODE_CLASS_MAPPINGS"):
        errors.append(
            {
                "mapping_key": duplicate,
                "reason": "duplicate_mapping_key",
            }
        )
    errors.extend(_unsupported_mapping_value_errors(tree, "NODE_CLASS_MAPPINGS"))

    for mapping_key, class_name in inspected["class_mappings"].items():
        if class_name not in classes:
            errors.append(
                {
                    "mapping_key": mapping_key,
                    "class_name": class_name,
                    "reason": "missing_class",
                }
            )
        if mapping_key not in display_names:
            errors.append(
                {
                    "mapping_key": mapping_key,
                    "reason": "missing_display_name",
                }
            )

    return {
        "status": "invalid" if errors else "valid",
        "errors": errors,
        "inspection": inspected,
    }


def _inspection_result(
    package_dir: Path,
    *,
    node_classes: list[str],
    class_mappings: dict[str, str],
    display_name_mappings: dict[str, str],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "invalid" if errors else "valid",
        "errors": errors,
        "package_dir": str(package_dir),
        "node_classes": node_classes,
        "class_mappings": class_mappings,
        "display_name_mappings": display_name_mappings,
    }


def _nodes_py(package_dir: Path) -> Path:
    path = package_dir / "nodes.py"
    if not path.exists():
        raise ValueError(f"missing nodes.py: {path}")
    return path


def _parse_nodes(package_dir: Path) -> ast.Module:
    return ast.parse(_nodes_py(package_dir).read_text(encoding="utf-8"))


def _dict_name_mappings(tree: ast.Module, variable_name: str) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        targets = [
            target.id for target in statement.targets if isinstance(target, ast.Name)
        ]
        if variable_name not in targets or not isinstance(statement.value, ast.Dict):
            continue
        for key, value in zip(statement.value.keys, statement.value.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if isinstance(value, ast.Name):
                mappings[key.value] = value.id
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                mappings[key.value] = value.value
    return mappings


def _duplicate_dict_keys(tree: ast.Module, variable_name: str) -> list[str]:
    duplicates: list[str] = []
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        targets = [
            target.id for target in statement.targets if isinstance(target, ast.Name)
        ]
        if variable_name not in targets or not isinstance(statement.value, ast.Dict):
            continue
        seen: set[str] = set()
        for key in statement.value.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if key.value in seen:
                duplicates.append(key.value)
            seen.add(key.value)
    return duplicates


def _unsupported_mapping_value_errors(
    tree: ast.Module,
    variable_name: str,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        targets = [
            target.id for target in statement.targets if isinstance(target, ast.Name)
        ]
        if variable_name not in targets or not isinstance(statement.value, ast.Dict):
            continue
        for key, value in zip(statement.value.keys, statement.value.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if isinstance(value, ast.Name):
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                continue
            errors.append(
                {
                    "mapping_key": key.value,
                    "reason": "unsupported_mapping_value",
                }
            )
    return errors
