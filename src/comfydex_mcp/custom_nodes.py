from __future__ import annotations

import ast
import subprocess
import sys
import threading
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


def validate_node_class(package_dir: Path, class_name: str) -> dict[str, Any]:
    inspected = inspect_custom_node_package(package_dir)
    if inspected["status"] == "invalid":
        return {
            "status": "invalid",
            "errors": inspected["errors"],
            "class_name": class_name,
        }

    tree = _parse_nodes(package_dir)
    class_node = _class_node(tree, class_name)
    if class_node is None:
        return {
            "status": "invalid",
            "errors": [{"class_name": class_name, "reason": "missing_class"}],
            "class_name": class_name,
        }

    errors: list[dict[str, Any]] = []
    assigned_values = _class_assigned_values(class_node)
    methods = _class_methods(class_node)
    method_names = set(methods)

    if "INPUT_TYPES" not in method_names:
        errors.append({"class_name": class_name, "reason": "missing_input_types"})
    elif not _has_valid_input_types_method(class_node):
        errors.append({"class_name": class_name, "reason": "invalid_input_types"})
    if "RETURN_TYPES" not in assigned_values:
        errors.append({"class_name": class_name, "reason": "missing_return_types"})
    if "FUNCTION" not in assigned_values:
        errors.append({"class_name": class_name, "reason": "missing_function"})
    if "CATEGORY" not in assigned_values:
        errors.append({"class_name": class_name, "reason": "missing_category"})

    function_value = assigned_values.get("FUNCTION")
    if function_value is not None and not (
        isinstance(function_value, ast.Constant)
        and isinstance(function_value.value, str)
    ):
        errors.append({"class_name": class_name, "reason": "invalid_function"})
    elif isinstance(function_value, ast.Constant) and isinstance(function_value.value, str):
        function_name = function_value.value
        if function_name not in method_names or _has_decorator(
            methods[function_name],
            "property",
        ):
            errors.append(
                {
                    "class_name": class_name,
                    "function": function_name,
                    "reason": "missing_callable_function",
                }
            )

    return {
        "status": "invalid" if errors else "valid",
        "errors": errors,
        "class_name": class_name,
    }


def check_node_imports(
    package_dir: Path,
    timeout_seconds: int = 5,
    max_output_bytes: int = 20000,
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    if not package_dir.is_dir():
        return {
            "status": "failed",
            "reason": "missing_package_dir",
            "returncode": None,
            "stdout": "",
            "stderr": f"package directory not found: {package_dir}",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }

    script = (
        "import pathlib, sys\n"
        f"package_dir = pathlib.Path({str(package_dir)!r})\n"
        "sys.path.insert(0, str(package_dir.parent))\n"
        "module = __import__(package_dir.name)\n"
        "print(sorted(getattr(module, 'NODE_CLASS_MAPPINGS', {}).keys()))\n"
    )
    process = None
    stdout_capture = _BoundedStreamCapture(max_output_bytes)
    stderr_capture = _BoundedStreamCapture(max_output_bytes)
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", script],
            cwd=str(package_dir.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_thread = threading.Thread(
            target=stdout_capture.read_from,
            args=(process.stdout,),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=stderr_capture.read_from,
            args=(process.stderr,),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        try:
            returncode = process.wait(timeout=timeout_seconds)
            reason = None if returncode == 0 else "import_error"
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
            reason = "timeout"
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
    except OSError as exc:
        return {
            "status": "failed",
            "reason": "import_check_error",
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "stdout_truncated": False,
            "stderr_truncated": False,
        }

    return {
        "status": "passed" if returncode == 0 else "failed",
        "reason": reason,
        "returncode": returncode,
        "stdout": stdout_capture.text(),
        "stderr": stderr_capture.text(),
        "stdout_truncated": stdout_capture.truncated,
        "stderr_truncated": stderr_capture.truncated,
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


def _class_node(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _class_assigned_values(class_node: ast.ClassDef) -> dict[str, ast.expr]:
    values: dict[str, ast.expr] = {}
    for statement in class_node.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name):
                values[target.id] = statement.value
    return values


def _class_methods(class_node: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {
        statement.name: statement
        for statement in class_node.body
        if isinstance(statement, ast.FunctionDef)
    }


def _has_valid_input_types_method(class_node: ast.ClassDef) -> bool:
    for statement in class_node.body:
        if not isinstance(statement, ast.FunctionDef) or statement.name != "INPUT_TYPES":
            continue
        return _has_decorator(statement, "classmethod") or _has_decorator(
            statement,
            "staticmethod",
        )
    return False


def _has_decorator(function_node: ast.FunctionDef, decorator_name: str) -> bool:
    return any(
        isinstance(decorator, ast.Name) and decorator.id == decorator_name
        for decorator in function_node.decorator_list
    )


class _BoundedStreamCapture:
    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max(0, max_bytes)
        self._chunks: list[bytes] = []
        self._size = 0
        self.truncated = False

    def read_from(self, stream: Any) -> None:
        if stream is None:
            return
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            self._append(chunk)

    def text(self) -> str:
        return b"".join(self._chunks).decode("utf-8", errors="replace")

    def _append(self, chunk: bytes) -> None:
        remaining = self._max_bytes - self._size
        if remaining <= 0:
            self.truncated = True
            return
        if len(chunk) > remaining:
            self._chunks.append(chunk[:remaining])
            self._size += remaining
            self.truncated = True
            return
        self._chunks.append(chunk)
        self._size += len(chunk)


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
