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


def test_usage_docs_cover_new_capabilities():
    required = {
        "workflow-import.md": "comfy_convert_ui_to_api",
        "workflow-builder.md": "comfy_build_workflow_plan",
        "custom-node-development.md": "comfy_validate_node_class",
        "run-diagnostics.md": "comfy_diagnose_run",
    }
    for filename, marker in required.items():
        text = (ROOT / "docs" / "usage" / filename).read_text(encoding="utf-8")
        assert marker in text


def test_readme_mentions_0_2_capabilities():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "0.2.0" in text
    assert "UI workflow" in text
    assert "custom node" in text
    assert "batch" in text


def test_readme_does_not_describe_0_2_features_as_future_scope():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "first release" not in text
    assert "Not included yet" not in text
    assert "UI workflow JSON to API prompt JSON conversion" not in text
    assert "custom node package scaffolding" not in text
    assert "old output cleanup" not in text


def test_workflow_skill_uses_current_version_language():
    text = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "First-version Comfydex" not in text
    assert "validated API prompt JSON" in text


def test_run_diagnostics_doc_lists_required_inputs():
    text = (ROOT / "docs" / "usage" / "run-diagnostics.md").read_text(
        encoding="utf-8"
    )

    for marker in ("run_id", "confirm=True", "failed_run_ids", "variations"):
        assert marker in text
    assert "concurrency" not in text


def test_readme_uses_local_plugin_validator():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "python scripts/validate_plugin.py" in text
    assert "plugin-creator/scripts/validate_plugin.py" not in text
