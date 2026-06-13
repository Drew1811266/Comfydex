from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowTemplate:
    id: str
    name: str
    description: str
    required_nodes: list[str]
    nodes: list[dict[str, Any]]
    links: list[dict[str, Any]]
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
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        nodes=[
            {
                "key": "checkpoint",
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": {"parameter": "checkpoint_name"}},
            },
            {
                "key": "positive_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "positive_prompt"}},
            },
            {
                "key": "negative_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "negative_prompt"}},
            },
            {
                "key": "latent",
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": {"parameter": "width"},
                    "height": {"parameter": "height"},
                    "batch_size": {"value": 1},
                },
            },
            {
                "key": "sampler",
                "class_type": "KSampler",
                "inputs": {
                    "seed": {"parameter": "seed"},
                    "steps": {"parameter": "steps"},
                    "cfg": {"parameter": "cfg"},
                    "sampler_name": {"parameter": "sampler_name"},
                    "scheduler": {"parameter": "scheduler"},
                    "denoise": {"value": 1.0},
                },
            },
            {"key": "decode", "class_type": "VAEDecode", "inputs": {}},
            {
                "key": "save",
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": {"value": "Comfydex"}},
            },
        ],
        links=[
            {"from": "checkpoint", "output_slot": 0, "to": "sampler", "input": "model"},
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "positive_prompt",
                "input": "clip",
            },
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "negative_prompt",
                "input": "clip",
            },
            {
                "from": "positive_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "positive",
            },
            {
                "from": "negative_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "negative",
            },
            {
                "from": "latent",
                "output_slot": 0,
                "to": "sampler",
                "input": "latent_image",
            },
            {"from": "sampler", "output_slot": 0, "to": "decode", "input": "samples"},
            {"from": "checkpoint", "output_slot": 2, "to": "decode", "input": "vae"},
            {"from": "decode", "output_slot": 0, "to": "save", "input": "images"},
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
        nodes=[
            {
                "key": "load_image",
                "class_type": "LoadImage",
                "inputs": {"image": {"parameter": "image"}},
            },
            {
                "key": "checkpoint",
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": {"parameter": "checkpoint_name"}},
            },
            {
                "key": "positive_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "positive_prompt"}},
            },
            {
                "key": "negative_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "negative_prompt"}},
            },
            {"key": "encode", "class_type": "VAEEncode", "inputs": {}},
            {
                "key": "sampler",
                "class_type": "KSampler",
                "inputs": {
                    "seed": {"parameter": "seed"},
                    "steps": {"parameter": "steps"},
                    "cfg": {"parameter": "cfg"},
                    "sampler_name": {"parameter": "sampler_name"},
                    "scheduler": {"parameter": "scheduler"},
                    "denoise": {"parameter": "denoise"},
                },
            },
            {"key": "decode", "class_type": "VAEDecode", "inputs": {}},
            {
                "key": "save",
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": {"value": "Comfydex"}},
            },
        ],
        links=[
            {"from": "load_image", "output_slot": 0, "to": "encode", "input": "pixels"},
            {"from": "checkpoint", "output_slot": 2, "to": "encode", "input": "vae"},
            {"from": "checkpoint", "output_slot": 0, "to": "sampler", "input": "model"},
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "positive_prompt",
                "input": "clip",
            },
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "negative_prompt",
                "input": "clip",
            },
            {
                "from": "positive_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "positive",
            },
            {
                "from": "negative_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "negative",
            },
            {
                "from": "encode",
                "output_slot": 0,
                "to": "sampler",
                "input": "latent_image",
            },
            {"from": "sampler", "output_slot": 0, "to": "decode", "input": "samples"},
            {"from": "checkpoint", "output_slot": 2, "to": "decode", "input": "vae"},
            {"from": "decode", "output_slot": 0, "to": "save", "input": "images"},
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
        nodes=[
            {
                "key": "load_image",
                "class_type": "LoadImage",
                "inputs": {"image": {"parameter": "image"}},
            },
            {
                "key": "upscale_model",
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": {"parameter": "upscale_model_name"}},
            },
            {"key": "upscale", "class_type": "ImageUpscaleWithModel", "inputs": {}},
            {
                "key": "save",
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": {"parameter": "output_prefix"}},
            },
        ],
        links=[
            {"from": "load_image", "output_slot": 0, "to": "upscale", "input": "image"},
            {
                "from": "upscale_model",
                "output_slot": 0,
                "to": "upscale",
                "input": "upscale_model",
            },
            {"from": "upscale", "output_slot": 0, "to": "save", "input": "images"},
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
        nodes=[
            {
                "key": "checkpoint",
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": {"parameter": "checkpoint_name"}},
            },
            {
                "key": "positive_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "positive_prompt"}},
            },
            {
                "key": "negative_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "negative_prompt"}},
            },
            {
                "key": "latent",
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": {"parameter": "width"},
                    "height": {"parameter": "height"},
                    "batch_size": {"value": 1},
                },
            },
            {
                "key": "sampler",
                "class_type": "KSampler",
                "inputs": {
                    "seed": {"parameter": "seed"},
                    "steps": {"parameter": "steps"},
                    "cfg": {"parameter": "cfg"},
                    "sampler_name": {"parameter": "sampler_name"},
                    "scheduler": {"parameter": "scheduler"},
                    "denoise": {"value": 1.0},
                },
            },
            {"key": "decode", "class_type": "VAEDecode", "inputs": {}},
            {
                "key": "save",
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": {"value": "Comfydex"}},
            },
        ],
        links=[
            {"from": "checkpoint", "output_slot": 0, "to": "sampler", "input": "model"},
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "positive_prompt",
                "input": "clip",
            },
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "negative_prompt",
                "input": "clip",
            },
            {
                "from": "positive_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "positive",
            },
            {
                "from": "negative_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "negative",
            },
            {
                "from": "latent",
                "output_slot": 0,
                "to": "sampler",
                "input": "latent_image",
            },
            {"from": "sampler", "output_slot": 0, "to": "decode", "input": "samples"},
            {"from": "checkpoint", "output_slot": 2, "to": "decode", "input": "vae"},
            {"from": "decode", "output_slot": 0, "to": "save", "input": "images"},
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
        nodes=[
            {
                "key": "checkpoint",
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": {"parameter": "checkpoint_name"}},
            },
            {
                "key": "lora",
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": {"parameter": "lora_name"},
                    "strength_model": {"parameter": "strength_model"},
                    "strength_clip": {"parameter": "strength_clip"},
                },
            },
            {
                "key": "positive_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "positive_prompt"}},
            },
            {
                "key": "negative_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "negative_prompt"}},
            },
            {
                "key": "latent",
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": {"parameter": "width"},
                    "height": {"parameter": "height"},
                    "batch_size": {"value": 1},
                },
            },
            {
                "key": "sampler",
                "class_type": "KSampler",
                "inputs": {
                    "seed": {"parameter": "seed"},
                    "steps": {"parameter": "steps"},
                    "cfg": {"parameter": "cfg"},
                    "sampler_name": {"parameter": "sampler_name"},
                    "scheduler": {"parameter": "scheduler"},
                    "denoise": {"value": 1.0},
                },
            },
            {"key": "decode", "class_type": "VAEDecode", "inputs": {}},
            {
                "key": "save",
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": {"value": "Comfydex"}},
            },
        ],
        links=[
            {"from": "checkpoint", "output_slot": 0, "to": "lora", "input": "model"},
            {"from": "checkpoint", "output_slot": 1, "to": "lora", "input": "clip"},
            {"from": "lora", "output_slot": 0, "to": "sampler", "input": "model"},
            {
                "from": "lora",
                "output_slot": 1,
                "to": "positive_prompt",
                "input": "clip",
            },
            {
                "from": "lora",
                "output_slot": 1,
                "to": "negative_prompt",
                "input": "clip",
            },
            {
                "from": "positive_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "positive",
            },
            {
                "from": "negative_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "negative",
            },
            {
                "from": "latent",
                "output_slot": 0,
                "to": "sampler",
                "input": "latent_image",
            },
            {"from": "sampler", "output_slot": 0, "to": "decode", "input": "samples"},
            {"from": "checkpoint", "output_slot": 2, "to": "decode", "input": "vae"},
            {"from": "decode", "output_slot": 0, "to": "save", "input": "images"},
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
        id="inpaint-basic",
        name="Basic Inpaint",
        description="A mask-driven inpaint recipe that loads an image and mask, encodes them for inpainting, samples the edited latent, and saves the result.",
        required_nodes=[
            "LoadImage",
            "LoadImageMask",
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "VAEEncodeForInpaint",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        nodes=[
            {
                "key": "load_image",
                "class_type": "LoadImage",
                "inputs": {"image": {"parameter": "image"}},
            },
            {
                "key": "mask_image",
                "class_type": "LoadImageMask",
                "inputs": {
                    "image": {"parameter": "mask"},
                    "channel": {"parameter": "mask_channel"},
                },
            },
            {
                "key": "checkpoint",
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": {"parameter": "checkpoint_name"}},
            },
            {
                "key": "positive_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "positive_prompt"}},
            },
            {
                "key": "negative_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "negative_prompt"}},
            },
            {
                "key": "encode_inpaint",
                "class_type": "VAEEncodeForInpaint",
                "inputs": {"grow_mask_by": {"parameter": "grow_mask_by"}},
            },
            {
                "key": "sampler",
                "class_type": "KSampler",
                "inputs": {
                    "seed": {"parameter": "seed"},
                    "steps": {"parameter": "steps"},
                    "cfg": {"parameter": "cfg"},
                    "sampler_name": {"parameter": "sampler_name"},
                    "scheduler": {"parameter": "scheduler"},
                    "denoise": {"parameter": "denoise"},
                },
            },
            {"key": "decode", "class_type": "VAEDecode", "inputs": {}},
            {
                "key": "save",
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": {"value": "Comfydex_inpaint"}},
            },
        ],
        links=[
            {
                "from": "load_image",
                "output_slot": 0,
                "to": "encode_inpaint",
                "input": "pixels",
            },
            {
                "from": "mask_image",
                "output_slot": 0,
                "to": "encode_inpaint",
                "input": "mask",
            },
            {
                "from": "checkpoint",
                "output_slot": 2,
                "to": "encode_inpaint",
                "input": "vae",
            },
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "positive_prompt",
                "input": "clip",
            },
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "negative_prompt",
                "input": "clip",
            },
            {
                "from": "positive_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "positive",
            },
            {
                "from": "negative_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "negative",
            },
            {"from": "checkpoint", "output_slot": 0, "to": "sampler", "input": "model"},
            {
                "from": "encode_inpaint",
                "output_slot": 0,
                "to": "sampler",
                "input": "latent_image",
            },
            {"from": "sampler", "output_slot": 0, "to": "decode", "input": "samples"},
            {"from": "checkpoint", "output_slot": 2, "to": "decode", "input": "vae"},
            {"from": "decode", "output_slot": 0, "to": "save", "input": "images"},
        ],
        parameters={
            "steps": 20,
            "cfg": 7.0,
            "denoise": 1.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": -1,
            "negative_prompt": "",
            "mask_channel": "alpha",
            "grow_mask_by": 6,
        },
        required_inputs=["image", "mask", "checkpoint_name", "positive_prompt"],
        assumptions=[
            "The source image and mask are available to ComfyUI.",
            "The mask clearly identifies the editable region.",
        ],
        tags=["inpaint", "inpainting", "mask", "masked", "background", "edit"],
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
        nodes=[
            {
                "key": "pose_image",
                "class_type": "LoadImage",
                "inputs": {"image": {"parameter": "pose_image"}},
            },
            {
                "key": "checkpoint",
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": {"parameter": "checkpoint_name"}},
            },
            {
                "key": "controlnet",
                "class_type": "ControlNetLoader",
                "inputs": {"control_net_name": {"parameter": "controlnet_name"}},
            },
            {
                "key": "positive_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "positive_prompt"}},
            },
            {
                "key": "negative_prompt",
                "class_type": "CLIPTextEncode",
                "inputs": {"text": {"parameter": "negative_prompt"}},
            },
            {
                "key": "apply_controlnet",
                "class_type": "ControlNetApply",
                "inputs": {"strength": {"parameter": "control_strength"}},
            },
            {
                "key": "latent",
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": {"parameter": "width"},
                    "height": {"parameter": "height"},
                    "batch_size": {"value": 1},
                },
            },
            {
                "key": "sampler",
                "class_type": "KSampler",
                "inputs": {
                    "seed": {"parameter": "seed"},
                    "steps": {"parameter": "steps"},
                    "cfg": {"parameter": "cfg"},
                    "sampler_name": {"parameter": "sampler_name"},
                    "scheduler": {"parameter": "scheduler"},
                    "denoise": {"value": 1.0},
                },
            },
            {"key": "decode", "class_type": "VAEDecode", "inputs": {}},
            {
                "key": "save",
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": {"value": "Comfydex"}},
            },
        ],
        links=[
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "positive_prompt",
                "input": "clip",
            },
            {
                "from": "checkpoint",
                "output_slot": 1,
                "to": "negative_prompt",
                "input": "clip",
            },
            {
                "from": "positive_prompt",
                "output_slot": 0,
                "to": "apply_controlnet",
                "input": "conditioning",
            },
            {
                "from": "controlnet",
                "output_slot": 0,
                "to": "apply_controlnet",
                "input": "control_net",
            },
            {
                "from": "pose_image",
                "output_slot": 0,
                "to": "apply_controlnet",
                "input": "image",
            },
            {
                "from": "apply_controlnet",
                "output_slot": 0,
                "to": "sampler",
                "input": "positive",
            },
            {
                "from": "negative_prompt",
                "output_slot": 0,
                "to": "sampler",
                "input": "negative",
            },
            {"from": "checkpoint", "output_slot": 0, "to": "sampler", "input": "model"},
            {
                "from": "latent",
                "output_slot": 0,
                "to": "sampler",
                "input": "latent_image",
            },
            {"from": "sampler", "output_slot": 0, "to": "decode", "input": "samples"},
            {"from": "checkpoint", "output_slot": 2, "to": "decode", "input": "vae"},
            {"from": "decode", "output_slot": 0, "to": "save", "input": "images"},
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
    (
        "inpaint-basic",
        (
            "inpaint",
            "inpainting",
            "mask",
            "masked",
            "replace background",
            "replace the background",
            "background replacement",
        ),
    ),
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
    _require_json_serializable(user_parameters)
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


def _require_json_serializable(value: Any) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("parameters must be JSON serializable") from exc
