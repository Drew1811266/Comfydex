from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .templates import get_workflow_template


@dataclass(frozen=True)
class WorkflowRecipe:
    recipe_id: str
    name: str
    description: str
    template_id: str
    intent_phrases: list[str]
    tags: list[str]
    required_nodes: list[str]
    required_model_types: list[str]
    required_inputs: list[str]
    optional_inputs: list[str]
    safety_notes: list[str]
    examples: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_RECIPES: tuple[WorkflowRecipe, ...] = (
    WorkflowRecipe(
        recipe_id="text-to-image-basic",
        name="Basic Text To Image",
        description="Generate an image from a prompt with a checkpoint, sampler, VAE decode, and save node.",
        template_id="basic-text-to-image",
        intent_phrases=["text to image", "text-to-image", "txt2img", "prompt image"],
        tags=["text-to-image", "txt2img", "basic", "prompt", "image"],
        required_nodes=[
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_model_types=["checkpoint"],
        required_inputs=["checkpoint_name", "positive_prompt"],
        optional_inputs=["negative_prompt", "width", "height", "steps", "cfg", "seed"],
        safety_notes=["Requires a compatible checkpoint model."],
        examples=["text to image of a small cabin beside a lake"],
    ),
    WorkflowRecipe(
        recipe_id="text-to-image-sdxl",
        name="SDXL Text To Image",
        description="Generate an image from a prompt using an SDXL-oriented text-to-image template.",
        template_id="sdxl-text-to-image",
        intent_phrases=["sdxl text to image", "sdxl prompt", "xl text to image"],
        tags=["text-to-image", "txt2img", "sdxl", "xl", "prompt"],
        required_nodes=[
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_model_types=["checkpoint"],
        required_inputs=["checkpoint_name", "positive_prompt"],
        optional_inputs=["negative_prompt", "width", "height", "steps", "cfg", "seed"],
        safety_notes=["Requires an SDXL-compatible checkpoint."],
        examples=["sdxl cinematic landscape"],
    ),
    WorkflowRecipe(
        recipe_id="text-to-image-lora",
        name="LoRA Text To Image",
        description="Generate an image from a prompt while applying a LoRA style or subject adapter.",
        template_id="lora-text-to-image",
        intent_phrases=["lora text to image", "lora style", "use lora", "with lora"],
        tags=["text-to-image", "txt2img", "lora", "style", "adapter"],
        required_nodes=[
            "CheckpointLoaderSimple",
            "LoraLoader",
            "CLIPTextEncode",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_model_types=["checkpoint", "lora"],
        required_inputs=["checkpoint_name", "lora_name", "positive_prompt"],
        optional_inputs=[
            "negative_prompt",
            "strength_model",
            "strength_clip",
            "width",
            "height",
            "steps",
            "cfg",
            "seed",
        ],
        safety_notes=["Requires a checkpoint and a compatible LoRA model."],
        examples=["make a portrait with a lora style"],
    ),
    WorkflowRecipe(
        recipe_id="image-to-image-basic",
        name="Basic Image To Image",
        description="Create an image variation from a source image, prompt, checkpoint, and denoise value.",
        template_id="basic-image-to-image",
        intent_phrases=["image to image", "image-to-image", "img2img", "variation"],
        tags=["image-to-image", "img2img", "variation", "denoise", "image"],
        required_nodes=[
            "LoadImage",
            "CheckpointLoaderSimple",
            "CLIPTextEncode",
            "VAEEncode",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_model_types=["checkpoint"],
        required_inputs=["image", "checkpoint_name", "positive_prompt"],
        optional_inputs=["negative_prompt", "denoise", "steps", "cfg", "seed"],
        safety_notes=["Requires a source image already available to ComfyUI."],
        examples=["image to image variation of input.png"],
    ),
    WorkflowRecipe(
        recipe_id="image-upscale",
        name="Image Upscale",
        description="Upscale an input image with an upscale model and save the result.",
        template_id="upscale",
        intent_phrases=["upscale image", "image upscale", "upscaler", "enlarge image"],
        tags=["upscale", "upscaler", "enlarge", "enhance", "image"],
        required_nodes=["LoadImage", "UpscaleModelLoader", "ImageUpscaleWithModel", "SaveImage"],
        required_model_types=["upscale"],
        required_inputs=["image", "upscale_model_name"],
        optional_inputs=["output_prefix"],
        safety_notes=["Requires an upscale model file."],
        examples=["upscale this image with 4x model"],
    ),
    WorkflowRecipe(
        recipe_id="controlnet-pose",
        name="ControlNet Pose",
        description="Generate an image guided by a pose or skeleton image through ControlNet.",
        template_id="controlnet-skeleton",
        intent_phrases=[
            "controlnet pose",
            "pose controlnet",
            "skeleton controlnet",
            "openpose",
        ],
        tags=["controlnet", "pose", "skeleton", "openpose", "guided"],
        required_nodes=[
            "CheckpointLoaderSimple",
            "ControlNetLoader",
            "ControlNetApply",
            "CLIPTextEncode",
            "LoadImage",
            "EmptyLatentImage",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        ],
        required_model_types=["checkpoint", "controlnet"],
        required_inputs=["checkpoint_name", "controlnet_name", "pose_image", "positive_prompt"],
        optional_inputs=["negative_prompt", "control_strength", "width", "height", "steps", "cfg", "seed"],
        safety_notes=["Requires a pose image and compatible ControlNet model."],
        examples=["controlnet pose image for a dancer"],
    ),
)


def list_workflow_recipes() -> list[dict[str, Any]]:
    return [recipe.to_dict() for recipe in _RECIPES]


def get_workflow_recipe(recipe_id: str) -> dict[str, Any] | None:
    for recipe in _RECIPES:
        if recipe.recipe_id == recipe_id:
            return recipe.to_dict()
    return None


def search_workflow_recipes(query: str) -> list[dict[str, Any]]:
    normalized_query = " ".join(query.casefold().split())
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for recipe in _RECIPES:
        score = _search_score(recipe, normalized_query)
        if score > 0:
            scored.append((score, recipe.recipe_id, recipe.to_dict()))
    return [
        recipe
        for _score, _recipe_id, recipe in sorted(
            scored,
            key=lambda item: (-item[0], item[1]),
        )
    ]


def validate_workflow_recipes() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for recipe in _RECIPES:
        if recipe.recipe_id in seen_ids:
            errors.append({"recipe_id": recipe.recipe_id, "reason": "duplicate_recipe_id"})
        seen_ids.add(recipe.recipe_id)
        if not recipe.required_nodes:
            errors.append({"recipe_id": recipe.recipe_id, "reason": "missing_required_nodes"})
        if not recipe.required_inputs:
            errors.append({"recipe_id": recipe.recipe_id, "reason": "missing_required_inputs"})
        try:
            get_workflow_template(recipe.template_id)
        except KeyError:
            errors.append({"recipe_id": recipe.recipe_id, "reason": "missing_template"})

    return {
        "status": "valid" if not errors else "invalid",
        "recipe_count": len(_RECIPES),
        "errors": errors,
    }


def _search_score(recipe: WorkflowRecipe, query: str) -> int:
    if not query:
        return 0
    haystacks = [
        recipe.recipe_id,
        recipe.name,
        recipe.description,
        *recipe.intent_phrases,
        *recipe.tags,
        *recipe.required_nodes,
        *recipe.required_model_types,
        *recipe.required_inputs,
    ]
    score = 0
    query_terms = set(query.split())
    for value in haystacks:
        normalized = value.casefold()
        if query in normalized:
            score += 50
        score += 8 * len(query_terms & set(normalized.replace("-", " ").split()))
    return score
