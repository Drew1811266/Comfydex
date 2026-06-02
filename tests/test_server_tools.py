from pathlib import Path

from comfydex_mcp.server import resolve_workspace, tool_context


def test_resolve_workspace_uses_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEX_WORKSPACE", str(tmp_path))
    assert resolve_workspace() == tmp_path.resolve()


def test_tool_context_loads_default_config(tmp_path: Path):
    ctx = tool_context(tmp_path)
    assert ctx.config.base_url == "http://127.0.0.1:8188"
    assert ctx.config.workflows_dir == tmp_path / "workflows"
