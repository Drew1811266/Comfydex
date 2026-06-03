import pytest

from comfydex_mcp.templates import (
    build_template_plan,
    list_workflow_templates,
    suggest_workflow_template,
)


EXPECTED_TEMPLATE_IDS = {
    "basic-text-to-image",
    "basic-image-to-image",
    "upscale",
    "sdxl-text-to-image",
    "lora-text-to-image",
    "controlnet-skeleton",
}


def test_list_workflow_templates_returns_initial_catalog():
    templates = list_workflow_templates()

    assert len(templates) == 6
    assert {template["id"] for template in templates} == EXPECTED_TEMPLATE_IDS


def test_each_template_has_required_metadata():
    templates = list_workflow_templates()

    for template in templates:
        assert set(template) >= {
            "id",
            "name",
            "description",
            "required_nodes",
            "parameters",
            "required_inputs",
            "assumptions",
            "tags",
        }
        assert isinstance(template["required_nodes"], list)
        assert template["required_nodes"]


@pytest.mark.parametrize(
    ("intent", "expected_template_id"),
    [
        ("make an image from a prompt", "basic-text-to-image"),
        ("image to image variation", "basic-image-to-image"),
        ("use sdxl", "sdxl-text-to-image"),
        ("add lora", "lora-text-to-image"),
        ("controlnet pose", "controlnet-skeleton"),
        ("upscale this image", "upscale"),
    ],
)
def test_suggest_workflow_template_matches_common_intents(intent, expected_template_id):
    suggestion = suggest_workflow_template(intent)

    assert suggestion["id"] == expected_template_id


def test_build_template_plan_merges_parameters_and_reports_missing_information(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    plan = build_template_plan(
        "make an image from a prompt",
        "basic-text-to-image",
        {"positive_prompt": "a quiet studio", "width": 768},
    )

    assert plan["intent"] == "make an image from a prompt"
    assert plan["template"]["id"] == "basic-text-to-image"
    assert plan["required_nodes"]
    assert plan["parameters"]["positive_prompt"] == "a quiet studio"
    assert plan["parameters"]["width"] == 768
    assert "height" in plan["parameters"]
    assert "assumptions" in plan
    assert "missing_information" in plan
    assert "checkpoint_name" in plan["missing_information"]
    assert "positive_prompt" not in plan["missing_information"]
    assert list(tmp_path.iterdir()) == []


def test_build_template_plan_selects_template_when_id_is_not_provided():
    plan = build_template_plan("upscale this image", parameters={"image": "input.png"})

    assert plan["template"]["id"] == "upscale"


def test_build_template_plan_raises_for_unknown_template_id():
    with pytest.raises(ValueError):
        build_template_plan("make an image", "missing-template", {})
