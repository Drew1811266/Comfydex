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
    assert "comfy_build_ui_workflow" in text
    assert "comfy_generate_ui_workflow" in text
    assert "comfy_generate_push_ui_workflow" in text
    assert "comfy_read_ui_graph_history" in text
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
        "ui-graph-builder.md": "comfy_generate_push_ui_workflow",
        "end-to-end-automation.md": "comfy_generate_run_fetch",
        "asset-library.md": "comfy_search_assets",
        "desktop-app.md": "Tauri",
    }
    for filename, marker in required.items():
        text = (ROOT / "docs" / "usage" / filename).read_text(encoding="utf-8")
        assert marker in text


def test_readme_mentions_0_8_capabilities():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "0.8.0" in text
    assert "Gallery And Batch UI" in text
    assert "asset gallery" in text
    assert "batch task view" in text
    assert "safe cleanup UI" in text
    assert "desktop/" in text
    assert "Tauri" in text
    assert "Python desktop bridge" in text
    assert "UI workflow" in text
    assert "custom node" in text
    assert "batch" in text
    assert "project index" in text
    assert "workflow generation" in text
    assert "comfy_project_status" in text
    assert "comfy_reindex_project" in text
    assert "comfy_plan_workflow_generation" in text
    assert "comfy_generate_workflow" in text
    assert "comfy_generate_run_fetch" in text
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


def test_readme_mentions_0_9_automation():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "0.9.0" in text
    assert "End-To-End Automation And Hardening" in text
    assert "comfy_generate_run_fetch" in text
    assert "confirm_risky_actions" in text
    assert "validate_release_package.py" in text


def test_readme_mentions_1_0_release():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "1.0.0" in text
    assert "Usable Developer Release" in text
    assert "scripts/install_windows.ps1" in text
    assert "comfy_generate_run_fetch" in text
    assert "validate_release_package.py" in text


def test_end_to_end_automation_docs_cover_confirmation_and_recovery():
    usage = (ROOT / "docs" / "usage" / "end-to-end-automation.md").read_text(
        encoding="utf-8"
    )
    skill = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "comfy_generate_run_fetch",
        "confirm_risky_actions",
        "wait_for_completion",
        "fetch_outputs",
        "object_info_unavailable",
        "reindex",
    ):
        assert marker in usage
        assert marker in skill


def test_release_docs_cover_1_0_install_and_review():
    install_doc = (ROOT / "docs" / "release" / "windows-install.md").read_text(
        encoding="utf-8"
    )
    checklist = (ROOT / "docs" / "release" / "1.0-release-checklist.md").read_text(
        encoding="utf-8"
    )
    security = (ROOT / "docs" / "release" / "security-path-review.md").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "scripts" / "install_windows.ps1").read_text(
        encoding="utf-8"
    )

    for marker in (
        "python -m pip install -e",
        "npm --prefix desktop install",
        "comfy_check_connection",
    ):
        assert marker in install_doc
        assert marker in script
    for marker in (
        "python -m pytest tests -q",
        "git ls-remote origin refs/heads/main refs/tags/v1.0.0",
    ):
        assert marker in checklist
    for marker in (
        "path traversal",
        "header redaction",
        "cleanup confirmation",
        "desktop bridge",
    ):
        assert marker in security


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


def test_desktop_app_docs_cover_tauri_shell():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "usage" / "desktop-app.md").read_text(
        encoding="utf-8"
    )
    skill = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "Tauri",
        "desktop/",
        "Python desktop bridge",
        "project_status",
        "search_assets",
        "0.7 non-goals",
    ):
        assert marker in usage
    assert "desktop/" in readme
    assert "desktop app shell" in skill
    assert "Python desktop bridge" in skill


def test_desktop_app_docs_cover_gallery_batch_ui():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "usage" / "desktop-app.md").read_text(
        encoding="utf-8"
    )
    skill = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "Gallery",
        "Compare",
        "Cleanup",
        "Generate report",
        "Batches",
        "Batch detail",
        "Confirm cleanup",
    ):
        assert marker in usage
    assert "Gallery And Batch UI" in readme
    assert "desktop gallery" in skill
    assert "batch task view" in skill


