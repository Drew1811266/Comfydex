from comfydex_mcp.recipes import (
    get_workflow_recipe,
    list_workflow_recipes,
    resolve_recipe_capabilities,
    search_workflow_recipes,
    suggest_workflow_recipes,
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


def test_list_workflow_recipes_includes_2_0_first_class_scenarios():
    recipes = list_workflow_recipes()
    recipe_ids = {recipe["recipe_id"] for recipe in recipes}

    assert {
        "portrait-basic",
        "character-consistency-lora",
        "product-image-basic",
        "inpainting-basic",
        "background-replacement-inpaint",
    }.issubset(recipe_ids)


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


def test_suggest_workflow_recipes_scores_lora_prompt():
    suggestions = suggest_workflow_recipes(
        "make a portrait with a lora style",
        {"lora_name": "style.safetensors", "checkpoint_name": "sdxl.safetensors"},
    )

    assert suggestions[0]["recipe_id"] == "text-to-image-lora"
    assert suggestions[0]["score"] > suggestions[-1]["score"]
    assert any("lora_name parameter" in reason for reason in suggestions[0]["reasons"])


def test_suggest_workflow_recipes_scores_2_0_scenarios():
    cases = [
        (
            "portrait photo",
            {"checkpoint_name": "model.safetensors", "positive_prompt": "portrait"},
            "portrait-basic",
        ),
        (
            "consistent character sheet",
            {
                "checkpoint_name": "model.safetensors",
                "lora_name": "character.safetensors",
                "positive_prompt": "same character",
            },
            "character-consistency-lora",
        ),
        (
            "product image on white background",
            {"checkpoint_name": "model.safetensors", "positive_prompt": "clean product"},
            "product-image-basic",
        ),
        (
            "inpaint masked area",
            {
                "checkpoint_name": "model.safetensors",
                "image": "input.png",
                "mask": "mask.png",
                "positive_prompt": "remove object",
            },
            "inpainting-basic",
        ),
        (
            "replace image background",
            {
                "checkpoint_name": "model.safetensors",
                "image": "input.png",
                "mask": "mask.png",
                "positive_prompt": "studio background",
            },
            "background-replacement-inpaint",
        ),
    ]

    for intent, parameters, expected_recipe_id in cases:
        suggestions = suggest_workflow_recipes(intent, parameters)
        assert suggestions[0]["recipe_id"] == expected_recipe_id


def test_suggest_workflow_recipes_honors_limit():
    suggestions = suggest_workflow_recipes("image upscale", limit=2)

    assert len(suggestions) == 2
    assert suggestions[0]["recipe_id"] == "image-upscale"


def test_suggest_workflow_recipes_accepts_explicit_recipe_id():
    suggestions = suggest_workflow_recipes(
        "anything",
        recipe_id="controlnet-pose",
    )

    assert suggestions == [
        {
            "recipe_id": "controlnet-pose",
            "template_id": "controlnet-skeleton",
            "score": 1000,
            "reasons": ["explicit recipe_id"],
        }
    ]


def test_resolve_recipe_capabilities_reports_ready_recipe():
    object_info = {
        "CheckpointLoaderSimple": {"input": {"required": {}}},
        "CLIPTextEncode": {"input": {"required": {}}},
        "EmptyLatentImage": {"input": {"required": {}}},
        "KSampler": {"input": {"required": {}}},
        "VAEDecode": {"input": {"required": {}}},
        "SaveImage": {"input": {"required": {}}},
    }
    inventory = {
        "models": [{"filename": "sdxl.safetensors", "model_type": "checkpoint"}],
        "by_type": {"checkpoint": [{"filename": "sdxl.safetensors"}]},
    }

    report = resolve_recipe_capabilities(
        "text-to-image-basic",
        {"checkpoint_name": "sdxl.safetensors", "positive_prompt": "a lake"},
        object_info,
        inventory,
    )

    assert report["recipe"]["recipe_id"] == "text-to-image-basic"
    assert report["capability_report"]["can_run_now"] is True


def test_resolve_recipe_capabilities_reports_unknown_recipe():
    report = resolve_recipe_capabilities("missing", {}, {}, {"models": [], "by_type": {}})

    assert report["status"] == "unknown_recipe"
    assert report["recipe_id"] == "missing"
