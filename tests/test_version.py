import json
import tomllib
from pathlib import Path

import comfydex_mcp


ROOT = Path(__file__).parents[1]


def test_versions_match_0_4_0():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["version"] == "0.4.0"
    assert manifest["version"] == "0.4.0"
    assert comfydex_mcp.__version__ == "0.4.0"
