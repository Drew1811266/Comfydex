from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowTemplate:
    id: str
    name: str
    description: str
    required_nodes: list[str]
    parameters: dict[str, Any]
    required_inputs: list[str]
    assumptions: list[str]
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TEMPLATES: tuple[WorkflowTemplate, ...] = (
    WorkflowTemplate(
        id="basic-text-to-image",
        name="Basic Text To Image",
        description="A minimal text-to-image recipe using a checkpoint, prompt encoders, sampler, VAE decode, and image save.",
        required_nodes=[
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        parameters={
            "width": 512,
            "height": 512,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": -1,
            "negative_prompt": "",
        },
        required_inputs=["checkpoint_name", "positive_prompt"],
        assumptions=[
            "A compatible checkpoint is available in ComfyUI.",
            "The default latent size is 512x512 unless overridden.",
        ],
        tags=["text-to-image", "txt2img", "basic", "prompt"],
    ),
    WorkflowTemplate(
        id="basic-image-to-image",
        name="Basic Image To Image",
        description="A basic image-to-image variation recipe that loads an input image, encodes it, samples with denoise, and saves the result.",
        required_nodes=[
            "LoadImage",
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "VAEEncode",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        parameters={
            "steps": 20,
            "cfg": 7.0,
            "denoise": 0.55,
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": -1,
            "negative_prompt": "",
        },
        required_inputs=["image", "checkpoint_name", "positive_prompt"],
        assumptions=[
            "The source image is already available to ComfyUI or can be referenced by the caller.",
            "Denoise defaults to a moderate variation strength.",
        ],
        tags=["image-to-image", "img2img", "variation", "basic"],
    ),
    WorkflowTemplate(
        id="upscale",
        name="Upscale",
        description="An image upscaling recipe using an upscale model and saving the upscaled image.",
        required_nodes=[
            "LoadImage",
            "UpscaleModelLoader",
            "ImageUpscaleWithModel",
            "SaveImage",
        ],
        parameters={
            "upscale_model_name": None,
            "output_prefix": "Comfydex_upscale",
        },
        required_inputs=["image", "upscale_model_name"],
        assumptions=[
            "An upscale model is installed in the ComfyUI models directory.",
            "The input image is available to ComfyUI.",
        ],
        tags=["upscale", "image", "enhance"],
    ),
    WorkflowTemplate(
        id="sdxl-text-to-image",
        name="SDXL Text To Image",
        description="An SDXL text-to-image recipe with base dimensions and prompt encoding suitable for SDXL checkpoints.",
        required_nodes=[
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        parameters={
            "width": 1024,
            "height": 1024,
            "steps": 30,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": -1,
            "negative_prompt": "",
        },
        required_inputs=["checkpoint_name", "positive_prompt"],
        assumptions=[
            "The selected checkpoint is an SDXL-compatible model.",
            "The default latent size is 1024x1024 unless overridden.",
        ],
        tags=["sdxl", "text-to-image", "txt2img", "prompt"],
    ),
    WorkflowTemplate(
        id="lora-text-to-image",
        name="LoRA Text To Image",
        description="A text-to-image recipe that applies a LoRA to the checkpoint model and CLIP before sampling.",
        required_nodes=[
            "CheckpointLoaderSimple",
            "LoraLoader",
            "CLIPTextEncode",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        parameters={
            "width": 512,
            "height": 512,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": -1,
            "negative_prompt": "",
            "strength_model": 0.8,
            "strength_clip": 0.8,
        },
        required_inputs=["checkpoint_name", "lora_name", "positive_prompt"],
        assumptions=[
            "The LoRA is compatible with the selected checkpoint family.",
            "LoRA model and CLIP strengths default to 0.8.",
        ],
        tags=["lora", "text-to-image", "txt2img", "prompt"],
    ),
    WorkflowTemplate(
        id="controlnet-skeleton",
        name="ControlNet Skeleton",
        description="A ControlNet pose skeleton recipe that conditions generation on a pose or skeleton image.",
        required_nodes=[
            "LoadImage",
            "CheckpointLoaderSimple",
            "ControlNetLoader",
            "CLIPTextEncode",
            "ControlNetApply",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        parameters={
            "width": 512,
            "height": 512,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": -1,
            "negative_prompt": "",
            "control_strength": 1.0,
        },
        required_inputs=[
            "checkpoint_name",
            "controlnet_name",
            "pose_image",
            "positive_prompt",
        ],
        assumptions=[
            "A pose-compatible ControlNet model is installed.",
            "The pose image already represents the desired skeleton or conditioning map.",
        ],
        tags=["controlnet", "pose", "skeleton", "text-to-image"],
    ),
)


_TEMPLATES_BY_ID = {template.id: template for template in _TEMPLATES}

_INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("controlnet-skeleton", ("controlnet", "pose", "skeleton", "openpose")),
    ("upscale", ("upscale", "upscaler", "enlarge", "enhance")),
    ("basic-image-to-image", ("image to image", "image-to-image", "img2img", "variation")),
    ("lora-text-to-image", ("lora", "loras")),
    ("sdxl-text-to-image", ("sdxl", "xl")),
    ("basic-text-to-image", ("text to image", "text-to-image", "txt2img", "prompt")),
)


def list_workflow_templates() -> list[dict[str, Any]]:
    return [template.to_dict() for template in _TEMPLATES]


def get_workflow_template(template_id: str) -> dict[str, Any]:
    try:
        return _TEMPLATES_BY_ID[template_id].to_dict()
    except KeyError as exc:
        raise ValueError(f"Unknown workflow template: {template_id}") from exc


def suggest_workflow_template(intent: str) -> dict[str, Any]:
    normalized_intent = intent.casefold()
    for template_id, keywords in _INTENT_KEYWORDS:
        if any(keyword in normalized_intent for keyword in keywords):
            return get_workflow_template(template_id)
    return get_workflow_template("basic-text-to-image")


def build_template_plan(
    intent: str,
    template_id: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template = (
        get_workflow_template(template_id)
        if template_id is not None
        else suggest_workflow_template(intent)
    )
    user_parameters = parameters or {}
    merged_parameters = {
        **deepcopy(template["parameters"]),
        **deepcopy(user_parameters),
    }
    missing_information = [
        input_name
        for input_name in template["required_inputs"]
        if not _has_parameter_value(merged_parameters, input_name)
    ]

    return {
        "intent": intent,
        "template": template,
        "required_nodes": deepcopy(template["required_nodes"]),
        "parameters": merged_parameters,
        "assumptions": deepcopy(template["assumptions"]),
        "missing_information": missing_information,
    }


def explain_workflow_plan(plan: dict[str, Any]) -> dict[str, Any]:
    template = plan.get("template", {})
    return {
        "selected_template": {
            "id": template.get("id"),
            "name": template.get("name"),
            "description": template.get("description"),
        },
        "required_nodes": deepcopy(plan.get("required_nodes", [])),
        "missing_information": deepcopy(plan.get("missing_information", [])),
        "assumptions": deepcopy(plan.get("assumptions", [])),
    }


def _has_parameter_value(parameters: dict[str, Any], name: str) -> bool:
    if name not in parameters:
        return False
    value = parameters[name]
    return value is not None and value != ""
