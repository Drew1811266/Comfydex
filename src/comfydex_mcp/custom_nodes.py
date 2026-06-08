from __future__ import annotations

import ast
import ctypes
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .paths import safe_package_file_path


def inspect_custom_node_package(package_dir: Path) -> dict[str, Any]:
    tree, errors = _parse_nodes(package_dir)
    if tree is None:
        return _inspection_result(
            package_dir,
            node_classes=[],
            class_mappings={},
            display_name_mappings={},
            errors=errors,
        )

    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    return _inspection_result(
        package_dir,
        node_classes=classes,
        class_mappings=_dict_name_mappings(
            tree,
            "NODE_CLASS_MAPPINGS",
            allow_string_values=False,
        ),
        display_name_mappings=_dict_name_mappings(
            tree,
            "NODE_DISPLAY_NAME_MAPPINGS",
            allow_string_values=True,
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

    tree, parse_errors = _parse_nodes(package_dir)
    if tree is None:
        return {
            "status": "invalid",
            "errors": parse_errors,
            "inspection": inspected,
        }

    errors: list[dict[str, Any]] = []
    classes = set(inspected["node_classes"])
    display_names = inspected["display_name_mappings"]
    class_mappings_assignment = _assigned_value(tree, "NODE_CLASS_MAPPINGS")

    if class_mappings_assignment is None:
        errors.append({"reason": "missing_class_mappings"})
    elif not isinstance(class_mappings_assignment, ast.Dict):
        errors.append({"reason": "invalid_class_mappings"})
    else:
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

    tree, parse_errors = _parse_nodes(package_dir)
    if tree is None:
        return {
            "status": "invalid",
            "errors": parse_errors,
            "class_name": class_name,
        }

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
    elif _literal_string_sequence(assigned_values["RETURN_TYPES"]) is None:
        errors.append({"class_name": class_name, "reason": "invalid_return_types"})
    if "FUNCTION" not in assigned_values:
        errors.append({"class_name": class_name, "reason": "missing_function"})
    if "CATEGORY" not in assigned_values:
        errors.append({"class_name": class_name, "reason": "missing_category"})
    elif _literal_string(assigned_values["CATEGORY"]) is None:
        errors.append({"class_name": class_name, "reason": "invalid_category"})

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


def node_class_details(package_dir: Path, class_name: str) -> dict[str, Any]:
    tree, errors = _parse_nodes(package_dir)
    if tree is None:
        return {
            "status": "invalid",
            "errors": errors,
            "class_name": class_name,
            "category": None,
            "function": None,
            "input_types": {},
            "return_types": [],
        }

    class_node = _class_node(tree, class_name)
    if class_node is None:
        return {
            "status": "invalid",
            "errors": [{"class_name": class_name, "reason": "missing_class"}],
            "class_name": class_name,
            "category": None,
            "function": None,
            "input_types": {},
            "return_types": [],
        }

    assigned_values = _class_assigned_values(class_node)
    methods = _class_methods(class_node)
    input_types = {}
    input_types_method = methods.get("INPUT_TYPES")
    if input_types_method is not None:
        input_types = _input_types_schema(input_types_method) or {}

    validation = validate_node_class(package_dir, class_name)
    return {
        "status": validation["status"],
        "errors": validation["errors"],
        "class_name": class_name,
        "category": _literal_string(assigned_values.get("CATEGORY")),
        "function": _literal_string(assigned_values.get("FUNCTION")),
        "input_types": input_types,
        "return_types": _literal_string_sequence(
            assigned_values.get("RETURN_TYPES")
        )
        or [],
    }


def check_node_imports(
    package_dir: Path,
    timeout_seconds: int = 5,
    max_output_bytes: int = 20000,
) -> dict[str, Any]:
    if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        return _import_check_result(
            status="failed",
            reason="invalid_timeout",
            returncode=None,
            stdout="",
            stderr="timeout_seconds must be greater than 0",
            stdout_truncated=False,
            stderr_truncated=False,
        )
    if not isinstance(max_output_bytes, int) or max_output_bytes < 0:
        return _import_check_result(
            status="failed",
            reason="invalid_max_output",
            returncode=None,
            stdout="",
            stderr="max_output_bytes must be greater than or equal to 0",
            stdout_truncated=False,
            stderr_truncated=False,
        )

    package_dir = package_dir.resolve()
    if not package_dir.is_dir():
        return _import_check_result(
            status="failed",
            reason="missing_package_dir",
            returncode=None,
            stdout="",
            stderr=f"package directory not found: {package_dir}",
            stdout_truncated=False,
            stderr_truncated=False,
        )

    script = (
        "import pathlib, sys\n"
        f"package_dir = pathlib.Path({str(package_dir)!r})\n"
        "sys.path.insert(0, str(package_dir.parent))\n"
        "module = __import__(package_dir.name)\n"
        "print(sorted(getattr(module, 'NODE_CLASS_MAPPINGS', {}).keys()))\n"
    )
    process = None
    job = None
    stdout_capture = _BoundedStreamCapture(max_output_bytes)
    stderr_capture = _BoundedStreamCapture(max_output_bytes)
    try:
        popen_kwargs: dict[str, Any] = {}
        if os.name == "posix":
            popen_kwargs["start_new_session"] = True
        elif os.name == "nt":
            try:
                job = _WindowsJob()
            except OSError as exc:
                return _import_check_result(
                    status="failed",
                    reason="process_isolation_error",
                    returncode=None,
                    stdout="",
                    stderr=str(exc),
                    stdout_truncated=False,
                    stderr_truncated=False,
                )

        process = subprocess.Popen(
            [sys.executable, "-I", "-c", script],
            cwd=str(package_dir.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **popen_kwargs,
        )
        if job is not None:
            try:
                job.assign(process)
            except OSError as exc:
                _kill_process_best_effort(process)
                returncode = _wait_process_best_effort(process)
                job.close()
                return _import_check_result(
                    status="failed",
                    reason="process_isolation_error",
                    returncode=returncode,
                    stdout="",
                    stderr=str(exc),
                    stdout_truncated=False,
                    stderr_truncated=False,
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
            _cleanup_process_tree(process, job)
            returncode = _wait_process_best_effort(process)
            reason = "timeout"
        else:
            _cleanup_process_tree(process, job)
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
    except OSError as exc:
        if process is not None:
            _cleanup_process_tree(process, job)
        elif job is not None:
            job.close()
        return _import_check_result(
            status="failed",
            reason="import_check_error",
            returncode=None,
            stdout="",
            stderr=str(exc),
            stdout_truncated=False,
            stderr_truncated=False,
        )

    return _import_check_result(
        status="passed" if reason is None and returncode == 0 else "failed",
        reason=reason,
        returncode=returncode,
        stdout=stdout_capture.text(),
        stderr=stderr_capture.text(),
        stdout_truncated=stdout_capture.truncated,
        stderr_truncated=stderr_capture.truncated,
    )


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


def _parse_nodes(package_dir: Path) -> tuple[ast.Module | None, list[dict[str, Any]]]:
    raw_nodes_py = package_dir / "nodes.py"
    try:
        nodes_py = safe_package_file_path(package_dir, "nodes.py")
    except ValueError:
        return None, [
            {"reason": "redirected_package_file", "path": str(raw_nodes_py)}
        ]

    if not nodes_py.exists():
        return None, [{"reason": "missing_nodes_py", "path": str(nodes_py)}]

    try:
        source = nodes_py.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return None, [
            {
                "reason": "invalid_nodes_py_encoding",
                "path": str(nodes_py),
                "message": str(exc),
            }
        ]
    except OSError as exc:
        return None, [
            {
                "reason": "read_nodes_py_failed",
                "path": str(nodes_py),
                "message": str(exc),
            }
        ]

    try:
        return ast.parse(source, filename=str(nodes_py)), []
    except SyntaxError as exc:
        return None, [
            {
                "reason": "invalid_nodes_py_syntax",
                "path": str(nodes_py),
                "message": exc.msg,
                "lineno": exc.lineno,
                "offset": exc.offset,
            }
        ]


def _dict_name_mappings(
    tree: ast.Module,
    variable_name: str,
    *,
    allow_string_values: bool,
) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for assigned_value in _assigned_values(tree, variable_name):
        if not isinstance(assigned_value, ast.Dict):
            continue
        for key, value in zip(assigned_value.keys, assigned_value.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if isinstance(value, ast.Name):
                mappings[key.value] = value.id
            elif (
                allow_string_values
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                mappings[key.value] = value.value
    return mappings


def _assigned_value(tree: ast.Module, variable_name: str) -> ast.expr | None:
    return next(iter(_assigned_values(tree, variable_name)), None)


def _assigned_values(tree: ast.Module, variable_name: str) -> list[ast.expr]:
    values: list[ast.expr] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = [
                target.id for target in statement.targets if isinstance(target, ast.Name)
            ]
            if variable_name in targets:
                values.append(statement.value)
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == variable_name
            and statement.value is not None
        ):
            values.append(statement.value)
    return values


def _duplicate_dict_keys(tree: ast.Module, variable_name: str) -> list[str]:
    duplicates: list[str] = []
    for assigned_value in _assigned_values(tree, variable_name):
        if not isinstance(assigned_value, ast.Dict):
            continue
        seen: set[str] = set()
        for key in assigned_value.keys:
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
        if not (
            _has_decorator(statement, "classmethod")
            or _has_decorator(statement, "staticmethod")
        ):
            return False
        return _input_types_schema(statement) is not None
    return False


def _input_types_schema(function_node: ast.FunctionDef) -> dict[str, Any] | None:
    for statement in function_node.body:
        if isinstance(statement, ast.Return):
            try:
                schema = ast.literal_eval(statement.value)
            except (ValueError, SyntaxError):
                return None
            if not isinstance(schema, dict):
                return None
            for section_name, section_fields in schema.items():
                if not isinstance(section_name, str):
                    return None
                if not isinstance(section_fields, dict):
                    return None
                if not all(isinstance(input_name, str) for input_name in section_fields):
                    return None
            return schema
    return None


def _literal_string(value: ast.expr | None) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _literal_string_sequence(value: ast.expr | None) -> list[str] | None:
    if value is None:
        return None
    try:
        literal = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(literal, (tuple, list)):
        return None
    if not all(isinstance(item, str) for item in literal):
        return None
    return list(literal)


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


def _import_check_result(
    *,
    status: str,
    reason: str | None,
    returncode: int | None,
    stdout: str,
    stderr: str,
    stdout_truncated: bool,
    stderr_truncated: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }


def _cleanup_process_tree(process: subprocess.Popen[Any], job: Any) -> None:
    if os.name == "nt":
        if job is not None:
            job.close()
        elif process.poll() is None:
            _kill_process_best_effort(process)
        return

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        time.sleep(0.1)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
        return

    if process.poll() is None:
        _kill_process_best_effort(process)


def _kill_process_best_effort(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        process.kill()
    except OSError:
        pass


def _wait_process_best_effort(process: subprocess.Popen[Any]) -> int | None:
    try:
        return process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        _kill_process_best_effort(process)
        try:
            return process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return process.poll()


class _IOCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IOCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WindowsJob:
    _job_object_extended_limit_information = 9
    _job_object_limit_kill_on_job_close = 0x2000

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows Job Objects are only available on Windows")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self._kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        self._kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self._kernel32.SetInformationJobObject.restype = ctypes.c_int
        self._kernel32.AssignProcessToJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.CloseHandle.restype = ctypes.c_int

        self._handle = self._kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError(f"CreateJobObjectW failed: {ctypes.get_last_error()}")

        info = _JobObjectExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = (
            self._job_object_limit_kill_on_job_close
        )
        if not self._kernel32.SetInformationJobObject(
            self._handle,
            self._job_object_extended_limit_information,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            error = ctypes.get_last_error()
            self.close()
            raise OSError(f"SetInformationJobObject failed: {error}")

    def assign(self, process: subprocess.Popen[Any]) -> None:
        process_handle = ctypes.c_void_p(int(process._handle))
        if not self._kernel32.AssignProcessToJobObject(self._handle, process_handle):
            raise OSError(f"AssignProcessToJobObject failed: {ctypes.get_last_error()}")

    def close(self) -> None:
        handle = getattr(self, "_handle", None)
        if handle:
            self._kernel32.CloseHandle(handle)
            self._handle = None


def _unsupported_mapping_value_errors(
    tree: ast.Module,
    variable_name: str,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for assigned_value in _assigned_values(tree, variable_name):
        if not isinstance(assigned_value, ast.Dict):
            continue
        for key, value in zip(assigned_value.keys, assigned_value.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if isinstance(value, ast.Name):
                continue
            errors.append(
                {
                    "mapping_key": key.value,
                    "reason": "unsupported_mapping_value",
                }
            )
    return errors
