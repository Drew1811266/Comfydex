import json
from pathlib import Path

from comfydex_mcp.workflows import classify_workflow


ROOT = Path(__file__).parents[1]


def test_workflow_skill_mentions_new_tool_order():
    text = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "comfy_import_ui_workflow" in text
    assert "comfy_build_workflow_plan" in text
    assert "comfy_validate_api_workflow" in text


def test_custom_node_skill_exists_and_mentions_workspace_boundary():
    text = (ROOT / "skills" / "comfyui-custom-nodes" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "custom_nodes/" in text
    assert "comfy_scaffold_custom_node_package" in text
    assert "comfy_check_node_imports" in text


def test_example_workflows_are_classified():
    api = json.loads(
        (ROOT / "examples" / "workflows" / "basic_text_to_image.api.json").read_text(
            encoding="utf-8"
        )
    )
    ui = json.loads(
        (ROOT / "examples" / "workflows" / "sample_ui_workflow.ui.json").read_text(
            encoding="utf-8"
        )
    )

    assert classify_workflow(api) == "api"
    assert classify_workflow(ui) == "ui"


def test_example_custom_node_contains_mappings():
    text = (
        ROOT / "examples" / "custom_nodes" / "simple_math_node" / "nodes.py"
    ).read_text(encoding="utf-8")

    assert "NODE_CLASS_MAPPINGS" in text
    assert "NODE_DISPLAY_NAME_MAPPINGS" in text


def test_example_report_is_markdown():
    text = (ROOT / "examples" / "reports" / "sample_run_report.md").read_text(
        encoding="utf-8"
    )

    assert text.startswith("# Comfydex Run Report")