def test_live_bridge_docs_cover_install_verify_remove_and_desktop_status():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "usage" / "live-bridge.md").read_text(
        encoding="utf-8"
    )
    desktop = (ROOT / "docs" / "usage" / "desktop-app.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        'scripts\\install_live_bridge.ps1 -ComfyBaseDir "E:\\ComfyUI files"',
        'scripts\\install_live_bridge.ps1 -ComfyCustomNodesDir "E:\\ComfyUI files\\custom_nodes"',
        'scripts\\verify_live_bridge.ps1 -BaseUrl "http://127.0.0.1:8188" -SkipPush',
        'scripts\\verify_live_bridge.ps1 -BaseUrl "http://127.0.0.1:8188" -WorkflowPath "workflows\\z-image-turbo-text-to-image.ui.json" -Force',
        'Remove-Item -LiteralPath "E:\\ComfyUI files\\custom_nodes\\comfydex_live_bridge"',
        "Ready: ComfyUI reachable, backend route loaded, frontend extension listed, frontend connected.",
        "Restart required: ComfyUI reachable but bridge status route is missing.",
        "Refresh required: backend route loaded but frontend client has not heartbeated or is stale.",
        "Unsaved canvas: frontend refused a push because the current workflow has unsaved changes.",
    ):
        assert marker in usage

    for marker in (
        "Live Bridge",
        "Ready",
        "Restart required",
        "Refresh required",
        "Reload client",
        "Reload backend",
    ):
        assert marker in desktop
        assert marker in readme


def test_release_checklist_1_2_covers_live_bridge_release_gates():
    checklist = (ROOT / "docs" / "release" / "1.2-release-checklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "clean worktree",
        "python -m pytest -q",
        "node --check custom_nodes\\comfydex_live_bridge\\web\\comfydex_live_bridge.js",
        "PowerShell parser checks",
        "npm run typecheck",
        "npm run build",
        "cargo check",
        "manual ComfyUI restart verification",
        "push verification with a UI workflow",
    ):
        assert marker in checklist


def test_node_semantic_registry_docs_cover_supported_unknown_and_tools():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    usage = (ROOT / "docs" / "usage" / "node-semantic-registry.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "Node Semantic Registry",
        "comfy_list_node_semantics",
        "comfy_explain_node_semantics",
        "comfy_search_node_semantics",
        "comfy_validate_node_semantics",
        "CheckpointLoaderSimple",
        "KSampler",
        "Unknown nodes are not treated as first-class supported nodes.",
    ):
        assert marker in usage
        assert marker in readme


def test_release_checklist_1_3_covers_registry_release_gates():
    checklist = (ROOT / "docs" / "release" / "1.3-release-checklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "python -m pytest -q",
        "registry validation",
        "object_info matching",
        "MCP registry tools",
        "unknown-node refusal",
        "version files report `1.3.0`",
    ):
        assert marker in checklist


def test_capability_resolver_docs_cover_install_planner():
    usage = (ROOT / "docs" / "usage" / "capability-resolver.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for marker in (
        "Capability Resolver",
        "model inventory",
        "node inventory",
        "object_info",
        "conservative install plan",
        "audit log",
        "no silent downloads",
        "comfy_model_inventory",
        "comfy_resolve_capabilities",
        "comfy_create_install_plan",
        "comfy_record_install_audit",
        "desktop Install Plan",
    ):
        assert marker in usage
        assert marker in readme


def test_release_checklist_1_4_covers_capability_release_gates():
    checklist = (ROOT / "docs" / "release" / "1.4-release-checklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "python -m pytest -q",
        "npm run typecheck",
        "npm run build",
        "cargo check",
        "comfy_resolve_capabilities",
        "conservative install plan",
        "audit log",
        "no silent downloads",
        "desktop Install Plan",
        "version files report `1.4.0`",
    ):
        assert marker in checklist


def test_scenario_recipe_docs_cover_recipe_aware_planning():
    usage = (ROOT / "docs" / "usage" / "scenario-recipes.md").read_text(
        encoding="utf-8"
    )
    capability = (ROOT / "docs" / "usage" / "capability-resolver.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "Scenario Recipe Registry",
        "recipe candidates",
        "selected recipe id",
        "comfy_suggest_workflow_recipes",
        "comfy_resolve_recipe_capabilities",
        "recipe-aware capability checks",
        "no automatic downloads",
    ):
        assert marker in usage
        assert marker in capability
        assert marker in readme
        assert marker in skill


