from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from .custom_nodes import (
    _BoundedStreamCapture,
    _WindowsJob,
    _cleanup_process_tree,
    _kill_process_best_effort,
    _wait_process_best_effort,
    check_node_imports,
    node_class_details,
    parse_traceback_diagnostics,
    validate_node_class,
    validate_node_mappings,
)

SCALAR_DEFAULTS: dict[str, Any] = {
    "INT": 1,
    "FLOAT": 1.0,
    "STRING": "example",
    "BOOLEAN": False,
    "BOOL": False,
}

RUNTIME_REQUIRED_TYPES = {
    "IMAGE",
    "LATENT",
    "MODEL",
    "CLIP",
    "VAE",
    "CONDITIONING",
}

_MISSING = object()
_CONTRACT_RESULT_MARKER = "COMFYDEX_CONTRACT_RESULT="


def generate_node_examples(package_dir: Path, class_name: str) -> dict[str, Any]:
    details = node_class_details(package_dir, class_name)
    if details["status"] != "valid":
        return {
            "status": "blocked",
            "reason": "invalid_class",
            "class_name": class_name,
            "errors": details["errors"],
            "examples": {},
            "unsupported_inputs": [],
        }

    examples: dict[str, Any] = {}
    unsupported: list[dict[str, Any]] = []
    input_types = details.get("input_types", {})
    required = input_types.get("required", {}) if isinstance(input_types, dict) else {}

    for input_name, input_spec in required.items():
        generated = _example_for_input(input_name, input_spec, required=True)
        if generated["status"] == "generated":
            examples[input_name] = generated["value"]
        else:
            unsupported.append(generated["error"])

    return {
        "status": "blocked" if unsupported else "generated",
        "class_name": class_name,
        "examples": examples if not unsupported else {},
        "unsupported_inputs": unsupported,
        "input_groups": ["required"],
    }


