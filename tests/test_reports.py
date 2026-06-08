from pathlib import Path

import pytest

from comfydex_mcp import reports
from comfydex_mcp.reports import export_run_report


def test_export_run_report_writes_completed_run_markdown(tmp_path: Path):
    run_record = {
        "run_id": "run-1",
        "workflow_name": "portrait.json",
        "prompt_id": "prompt-1",
        "status": "completed",
        "outputs": [
            {
                "filename": "portrait.png",
                "subfolder": "samples",
                "type": "output",
                "downloaded_path": "outputs/portrait.png",
                "full_history_dump": "x" * 1000,
            }
        ],
    }
    workflow_summary = {"node_count": 4, "node_types": {"KSampler": 1}}
    diagnosis = {"summary": "Run completed with one image.", "signals": ["completed"]}

    result = export_run_report(tmp_path, run_record, workflow_summary, diagnosis)

    path = tmp_path / "report.md"
    assert result["path"] == str(path)
    assert result["markdown"] == path.read_text(encoding="utf-8")
    assert "# Comfydex Run Report" in result["markdown"]
    assert "run-1" in result["markdown"]
    assert "portrait.json" in result["markdown"]
    assert "prompt-1" in result["markdown"]
    assert "completed" in result["markdown"]
    assert "Run completed with one image." in result["markdown"]
    assert "completed" in result["markdown"]
    assert "Node count: 4" in result["markdown"]
    assert "portrait.png" in result["markdown"]
    assert "outputs/portrait.png" in result["markdown"]
    assert "samples" in result["markdown"]
    assert "full_history_dump" not in result["markdown"]
    assert "x" * 100 not in result["markdown"]


def test_export_run_report_notes_when_no_outputs_registered(tmp_path: Path):
    result = export_run_report(
        tmp_path,
        {"run_id": "run-2", "workflow_name": "empty.json", "prompt_id": "prompt-2", "status": "completed", "outputs": []},
        {"node_count": 1},
        {"summary": "Completed run has no registered outputs.", "signals": ["missing_outputs"]},
    )

    assert "No outputs registered" in result["markdown"]


def test_export_run_report_uses_downloaded_path_fallback_and_sorts_signals(tmp_path: Path):
    result = export_run_report(
        tmp_path,
        {
            "run_id": "run-3",
            "workflow_name": "fallback.json",
            "prompt_id": "prompt-3",
            "status": "failed",
            "outputs": [
                {"downloaded_path": "outputs/fallback.png", "type": "output"},
            ],
        },
        {"node_count": 2},
        {"summary": "Failure detected.", "signals": ["websocket_error", "execution_error"]},
    )

    markdown = result["markdown"]
    assert "outputs/fallback.png" in markdown
    assert markdown.index("execution_error") < markdown.index("websocket_error")


def test_export_run_report_handles_malformed_outputs_signals_and_summary(tmp_path: Path):
    result = export_run_report(
        tmp_path,
        {"run_id": "run-4", "outputs": ["bad", None, {"filename": "valid.png"}, {"debug_dump": "ignored"}]},
        "bad summary",
        {"summary": {"nested": "ignored"}, "signals": ["alpha", None, 3, "", {"bad": "ignored"}]},
    )

    assert result["path"] == str(tmp_path / "report.md")
    assert "run-4" in result["markdown"]
    assert "valid.png" in result["markdown"]
    assert "alpha" in result["markdown"]


def test_export_run_report_rejects_redirected_report_path(
    monkeypatch,
    tmp_path: Path,
):
    def redirected(path: Path) -> bool:
        return path.name == "report.md"

    monkeypatch.setattr(reports, "is_redirected_path", redirected, raising=False)

    with pytest.raises(ValueError, match="report.md"):
        export_run_report(
            tmp_path,
            {"run_id": "run-5", "workflow_name": "wf.json", "status": "completed"},
            {"node_count": 1},
            {"summary": "ok", "signals": []},
        )
