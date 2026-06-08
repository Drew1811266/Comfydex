from __future__ import annotations

from pathlib import Path
from typing import Any

from .custom_nodes import node_class_details

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
