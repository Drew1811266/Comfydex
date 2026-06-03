from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path(".codex-plugin/plugin.json")
MCP_CONFIG_PATH = Path(".mcp.json")
REQUIRED_MANIFEST_KEYS = {
    "name",
    "version",
    "description",
    "skills",
    "mcpServers",
    "interface",
}


def _load_json_object(root: Path, relative_path: Path, errors: list[str]) -> dict[str, Any] | None:
    path = root / relative_path
    if not path.exists():
        errors.append(f"Missing required JSON file: {relative_path.as_posix()}")
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {relative_path.as_posix()}: {exc}")
        return None

    if not isinstance(data, dict):
        errors.append(f"{relative_path.as_posix()} must contain a JSON object")
        return None

    return data


def validate_plugin(root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve()

    manifest = _load_json_object(root, MANIFEST_PATH, errors)
    if manifest is not None:
        missing_keys = sorted(REQUIRED_MANIFEST_KEYS - manifest.keys())
        for key in missing_keys:
            errors.append(f"{MANIFEST_PATH.as_posix()} is missing required key: {key}")

        skills_path = manifest.get("skills")
        if isinstance(skills_path, str):
            skills_dir = root / skills_path
            if not skills_dir.is_dir():
                errors.append(f"Skills directory does not exist: {skills_path}")
            elif not any(skills_dir.glob("*/SKILL.md")):
                errors.append(f"Skills directory must contain at least one */SKILL.md: {skills_path}")
        elif "skills" in manifest:
            errors.append(f"{MANIFEST_PATH.as_posix()} key 'skills' must be a string path")

    mcp_config = _load_json_object(root, MCP_CONFIG_PATH, errors)
    if mcp_config is not None and "mcpServers" not in mcp_config:
        errors.append(f"{MCP_CONFIG_PATH.as_posix()} is missing required key: mcpServers")

    if not (root / "pyproject.toml").is_file():
        errors.append("Missing required file: pyproject.toml")

    if not (root / "src/comfydex_mcp/server.py").is_file():
        errors.append("Missing required file: src/comfydex_mcp/server.py")

    return errors


def main() -> int:
    errors = validate_plugin(Path.cwd())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Comfydex plugin validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
