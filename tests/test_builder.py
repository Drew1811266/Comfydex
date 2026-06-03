import pytest

from comfydex_mcp.builder import (
    build_workflow_from_template,
    validate_workflow_against_object_info,
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

IMAGE_TO_IMAGE_OBJECT_INFO = {
    **TEXT_TO_IMAGE_OBJECT_INFO,
    "LoadImage": {
        "input": {"required": {"image": ("STRING",)}},
        "output": ["IMAGE", "MASK"],
    },
    "VAEEncode": {
        "input": {"required": {"pixels": ("IMAGE",), "vae": ("VAE",)}},
        "output": ["LATENT"],
    },
}


def test_build_basic_text_to_image_returns_valid_submit_ready_workflow():
    result = build_workflow_from_template(
        "basic-text-to-image",
        {
            "checkpoint_name": "dream.safetensors",
            "positive_prompt": "a quiet studio",
        },
        TEXT_TO_IMAGE_OBJECT_INFO,
    )

    assert result["status"] == "valid"
    assert result["submit_ready"] is True
    assert isinstance(result["workflow"], dict)
    assert result["validation"]["status"] == "valid"
    assert any(
        node["class_type"] == "SaveImage" for node in result["workflow"].values()
    )


def test_build_basic_image_to_image_returns_valid_submit_ready_workflow():
    result = build_workflow_from_template(
        "basic-image-to-image",
        {
            "image": "input.png",
            "checkpoint_name": "dream.safetensors",
            "positive_prompt": "make it cinematic",
        },
        IMAGE_TO_IMAGE_OBJECT_INFO,
    )

    assert result["status"] == "valid"
    assert result["submit_ready"] is True
    assert isinstance(result["workflow"], dict)
    assert result["validation"]["status"] == "valid"
    assert any(
        node["class_type"] == "LoadImage" for node in result["workflow"].values()
    )
    assert any(
        node["class_type"] == "VAEEncode" for node in result["workflow"].values()
    )


def test_build_missing_required_parameter_does_not_claim_submit_ready():
    result = build_workflow_from_template(
        "basic-text-to-image",
        {"positive_prompt": "a quiet studio"},
        TEXT_TO_IMAGE_OBJECT_INFO,
    )

    assert result["status"] == "missing_information"
    assert result["submit_ready"] is False
    assert result["workflow"] is None
    assert "checkpoint_name" in result["missing_information"]


def test_build_missing_required_object_info_does_not_claim_submit_ready():
    object_info = dict(TEXT_TO_IMAGE_OBJECT_INFO)
    object_info.pop("KSampler")

    result = build_workflow_from_template(
        "basic-text-to-image",
        {
            "checkpoint_name": "dream.safetensors",
            "positive_prompt": "a quiet studio",
        },
        object_info,
    )

    assert result["status"] != "valid"
    assert result["submit_ready"] is False
    assert result["workflow"] is None
    assert result["gaps"] == [
        {"class_type": "KSampler", "reason": "missing_object_info"}
    ]


def test_build_writes_user_parameters_to_expected_node_inputs():
    result = build_workflow_from_template(
        "basic-text-to-image",
        {
            "checkpoint_name": "dream.safetensors",
            "positive_prompt": "a bright alpine lake",
            "width": 768,
            "height": 512,
            "seed": 12345,
        },
        TEXT_TO_IMAGE_OBJECT_INFO,
    )
    workflow = result["workflow"]

    positive_node = next(
        node
        for node in workflow.values()
        if node["class_type"] == "CLIPTextEncode"
        and node["inputs"]["text"] == "a bright alpine lake"
    )
    latent_node = next(
        node for node in workflow.values() if node["class_type"] == "EmptyLatentImage"
    )
    sampler_node = next(
        node for node in workflow.values() if node["class_type"] == "KSampler"
    )

    assert positive_node["inputs"]["text"] == "a bright alpine lake"
    assert latent_node["inputs"]["width"] == 768
    assert latent_node["inputs"]["height"] == 512
    assert sampler_node["inputs"]["seed"] == 12345


def test_build_invalid_widget_parameter_type_does_not_claim_submit_ready():
    result = build_workflow_from_template(
        "basic-text-to-image",
        {
            "checkpoint_name": "dream.safetensors",
            "positive_prompt": "a quiet studio",
            "width": "wide",
        },
        TEXT_TO_IMAGE_OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["submit_ready"] is False
    assert result["workflow"] is None
    assert result["draft_workflow"]["4"]["inputs"]["width"] == "wide"
    assert any(
        error["reason"] == "invalid_input_value" and error["input"] == "width"
        for error in result["validation"]["errors"]
    )


def test_validate_workflow_against_object_info_wraps_validation_report():
    workflow = {
        "1": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "Comfydex"},
        },
        "2": {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0], "vae": ["2", 0]}},
    }

    report = validate_workflow_against_object_info(workflow, TEXT_TO_IMAGE_OBJECT_INFO)

    assert report["status"] == "invalid"


def test_build_raises_for_unsupported_template_id():
    with pytest.raises(ValueError):
        build_workflow_from_template(
            "unsupported-template",
            {"checkpoint_name": "dream.safetensors"},
            TEXT_TO_IMAGE_OBJECT_INFO,
        )
