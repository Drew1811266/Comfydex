from pathlib import Path

import pytest

from comfydex_mcp.templates import (
    build_template_plan,
    get_workflow_template,
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
    "inpaint-basic",
}


def test_list_workflow_templates_returns_initial_catalog():
    templates = list_workflow_templates()

    assert len(templates) == 7
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


def test_each_template_has_graph_recipe_metadata():
    templates = list_workflow_templates()

    for template in templates:
        assert isinstance(template["nodes"], list)
        assert template["nodes"]
        assert isinstance(template["links"], list)
        node_keys = {node["key"] for node in template["nodes"]}
        assert len(node_keys) == len(template["nodes"])
        node_class_types = {node["class_type"] for node in template["nodes"]}
        assert set(template["required_nodes"]).issubset(node_class_types)

        for node in template["nodes"]:
            assert set(node) >= {"key", "class_type", "inputs"}
            assert isinstance(node["key"], str)
            assert isinstance(node["class_type"], str)
            assert isinstance(node["inputs"], dict)

        for link in template["links"]:
            assert set(link) == {"from", "output_slot", "to", "input"}
            assert link["from"] in node_keys
            assert link["to"] in node_keys
            assert isinstance(link["output_slot"], int)
            assert isinstance(link["input"], str)


def test_template_accessors_return_deep_copies():
    listed_template = list_workflow_templates()[0]
    listed_template["nodes"][0]["inputs"]["mutated"] = {"value": "bad"}

    fresh_template = get_workflow_template(listed_template["id"])

    assert "mutated" not in fresh_template["nodes"][0]["inputs"]


@pytest.mark.parametrize(
    ("intent", "expected_template_id"),
    [
        ("make an image from a prompt", "basic-text-to-image"),
        ("image to image variation", "basic-image-to-image"),
        ("use sdxl", "sdxl-text-to-image"),
        ("add lora", "lora-text-to-image"),
        ("controlnet pose", "controlnet-skeleton"),
        ("upscale this image", "upscale"),
        ("inpaint the masked area", "inpaint-basic"),
        ("replace the background", "inpaint-basic"),
    ],
)
def test_suggest_workflow_template_matches_common_intents(intent, expected_template_id):
    suggestion = suggest_workflow_template(intent)

    assert suggestion["id"] == expected_template_id


@pytest.mark.parametrize(
    ("intent", "expected_template_id"),
    [
        ("image to image with lora", "basic-image-to-image"),
        ("upscale this sdxl image", "upscale"),
    ],
)
def test_suggest_workflow_template_prefers_workflow_shape_over_model_modifier(
    intent,
    expected_template_id,
):
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


def test_build_template_plan_reports_missing_inpaint_mask():
    plan = build_template_plan(
        "inpaint masked area",
        "inpaint-basic",
        {"image": "input.png", "checkpoint_name": "model.safetensors"},
    )

    assert plan["template"]["id"] == "inpaint-basic"
    assert plan["parameters"]["grow_mask_by"] == 6
    assert "mask" in plan["missing_information"]
    assert "positive_prompt" in plan["missing_information"]


def test_build_template_plan_raises_for_unknown_template_id():
    with pytest.raises(ValueError):
        build_template_plan("make an image", "missing-template", {})


def test_build_template_plan_rejects_non_json_serializable_parameters():
    with pytest.raises(ValueError, match="parameters must be JSON serializable"):
        build_template_plan(
            "make an image from a prompt",
            "basic-text-to-image",
            {"checkpoint_name": Path("model.safetensors")},
        )
