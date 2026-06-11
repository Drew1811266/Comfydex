from comfydex_mcp.generation import (
    DEFAULT_CONSTRAINTS,
    build_generated_workflow,
    candidate_templates,
    evaluate_submit_policy,
    normalize_constraints,
    plan_workflow_generation,
)


TEXT_TO_IMAGE_OBJECT_INFO = {
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": ("STRING",)}},
        "output": ["MODEL", "CLIP", "VAE"],
    },
    "CLIPTextEncode": {
        "input": {"required": {"text": ("STRING",), "clip": ("CLIP",)}},
        "output": ["CONDITIONING"],
    },
    "EmptyLatentImage": {
        "input": {
            "required": {
                "width": ("INT",),
                "height": ("INT",),
                "batch_size": ("INT",),
            }
        },
        "output": ["LATENT"],
    },
    "KSampler": {
        "input": {
            "required": {
                "model": ("MODEL",),
                "seed": ("INT",),
                "steps": ("INT",),
                "cfg": ("FLOAT",),
                "sampler_name": ("STRING",),
                "scheduler": ("STRING",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "denoise": ("FLOAT",),
            }
        },
        "output": ["LATENT"],
    },
    "VAEDecode": {
        "input": {"required": {"samples": ("LATENT",), "vae": ("VAE",)}},
        "output": ["IMAGE"],
    },
    "SaveImage": {
        "input": {
            "required": {"images": ("IMAGE",), "filename_prefix": ("STRING",)}
        },
        "output": [],
    },
}


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


def test_plan_workflow_generation_includes_semantic_coverage():
    plan = plan_workflow_generation(
        "make a text to image workflow",
        parameters={
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "a studio portrait",
        },
    )

    semantic = plan["semantic_coverage"]
    assert "CheckpointLoaderSimple" in semantic["supported_node_types"]
    assert "KSampler" in semantic["supported_node_types"]
    assert semantic["unsupported_node_types"] == []
    assert semantic["status"] == "supported"


def test_plan_workflow_generation_includes_recipe_context():
    plan = plan_workflow_generation(
        "use a lora style for a portrait",
        {
            "lora_name": "style.safetensors",
            "checkpoint_name": "sdxl.safetensors",
            "positive_prompt": "portrait",
        },
    )

    assert plan["selected_recipe_id"] == "text-to-image-lora"
    assert plan["recipe_candidates"][0]["recipe_id"] == "text-to-image-lora"
    assert plan["selected_template_id"] == "lora-text-to-image"


def test_candidate_templates_keeps_explicit_template_id_authoritative():
    candidates = candidate_templates(
        "upscale this image",
        {"image": "input.png"},
        template_id="basic-text-to-image",
    )

    assert candidates == [
        {
            "template_id": "basic-text-to-image",
            "score": 1000,
            "reasons": ["explicit template_id"],
        }
    ]


def test_plan_workflow_generation_reports_unsupported_template_nodes(monkeypatch):
    monkeypatch.setattr(
        "comfydex_mcp.generation.get_node_semantics",
        lambda node_type: None if node_type == "KSampler" else {"node_type": node_type},
    )

    plan = plan_workflow_generation(
        "make a text to image workflow",
        parameters={
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "a studio portrait",
        },
    )

    assert "KSampler" in plan["semantic_coverage"]["unsupported_node_types"]
    assert plan["semantic_coverage"]["status"] == "partial"


def test_normalize_constraints_uses_safe_defaults():
    assert normalize_constraints({}) == DEFAULT_CONSTRAINTS


def test_normalize_constraints_parses_string_booleans_safely():
    constraints = normalize_constraints(
        {"allow_overwrite": "false", "allow_batch": "true"}
    )

    assert constraints["allow_overwrite"] is False
    assert constraints["allow_batch"] is True


def test_build_generated_workflow_clamps_repairable_steps():
    plan = plan_workflow_generation(
        "text to image",
        parameters={
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "cat",
            "steps": 150,
        },
    )

    result = build_generated_workflow(plan, TEXT_TO_IMAGE_OBJECT_INFO)

    assert result["status"] == "valid"
    assert result["workflow"] is not None
    assert result["repairs"][0]["kind"] == "clamped_steps"
    assert result["repairs"][0]["after"] == 60
    assert result["policy"]["decision"] == "allowed"


def test_build_generated_workflow_blocks_too_many_pixels():
    plan = plan_workflow_generation(
        "text to image",
        parameters={
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "cat",
            "width": 2048,
            "height": 2048,
        },
    )

    result = build_generated_workflow(plan, TEXT_TO_IMAGE_OBJECT_INFO)

    assert result["status"] == "blocked"
    assert result["submit_ready"] is False
    assert result["policy"]["decision"] == "blocked"
    assert "pixel_count_exceeds_limit" in result["policy"]["reasons"]


def test_evaluate_submit_policy_requires_confirmation_for_overwrite():
    policy = evaluate_submit_policy(
        validation={"status": "valid", "errors": [], "warnings": []},
        submit_ready=True,
        constraints={
            "allow_overwrite": False,
            "allow_batch": False,
            "max_steps": 60,
            "max_pixels": 1048576,
        },
        target_exists=True,
    )

    assert policy["decision"] == "requires_confirmation"
    assert policy["requires_confirmation"] is True
    assert "workflow_overwrite" in policy["reasons"]


def test_evaluate_submit_policy_requires_confirmation_for_unknown_validation():
    policy = evaluate_submit_policy(
        validation={"status": "valid", "errors": [], "warnings": []},
        submit_ready=True,
        constraints={},
        issues=["object_info_unavailable"],
    )

    assert policy["decision"] == "requires_confirmation"
    assert policy["requires_confirmation"] is True
    assert policy["risk_level"] == "medium"
    assert "object_info_unavailable" in policy["reasons"]


def test_evaluate_submit_policy_blocks_invalid_even_with_unknown_validation():
    policy = evaluate_submit_policy(
        validation={
            "status": "invalid",
            "errors": [{"reason": "bad"}],
            "warnings": [],
        },
        submit_ready=False,
        constraints={},
        issues=["object_info_unavailable"],
    )

    assert policy["decision"] == "blocked"
    assert policy["blocked"] is True
    assert "validation_not_submit_ready" in policy["reasons"]
