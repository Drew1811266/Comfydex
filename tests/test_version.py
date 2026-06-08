import json
import tomllib
from pathlib import Path

import comfydex_mcp


ROOT = Path(__file__).parents[1]


EXPECTED_VERSION = "1.0.0"


def test_versions_match_expected_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert manifest["version"] == EXPECTED_VERSION
    assert comfydex_mcp.__version__ == EXPECTED_VERSION
