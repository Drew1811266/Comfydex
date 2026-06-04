from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import ensure_directory

TEXT_MAX_LENGTH = 200
OUTPUT_FIELDS = ("filename", "downloaded_path", "type", "subfolder")


def _clean_text(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    if not isinstance(value, (str, int, float, bool)):
        return default
    text = " ".join(str(value).split())
    if not text:
        return default
    if len(text) > TEXT_MAX_LENGTH:
        return text[: TEXT_MAX_LENGTH - 3].rstrip() + "..."
    return text


def _node_count(workflow_summary: Any) -> str:
    if not isinstance(workflow_summary, dict):
        return "0"
    value = workflow_summary.get("node_count", 0)
    if isinstance(value, bool):
        return "0"
    if isinstance(value, int) and value >= 0:
        return str(value)
    return "0"


def _signals(diagnosis: Any) -> list[str]:
    if not isinstance(diagnosis, dict):
        return []
    values = diagnosis.get("signals", [])
    if not isinstance(values, list):
        return []
    return sorted({_clean_text(value, "") for value in values if _clean_text(value, "")})


def _diagnosis_summary(diagnosis: Any) -> str:
    if not isinstance(diagnosis, dict):
        return "No diagnosis summary available."
    return _clean_text(diagnosis.get("summary"), "No diagnosis summary available.")


def _outputs(run_record: Any) -> list[dict[str, str]]:
    if not isinstance(run_record, dict):
        return []
    values = run_record.get("outputs", [])
    if not isinstance(values, list):
        return []

    outputs: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        output = {
            field: _clean_text(value.get(field), "")
            for field in OUTPUT_FIELDS
            if _clean_text(value.get(field), "")
        }
        if output:
            outputs.append(output)
    return sorted(
        outputs,
        key=lambda output: (
            output.get("filename", ""),
            output.get("downloaded_path", ""),
            output.get("type", ""),
            output.get("subfolder", ""),
        ),
    )


def _format_outputs(outputs: list[dict[str, str]]) -> list[str]:
    if not outputs:
        return ["No outputs registered."]

    lines: list[str] = []
    for output in outputs:
        label = output.get("filename") or output.get("downloaded_path") or "output"
        details = [
            f"{field}: {output[field]}"
            for field in ("downloaded_path", "type", "subfolder")
            if output.get(field)
        ]
        suffix = f" ({'; '.join(details)})" if details else ""
        lines.append(f"- {label}{suffix}")
    return lines


def export_run_report(
    run_dir: Path,
    run_record: dict[str, Any],
    workflow_summary: dict[str, Any],
    diagnosis: dict[str, Any],
) -> dict[str, str]:
    path = ensure_directory(run_dir) / "report.md"
    signals = _signals(diagnosis)
    outputs = _outputs(run_record)

    lines = [
        "# Comfydex Run Report",
        "",
        "## Run",
        "",
        f"- Run id: {_clean_text(run_record.get('run_id') if isinstance(run_record, dict) else None)}",
        f"- Workflow name: {_clean_text(run_record.get('workflow_name') if isinstance(run_record, dict) else None)}",
        f"- Prompt id: {_clean_text(run_record.get('prompt_id') if isinstance(run_record, dict) else None)}",
        f"- Status: {_clean_text(run_record.get('status') if isinstance(run_record, dict) else None)}",
        "",
        "## Diagnosis",
        "",
        f"- Summary: {_diagnosis_summary(diagnosis)}",
        f"- Signals: {', '.join(signals) if signals else 'None'}",
        "",
        "## Workflow Summary",
        "",
        f"- Node count: {_node_count(workflow_summary)}",
        "",
        "## Outputs",
        "",
        *_format_outputs(outputs),
        "",
    ]
    markdown = "\n".join(lines)
    path.write_text(markdown, encoding="utf-8")
    return {"path": str(path), "markdown": markdown}
