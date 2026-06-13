from __future__ import annotations

from comfydex_mcp.live_bridge import explain_canvas_replacement


def test_explain_canvas_replacement_requires_review_for_unsaved_canvas():
    result = explain_canvas_replacement(
        {"diagnostics": [{"code": "unsaved_canvas", "message": "Unsaved"}]},
        workflow_name="new.ui.json",
        force=False,
    )

    assert result["title"] == "Review before replacing the canvas"
    assert result["requires_confirmation"] is True
    assert result["severity"] == "warn"
    assert "new.ui.json" in result["summary"]
    assert "unsaved_canvas" in result["technical"]["diagnostic_codes"]


def test_explain_canvas_replacement_allows_forced_replace():
    result = explain_canvas_replacement(
        {"diagnostics": [{"code": "unsaved_canvas", "message": "Unsaved"}]},
        workflow_name="new.ui.json",
        force=True,
    )

    assert result["title"] == "Canvas replacement is ready"
    assert result["requires_confirmation"] is False
    assert result["severity"] == "ok"