def run_node_contract_tests(
    package_dir: Path,
    class_name: str,
    timeout_seconds: int = 5,
    max_output_bytes: int = 20000,
) -> dict[str, Any]:
    examples = generate_node_examples(package_dir, class_name)
    if examples["status"] != "generated":
        return {
            "status": "blocked",
            "reason": "example_generation_blocked",
            "class_name": class_name,
            "examples": examples,
            "contract": None,
            "diagnostics": {},
        }

    details = node_class_details(package_dir, class_name)
    expected_return_count = len(details.get("return_types", []))
    process_result = _run_contract_subprocess(
        package_dir.resolve(),
        class_name,
        examples["examples"],
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    contract = process_result.get("contract")
    if process_result["status"] != "passed" or contract is None:
        return {
            "status": "failed",
            "reason": process_result["reason"],
            "class_name": class_name,
            "examples": examples,
            "contract": contract,
            "diagnostics": parse_traceback_diagnostics(process_result["stderr"]),
            "stdout": process_result["stdout"],
            "stderr": process_result["stderr"],
            "stdout_truncated": process_result["stdout_truncated"],
            "stderr_truncated": process_result["stderr_truncated"],
        }

    contract["expected_return_count"] = expected_return_count
    if not contract["result_is_tuple"]:
        return _contract_failure(
            "result_not_tuple",
            class_name,
            examples,
            contract,
            process_result,
        )
    if contract["result_length"] != expected_return_count:
        return _contract_failure(
            "return_count_mismatch",
            class_name,
            examples,
            contract,
            process_result,
        )

    return {
        "status": "passed",
        "reason": "contract_passed",
        "class_name": class_name,
        "examples": examples,
        "contract": contract,
        "diagnostics": {},
        "stdout": process_result["stdout"],
        "stderr": process_result["stderr"],
        "stdout_truncated": process_result["stdout_truncated"],
        "stderr_truncated": process_result["stderr_truncated"],
    }


def custom_node_repair_guidance(package_dir: Path) -> dict[str, Any]:
    mappings = validate_node_mappings(package_dir)
    imports = check_node_imports(package_dir)
    actions: list[dict[str, Any]] = []
    actions.extend(_mapping_actions(mappings.get("errors", [])))

    inspection = mappings.get("inspection", {})
    class_mappings = inspection.get("class_mappings", {})
    if isinstance(class_mappings, dict):
        for mapping_key, class_name in class_mappings.items():
            class_result = validate_node_class(package_dir, class_name)
            actions.extend(_class_actions(class_result.get("errors", []), mapping_key))

    if imports["status"] != "passed":
        actions.append(
            {
                "reason": "import_failed",
                "severity": "blocked",
                "message": imports["diagnostics"].get("summary")
                or imports["reason"]
                or "Custom node package import failed.",
                "next_step": "Fix the import error before running contract tests.",
            }
        )

    blocked = any(action["severity"] == "blocked" for action in actions)
    return {
        "status": "blocked" if blocked else "needs_work" if actions else "ready",
        "package_dir": str(package_dir),
        "actions": actions,
        "mapping_status": mappings["status"],
        "import_status": imports["status"],
    }


def _mapping_actions(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    guidance = {
        "missing_class_mappings": (
            "blocked",
            "Define NODE_CLASS_MAPPINGS in nodes.py.",
            "Add NODE_CLASS_MAPPINGS = {'MappingName': ClassName}.",
        ),
        "invalid_class_mappings": (
            "blocked",
            "NODE_CLASS_MAPPINGS must be a literal dictionary.",
            "Replace dynamic mapping construction with a literal dictionary.",
        ),
        "duplicate_mapping_key": (
            "blocked",
            "NODE_CLASS_MAPPINGS contains duplicate mapping keys.",
            "Keep one entry for the duplicated mapping key.",
        ),
        "unsupported_mapping_value": (
            "blocked",
            "NODE_CLASS_MAPPINGS values must reference class names directly.",
            "Use {'MappingName': ClassName} instead of calls or string values.",
        ),
        "missing_class": (
            "blocked",
            "A mapped custom node class is missing from nodes.py.",
            "Create the class or update the mapping to reference an existing class.",
        ),
        "missing_display_name": (
            "important",
            "NODE_DISPLAY_NAME_MAPPINGS is missing an entry for a mapped node.",
            "Add NODE_DISPLAY_NAME_MAPPINGS with a display name for every mapping key.",
        ),
    }
    return [_action_from_error(error, guidance) for error in errors]


def _class_actions(
    errors: list[dict[str, Any]],
    mapping_key: str,
) -> list[dict[str, Any]]:
    guidance = {
        "missing_input_types": (
            "blocked",
            "Custom node class is missing INPUT_TYPES.",
            "Add a classmethod or staticmethod INPUT_TYPES returning a dictionary.",
        ),
        "invalid_input_types": (
            "blocked",
            "INPUT_TYPES must be a classmethod or staticmethod returning a literal dictionary.",
            "Return {'required': {...}} from INPUT_TYPES.",
        ),
        "invalid_input_spec": (
            "blocked",
            "An INPUT_TYPES field has a malformed input spec.",
            "Use specs like ('INT', {'default': 1}) or (['choice'],).",
        ),
        "missing_return_types": (
            "blocked",
            "Custom node class is missing RETURN_TYPES.",
            "Add RETURN_TYPES as a tuple of output type strings.",
        ),
        "invalid_return_types": (
            "blocked",
            "RETURN_TYPES must be a tuple or list of strings.",
            "Set RETURN_TYPES = ('INT',) or another tuple of ComfyUI output types.",
        ),
        "missing_function": (
            "blocked",
            "Custom node class is missing FUNCTION.",
            "Set FUNCTION to the method name that executes the node.",
        ),
        "invalid_function": (
            "blocked",
            "FUNCTION must be a string method name.",
            "Set FUNCTION = 'run' or another callable method name.",
        ),
        "missing_callable_function": (
            "blocked",
            "FUNCTION references a missing or non-callable method.",
            "Add the method named by FUNCTION and make it a normal callable method.",
        ),
        "missing_category": (
            "important",
            "Custom node class is missing CATEGORY.",
            "Set CATEGORY to the ComfyUI menu category for this node.",
        ),
        "invalid_category": (
            "important",
            "CATEGORY must be a string.",
            "Set CATEGORY = 'Comfydex' or another string category.",
        ),
        "missing_class": (
            "blocked",
            "A mapped class could not be found.",
            "Create the class or fix NODE_CLASS_MAPPINGS.",
        ),
    }
    actions = [_action_from_error(error, guidance) for error in errors]
    for action in actions:
        action["mapping_key"] = mapping_key
    return actions


def _action_from_error(
    error: dict[str, Any],
    guidance: dict[str, tuple[str, str, str]],
) -> dict[str, Any]:
    reason = error.get("reason", "unknown")
    severity, message, next_step = guidance.get(
        reason,
        (
            "important",
            f"Custom node validation reported {reason}.",
            "Inspect the validation error and adjust nodes.py.",
        ),
    )
    action = {
        "reason": reason,
        "severity": severity,
        "message": message,
        "next_step": next_step,
    }
    for key in ("mapping_key", "class_name", "input_name", "input_group", "function"):
        if key in error:
            action[key] = error[key]
    return action


def _run_contract_subprocess(
    package_dir: Path,
    class_name: str,
    examples: dict[str, Any],
    *,
    timeout_seconds: int,
    max_output_bytes: int,
) -> dict[str, Any]:
    if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        return _subprocess_result(
            status="failed",
            reason="invalid_timeout",
            returncode=None,
            stdout="",
            stderr="timeout_seconds must be greater than 0",
            stdout_truncated=False,
            stderr_truncated=False,
            contract=None,
        )
    if not isinstance(max_output_bytes, int) or max_output_bytes < 0:
        return _subprocess_result(
            status="failed",
            reason="invalid_max_output",
            returncode=None,
            stdout="",
            stderr="max_output_bytes must be greater than or equal to 0",
            stdout_truncated=False,
            stderr_truncated=False,
            contract=None,
        )

    script = _contract_script(package_dir, class_name, examples)
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
                return _subprocess_result(
                    status="failed",
                    reason="process_isolation_error",
                    returncode=None,
                    stdout="",
                    stderr=str(exc),
                    stdout_truncated=False,
                    stderr_truncated=False,
                    contract=None,
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
                return _subprocess_result(
                    status="failed",
                    reason="process_isolation_error",
                    returncode=returncode,
                    stdout="",
                    stderr=str(exc),
                    stdout_truncated=False,
                    stderr_truncated=False,
                    contract=None,
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
            reason = None if returncode == 0 else "contract_execution_failed"
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
        return _subprocess_result(
            status="failed",
            reason="contract_execution_error",
            returncode=None,
            stdout="",
            stderr=str(exc),
            stdout_truncated=False,
            stderr_truncated=False,
            contract=None,
        )

    stdout = stdout_capture.text()
    contract = _contract_from_stdout(stdout)
    if reason is None and contract is None:
        reason = "missing_contract_result"
    return _subprocess_result(
        status="passed" if reason is None and returncode == 0 else "failed",
        reason=reason or "contract_passed",
        returncode=returncode,
        stdout=stdout,
        stderr=stderr_capture.text(),
        stdout_truncated=stdout_capture.truncated,
        stderr_truncated=stderr_capture.truncated,
        contract=contract,
    )


def _contract_script(
    package_dir: Path,
    class_name: str,
    examples: dict[str, Any],
) -> str:
    examples_json = json.dumps(examples)
    return (
        "import json, pathlib, sys, traceback\n"
        f"marker = {json.dumps(_CONTRACT_RESULT_MARKER)}\n"
        f"package_dir = pathlib.Path({str(package_dir)!r})\n"
        f"class_name = {class_name!r}\n"
        f"examples = json.loads({examples_json!r})\n"
        "try:\n"
        "    sys.path.insert(0, str(package_dir.parent))\n"
        "    module = __import__(package_dir.name)\n"
        "    mappings = getattr(module, 'NODE_CLASS_MAPPINGS', {})\n"
        "    cls = mappings[class_name]\n"
        "    function_name = getattr(cls, 'FUNCTION')\n"
        "    if not isinstance(function_name, str):\n"
        "        raise TypeError('FUNCTION must be a string')\n"
        "    instance = cls()\n"
        "    result = getattr(instance, function_name)(**examples)\n"
        "    payload = {\n"
        "        'result_is_tuple': isinstance(result, tuple),\n"
        "        'result_length': len(result) if isinstance(result, tuple) else None,\n"
        "        'result_repr': repr(result)[:1000],\n"
        "    }\n"
        "    print(marker + json.dumps(payload, sort_keys=True))\n"
        "except Exception:\n"
        "    traceback.print_exc()\n"
        "    raise SystemExit(1)\n"
    )


def _contract_from_stdout(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if not line.startswith(_CONTRACT_RESULT_MARKER):
            continue
        try:
            payload = json.loads(line[len(_CONTRACT_RESULT_MARKER) :])
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return payload
    return None


def _subprocess_result(
    *,
    status: str,
    reason: str | None,
    returncode: int | None,
    stdout: str,
    stderr: str,
    stdout_truncated: bool,
    stderr_truncated: bool,
    contract: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "contract": contract,
    }


def _contract_failure(
    reason: str,
    class_name: str,
    examples: dict[str, Any],
    contract: dict[str, Any],
    process_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "failed",
        "reason": reason,
        "class_name": class_name,
        "examples": examples,
        "contract": contract,
        "diagnostics": {},
        "stdout": process_result["stdout"],
        "stderr": process_result["stderr"],
        "stdout_truncated": process_result["stdout_truncated"],
        "stderr_truncated": process_result["stderr_truncated"],
    }


def _example_for_input(
    input_name: str,
    input_spec: Any,
    *,
    required: bool,
) -> dict[str, Any]:
    default = _default_from_options(input_spec)
    type_name = _type_name(input_spec)
    if default is not _MISSING:
        return {"status": "generated", "value": default}

    first_choice = _literal_first_choice(input_spec)
    if first_choice is not _MISSING:
        return {"status": "generated", "value": first_choice}

    if type_name is None:
        return {
            "status": "unsupported",
            "error": {
                "name": input_name,
                "type": None,
                "required": required,
                "reason": "invalid_input_spec",
            },
        }

    normalized_type = type_name.upper()
    if normalized_type in SCALAR_DEFAULTS:
        return {"status": "generated", "value": SCALAR_DEFAULTS[normalized_type]}

    reason = (
        "requires_runtime_value"
        if normalized_type in RUNTIME_REQUIRED_TYPES
        else "unsupported_input_type"
    )
    return {
        "status": "unsupported",
        "error": {
            "name": input_name,
            "type": normalized_type,
            "required": required,
            "reason": reason,
        },
    }


def _default_from_options(input_spec: Any) -> Any:
    if not isinstance(input_spec, (tuple, list)) or len(input_spec) < 2:
        return _MISSING
    options = input_spec[1]
    if isinstance(options, dict) and "default" in options:
        return options["default"]
    return _MISSING


def _type_name(input_spec: Any) -> str | None:
    if isinstance(input_spec, str):
        return input_spec
    if not isinstance(input_spec, (tuple, list)) or not input_spec:
        return None
    first_item = input_spec[0]
    if isinstance(first_item, str):
        return first_item
    return None


def _literal_first_choice(input_spec: Any) -> Any:
    if not isinstance(input_spec, (tuple, list)) or not input_spec:
        return _MISSING
    choices = input_spec[0]
    if not isinstance(choices, (tuple, list)) or not choices:
        return _MISSING
    return choices[0]