def test_release_checklist_1_5_covers_recipe_release_gates():
    checklist = (ROOT / "docs" / "release" / "1.5-release-checklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "python -m pytest -q",
        "recipe registry tests",
        "MCP recipe tools",
        "desktop bridge recipe operations",
        "recipe-aware planning",
        "recipe-aware capability checks",
        "no automatic downloads",
        "npm run typecheck",
        "npm run build",
        "cargo check",
        "version files report `1.5.0`",
    ):
        assert marker in checklist


def test_ui_graph_builder_docs_cover_generated_graphs():
    usage = (ROOT / "docs" / "usage" / "ui-graph-builder.md").read_text(
        encoding="utf-8"
    )
    desktop = (ROOT / "docs" / "usage" / "desktop-app.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "UI Graph Builder",
        "generated UI workflow",
        "readable graph",
        "stable node ids",
        "comfy_build_ui_workflow",
        "comfy_generate_ui_workflow",
        "comfy_generate_push_ui_workflow",
        "comfy_read_ui_graph_history",
        "Live Bridge push",
        "no full visual editor",
    ):
        assert marker in usage

    for marker in (
        "Generated Graphs",
        "generated UI workflow history",
        "push_ui_workflow",
    ):
        assert marker in desktop

    for marker in (
        "UI Graph Builder",
        "Generated Graphs",
        "comfy_generate_push_ui_workflow",
    ):
        assert marker in readme
        assert marker in skill


def test_release_checklist_1_6_covers_ui_graph_release_gates():
    checklist = (ROOT / "docs" / "release" / "1.6-release-checklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "python -m pytest -q",
        "UI graph builder tests",
        "MCP UI graph tools",
        "desktop bridge operations",
        "Generated Graphs desktop view",
        "Live Bridge push",
        "npm run typecheck",
        "npm run build",
        "cargo check",
        "validate_release_package.py",
        "version files report `1.6.0`",
    ):
        assert marker in checklist


def test_execution_repair_loop_docs_cover_repair_tools_and_desktop():
    usage = (ROOT / "docs" / "usage" / "execution-repair-loop.md").read_text(
        encoding="utf-8"
    )
    desktop = (ROOT / "docs" / "usage" / "desktop-app.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills" / "comfyui-workflows" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "Execution And Repair Loop",
        "failure_class",
        "repair_plan",
        "comfy_plan_run_repair",
        "comfy_retry_run_repair",
        "comfy_read_repair_history",
        "comfy_generate_run_fetch",
        "fetch_outputs",
        "requires_confirmation",
        "no silent downloads",
    ):
        assert marker in usage
        assert marker in readme
        assert marker in skill

    for marker in (
        "Runs repair panel",
        "plan_run_repair",
        "retry_run_repair",
        "read_repair_history",
    ):
        assert marker in desktop


def test_release_checklist_1_7_covers_execution_repair_release_gates():
    checklist = (ROOT / "docs" / "release" / "1.7-release-checklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "python -m pytest -q",
        "repair planner tests",
        "MCP repair tools",
        "automation failure repair payloads",
        "desktop bridge repair operations",
        "Runs repair panel",
        "npm run typecheck",
        "npm run build",
        "cargo check",
        "validate_release_package.py",
        "version files report `1.7.0`",
    ):
        assert marker in checklist


def test_ordinary_user_guidance_doc_covers_1_8_user_polish():
    usage = (ROOT / "docs" / "usage" / "ordinary-user-polish.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for marker in (
        "Ordinary User Guidance",
        "quality_preset",
        "aspect_ratio",
        "style_preset",
        "user_guidance",
        "resolved_defaults",
        "canvas_replacement",
        "output_summary",
        "comfy_list_generation_presets",
        "comfy_summarize_assets",
    ):
        assert marker in usage
        assert marker in readme


def test_release_checklist_1_8_covers_ordinary_user_release_gates():
    checklist = (ROOT / "docs" / "release" / "1.8-release-checklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "python -m pytest -q",
        "plain user guidance helpers",
        "generation presets",
        "MCP user guidance tools",
        "desktop bridge user guidance operations",
        "desktop ordinary-user UI polish",
        "Browser desktop and mobile verification",
        "npm run typecheck",
        "npm run build",
        "cargo check",
        "validate_release_package.py",
        "version files report `1.8.0`",
    ):
        assert marker in checklist


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
