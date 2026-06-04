from pathlib import Path


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
