from comfydex_mcp.generation import (
    DEFAULT_CONSTRAINTS,
    normalize_constraints,
    plan_workflow_generation,
)


def test_plan_workflow_generation_scores_candidate_templates():
    plan = plan_workflow_generation(
        "Create an SDXL cinematic city image",
        parameters={
            "checkpoint_name": "sdxl.safetensors",
            "positive_prompt": "cinematic city at night",
        },
    )

    assert plan["selected_template_id"] == "sdxl-text-to-image"
    assert plan["candidate_templates"][0]["template_id"] == "sdxl-text-to-image"
    assert plan["candidate_templates"][0]["score"] > 0
    assert "intent mentions sdxl" in plan["candidate_templates"][0]["reasons"]
    assert plan["missing_information"] == []


def test_plan_workflow_generation_honors_explicit_template_override():
    plan = plan_workflow_generation(
        "make a simple prompt workflow",
        template_id="lora-text-to-image",
        parameters={
            "checkpoint_name": "base.safetensors",
            "lora_name": "style.safetensors",
            "positive_prompt": "portrait",
        },
    )

    assert plan["selected_template_id"] == "lora-text-to-image"
    assert plan["template"]["id"] == "lora-text-to-image"


def test_plan_workflow_generation_normalizes_parameters_and_constraints():
    plan = plan_workflow_generation(
        "text to image",
        parameters={
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "cat",
            "width": "768",
            "height": "512",
            "steps": "25",
            "cfg": "6.5",
            "seed": "42",
        },
        constraints={"max_steps": "50", "max_pixels": "786432"},
    )

    assert plan["parameters"]["width"] == 768
    assert plan["parameters"]["height"] == 512
    assert plan["parameters"]["steps"] == 25
    assert plan["parameters"]["cfg"] == 6.5
    assert plan["parameters"]["seed"] == 42
    assert plan["constraints"]["max_steps"] == 50
    assert plan["constraints"]["max_pixels"] == 786432


def test_plan_workflow_generation_reports_missing_required_information():
    plan = plan_workflow_generation("text to image")

    assert "checkpoint_name" in plan["missing_information"]
    assert "positive_prompt" in plan["missing_information"]


def test_normalize_constraints_uses_safe_defaults():
    assert normalize_constraints({}) == DEFAULT_CONSTRAINTS
