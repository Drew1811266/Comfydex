import json
from pathlib import Path

from comfydex_mcp.workflows import classify_workflow


ROOT = Path(__file__).parents[1]


def test_workflow_skill_mentions_new_tool_order():
    text = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "comfy_import_ui_workflow" in text
    assert "comfy_project_status" in text
    assert "comfy_reindex_project" in text
    assert "comfy_plan_workflow_generation" in text
    assert "comfy_generate_workflow" in text
    assert "comfy_evaluate_submit_policy" in text
    assert "comfy_reindex_assets" in text
    assert "comfy_search_assets" in text
    assert "comfy_update_asset_metadata" in text
    assert "comfy_plan_asset_cleanup" in text
    assert "comfy_build_workflow_plan" in text
    assert "comfy_validate_api_workflow" in text


def test_custom_node_skill_exists_and_mentions_workspace_boundary():
    text = (ROOT / "skills" / "comfyui-custom-nodes" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "custom_nodes/" in text
    assert "comfy_scaffold_custom_node_package" in text
    assert "comfy_check_node_imports" in text
    assert "comfy_generate_node_examples" in text
    assert "comfy_run_node_contract_tests" in text
    assert "comfy_custom_node_repair_guidance" in text


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
        "project-index.md": "comfy_reindex_project",
        "workflow-generation.md": "comfy_generate_workflow",
        "asset-library.md": "comfy_search_assets",
    }
    for filename, marker in required.items():
        text = (ROOT / "docs" / "usage" / filename).read_text(encoding="utf-8")
        assert marker in text


def test_readme_mentions_0_6_capabilities():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "0.6.0" in text
    assert "UI workflow" in text
    assert "custom node" in text
    assert "batch" in text
    assert "project index" in text
    assert "workflow generation" in text
    assert "comfy_project_status" in text
    assert "comfy_reindex_project" in text
    assert "comfy_plan_workflow_generation" in text
    assert "comfy_generate_workflow" in text
    assert "comfy_evaluate_submit_policy" in text
    assert "comfy_generate_node_examples" in text
    assert "comfy_run_node_contract_tests" in text
    assert "comfy_custom_node_repair_guidance" in text
    assert "comfy_reindex_assets" in text
    assert "comfy_search_assets" in text
    assert "comfy_update_asset_metadata" in text
    assert "comfy_write_asset_sidecars" in text
    assert "comfy_plan_asset_cleanup" in text
    assert "comfy_export_asset_library_report" in text
    assert "comfy_compare_assets" in text
    assert ".comfydex/comfydex.db" in text


def test_custom_node_docs_cover_complete_loop_tools():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "usage" / "custom-node-development.md").read_text(
        encoding="utf-8"
    )
    skill = (ROOT / "skills" / "comfyui-custom-nodes" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "comfy_generate_node_examples",
        "comfy_run_node_contract_tests",
        "comfy_custom_node_repair_guidance",
    ):
        assert marker in readme
        assert marker in usage
        assert marker in skill


def test_project_index_doc_explains_reindex_safety():
    text = (ROOT / "docs" / "usage" / "project-index.md").read_text(
        encoding="utf-8"
    )

    assert ".comfydex/comfydex.db" in text
    assert "comfy_project_status" in text
    assert "comfy_reindex_project" in text
    assert "schema version `2`" in text
    assert "assets" in text
    assert "does not delete" in text
    assert "compatibility records" in text


def test_asset_library_docs_cover_asset_tools():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "usage" / "asset-library.md").read_text(
        encoding="utf-8"
    )
    skill = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "comfy_reindex_assets",
        "comfy_search_assets",
        "comfy_update_asset_metadata",
        "comfy_write_asset_sidecars",
        "comfy_plan_asset_cleanup",
        "comfy_export_asset_library_report",
        "comfy_compare_assets",
    ):
        assert marker in readme
        assert marker in usage
        assert marker in skill


def test_workflow_generation_doc_explains_submit_policy():
    text = (ROOT / "docs" / "usage" / "workflow-generation.md").read_text(
        encoding="utf-8"
    )

    assert "comfy_plan_workflow_generation" in text
    assert "comfy_generate_workflow" in text
    assert "comfy_evaluate_submit_policy" in text
    assert "allowed" in text
    assert "requires_confirmation" in text
    assert "blocked" in text


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
