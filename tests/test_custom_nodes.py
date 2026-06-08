import ctypes
import os
import signal
import subprocess
import sys
import time
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


def test_validate_node_mappings_rejects_string_class_mapping_value(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': 'GoodNode'}\n"
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


def test_validate_node_mappings_reports_missing_class_mappings(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"] == [{"reason": "missing_class_mappings"}]


def test_validate_node_mappings_reports_call_class_mappings(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n"
        "def build():\n"
        "    return {'GoodNode': GoodNode}\n"
        "NODE_CLASS_MAPPINGS = build()\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"] == [{"reason": "invalid_class_mappings"}]


def test_validate_node_mappings_reports_list_class_mappings(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n"
        "NODE_CLASS_MAPPINGS = []\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'GoodNode': 'Good Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"] == [{"reason": "invalid_class_mappings"}]


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


def test_validate_node_class_reports_missing_return_types_function_and_category(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
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

    reasons = {error["reason"] for error in result["errors"]}
    assert result["status"] == "invalid"
    assert {"missing_return_types", "missing_function", "missing_category"}.issubset(
        reasons
    )


def test_validate_node_class_reports_missing_class(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class GoodNode: pass\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "MissingNode")

    assert result["status"] == "invalid"
    assert result["errors"] == [
        {"class_name": "MissingNode", "reason": "missing_class"}
    ]


def test_validate_node_class_reports_missing_nodes_py(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()

    result = validate_node_class(package, "MissingNode")

    assert result["status"] == "invalid"
    assert result["errors"] == [
        {"reason": "missing_nodes_py", "path": str(package / "nodes.py")}
    ]


def test_validate_node_class_accepts_classmethod_and_staticmethod_input_types(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class ClassMethodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "class StaticMethodNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @staticmethod\n"
        "    def INPUT_TYPES():\n"
        "        return {'required': {}}\n"
        "    def run(self):\n"
        "        return (1,)\n",
        encoding="utf-8",
    )

    classmethod_result = validate_node_class(package, "ClassMethodNode")
    staticmethod_result = validate_node_class(package, "StaticMethodNode")

    assert classmethod_result["status"] == "valid"
    assert staticmethod_result["status"] == "valid"


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


def test_validate_node_class_reports_invalid_return_types(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = 'INT'\n"
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
    assert any(error["reason"] == "invalid_return_types" for error in result["errors"])


def test_validate_node_class_reports_invalid_category(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 123\n"
        "    FUNCTION = 'run'\n"
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
    assert any(error["reason"] == "invalid_category" for error in result["errors"])


def test_validate_node_class_reports_list_input_types_return(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return []\n"
        "    def run(self):\n"
        "        return (1,)\n"
        "NODE_CLASS_MAPPINGS = {'BadNode': BadNode}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {'BadNode': 'Bad Node'}\n",
        encoding="utf-8",
    )

    result = validate_node_class(package, "BadNode")

    assert result["status"] == "invalid"
    assert any(error["reason"] == "invalid_input_types" for error in result["errors"])


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


def test_validate_node_class_reports_property_function_target(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode:\n"
        "    CATEGORY = 'Comfydex'\n"
        "    FUNCTION = 'run'\n"
        "    RETURN_TYPES = ('INT',)\n"
        "    @classmethod\n"
        "    def INPUT_TYPES(cls):\n"
        "        return {'required': {}}\n"
        "    @property\n"
        "    def run(self):\n"
        "        return lambda: (1,)\n"
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
    assert result["reason"] == "import_error"
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


def test_check_node_imports_truncates_output_on_timeout(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS\n",
        encoding="utf-8",
    )
    (package / "nodes.py").write_text(
        "while True:\n"
        "    print('x' * 1000)\n",
        encoding="utf-8",
    )

    result = check_node_imports(package, timeout_seconds=1, max_output_bytes=2048)

    assert result["status"] == "failed"
    assert result["reason"] == "timeout"
    assert len(result["stdout"].encode("utf-8")) <= 2048
    assert result["stdout_truncated"] is True


def test_check_node_imports_returns_missing_package_failure(tmp_path: Path):
    result = check_node_imports(tmp_path / "missing")

    assert result["status"] == "failed"
    assert result["reason"] == "missing_package_dir"


def test_inspect_custom_node_package_reports_syntax_error_without_raising(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode(:\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = inspect_custom_node_package(package)

    assert result["status"] == "invalid"
    assert result["node_classes"] == []
    assert result["class_mappings"] == {}
    assert result["display_name_mappings"] == {}
    assert result["errors"][0]["reason"] == "invalid_nodes_py_syntax"


def test_validate_node_mappings_reports_syntax_error_without_raising(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "nodes.py").write_text(
        "class BadNode(:\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = validate_node_mappings(package)

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "invalid_nodes_py_syntax"


def test_inspect_custom_node_package_rejects_redirected_nodes_py(
    monkeypatch,
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    nodes_py = package / "nodes.py"
    nodes_py.write_text(
        "class GoodNode: pass\n"
        "NODE_CLASS_MAPPINGS = {'GoodNode': GoodNode}\n",
        encoding="utf-8",
    )

    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path: Path):
        if path == nodes_py:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    result = inspect_custom_node_package(package)

    assert result["status"] == "invalid"
    assert result["node_classes"] == []
    assert result["class_mappings"] == {}
    assert result["errors"] == [
        {"reason": "redirected_package_file", "path": str(nodes_py)}
    ]


def test_check_node_imports_rejects_invalid_direct_options(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()

    timeout_result = check_node_imports(package, timeout_seconds=0)
    output_result = check_node_imports(package, max_output_bytes=-1)

    assert timeout_result["status"] == "failed"
    assert timeout_result["reason"] == "invalid_timeout"
    assert output_result["status"] == "failed"
    assert output_result["reason"] == "invalid_max_output"


def test_check_node_imports_kills_descendants_after_successful_import(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    marker = package / "child.pid"
    child_code = (
        "import pathlib, sys, time, os\n"
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    (package / "__init__.py").write_text(
        "from .nodes import NODE_CLASS_MAPPINGS\n",
        encoding="utf-8",
    )
    (package / "nodes.py").write_text(
        "import subprocess, sys, time\n"
        f"marker = {str(marker)!r}\n"
        f"child_code = {child_code!r}\n"
        "subprocess.Popen([sys.executable, '-c', child_code, marker])\n"
        "deadline = time.time() + 5\n"
        "while not __import__('pathlib').Path(marker).exists() and time.time() < deadline:\n"
        "    time.sleep(0.05)\n"
        "NODE_CLASS_MAPPINGS = {}\n",
        encoding="utf-8",
    )

    result = check_node_imports(package, timeout_seconds=5)

    assert result["status"] == "passed"
    child_pid = int(marker.read_text(encoding="utf-8"))
    try:
        deadline = time.monotonic() + 5
        while _pid_is_running(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        if _pid_is_running(child_pid):
            pytest_message = f"descendant process {child_pid} survived import check"
            raise AssertionError(pytest_message)
    finally:
        if _pid_is_running(child_pid):
            _kill_pid(child_pid)


def _pid_is_running(pid: int) -> bool:
    if sys.platform == "win32":
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
