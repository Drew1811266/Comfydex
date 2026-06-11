from comfydex_mcp.recipes import (
    get_workflow_recipe,
    list_workflow_recipes,
    search_workflow_recipes,
    validate_workflow_recipes,
)


def test_list_workflow_recipes_includes_core_scenarios():
    recipes = list_workflow_recipes()
    recipe_ids = {recipe["recipe_id"] for recipe in recipes}

    assert "text-to-image-basic" in recipe_ids
    assert "text-to-image-lora" in recipe_ids
    assert "image-to-image-basic" in recipe_ids
    assert "image-upscale" in recipe_ids
    assert "controlnet-pose" in recipe_ids


def test_get_workflow_recipe_returns_template_and_requirements():
    recipe = get_workflow_recipe("text-to-image-lora")

    assert recipe["template_id"] == "lora-text-to-image"
    assert "CheckpointLoaderSimple" in recipe["required_nodes"]
    assert "LoraLoader" in recipe["required_nodes"]
    assert "checkpoint" in recipe["required_model_types"]
    assert "lora" in recipe["required_model_types"]
    assert "checkpoint_name" in recipe["required_inputs"]


def test_search_workflow_recipes_matches_intent_tags_and_nodes():
    results = search_workflow_recipes("pose controlnet skeleton")

    assert results[0]["recipe_id"] == "controlnet-pose"
    assert any(result["recipe_id"] == "controlnet-pose" for result in results)


def test_validate_workflow_recipes_checks_template_ids_and_nodes():
    report = validate_workflow_recipes()

    assert report["status"] == "valid"
    assert report["recipe_count"] >= 5
    assert report["errors"] == []
