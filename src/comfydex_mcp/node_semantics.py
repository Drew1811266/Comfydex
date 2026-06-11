from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NodePortSemantic:
    name: str
    meaning: str
    data_type: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "meaning": self.meaning,
            "data_type": self.data_type,
            "required": self.required,
        }


@dataclass(frozen=True)
class NodeSemanticEntry:
    node_type: str
    display_names: tuple[str, ...]
    category: str
    purpose: str
    inputs: tuple[NodePortSemantic, ...]
    outputs: tuple[NodePortSemantic, ...]
    parameter_strategies: tuple[str, ...]
    compatible_upstream: tuple[str, ...]
    compatible_downstream: tuple[str, ...]
    failure_modes: tuple[str, ...]
    repair_hints: tuple[str, ...]
    safe_for_user: bool
    requires_external_models: bool
    custom_node_package: str | None = None
    first_class: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": self.node_type,
            "display_names": list(self.display_names),
            "category": self.category,
            "purpose": self.purpose,
            "inputs": [port.to_dict() for port in self.inputs],
            "outputs": [port.to_dict() for port in self.outputs],
            "parameter_strategies": list(self.parameter_strategies),
            "compatible_upstream": list(self.compatible_upstream),
            "compatible_downstream": list(self.compatible_downstream),
            "failure_modes": list(self.failure_modes),
            "repair_hints": list(self.repair_hints),
            "safe_for_user": self.safe_for_user,
            "requires_external_models": self.requires_external_models,
            "custom_node_package": self.custom_node_package,
            "first_class": self.first_class,
        }


def _port(
    name: str,
    meaning: str,
    data_type: str,
    required: bool = True,
) -> NodePortSemantic:
    return NodePortSemantic(
        name=name,
        meaning=meaning,
        data_type=data_type,
        required=required,
    )


def _entry(
    node_type: str,
    *,
    display_names: tuple[str, ...],
    category: str,
    purpose: str,
    inputs: tuple[NodePortSemantic, ...],
    outputs: tuple[NodePortSemantic, ...],
    parameter_strategies: tuple[str, ...],
    compatible_upstream: tuple[str, ...],
    compatible_downstream: tuple[str, ...],
    failure_modes: tuple[str, ...],
    repair_hints: tuple[str, ...],
    safe_for_user: bool = True,
    requires_external_models: bool = False,
    custom_node_package: str | None = None,
    first_class: bool = True,
) -> NodeSemanticEntry:
    return NodeSemanticEntry(
        node_type=node_type,
        display_names=display_names,
        category=category,
        purpose=purpose,
        inputs=inputs,
        outputs=outputs,
        parameter_strategies=parameter_strategies,
        compatible_upstream=compatible_upstream,
        compatible_downstream=compatible_downstream,
        failure_modes=failure_modes,
        repair_hints=repair_hints,
        safe_for_user=safe_for_user,
        requires_external_models=requires_external_models,
        custom_node_package=custom_node_package,
        first_class=first_class,
    )


_REGISTRY: dict[str, NodeSemanticEntry] = {
    "CheckpointLoaderSimple": _entry(
        "CheckpointLoaderSimple",
        display_names=("Load Checkpoint", "Checkpoint Loader Simple"),
        category="Model",
        purpose="Load a checkpoint and expose model, CLIP, and VAE outputs.",
        inputs=(_port("ckpt_name", "Checkpoint filename selected from ComfyUI models.", "COMBO"),),
        outputs=(
            _port("model", "Diffusion model used by sampler nodes.", "MODEL"),
            _port("clip", "Text encoder used by conditioning nodes.", "CLIP"),
            _port("vae", "VAE used for latent/image conversion.", "VAE"),
        ),
        parameter_strategies=("Use an installed checkpoint name from ComfyUI object metadata.",),
        compatible_upstream=(),
        compatible_downstream=("CLIPTextEncode", "KSampler", "VAEDecode", "VAEEncode"),
        failure_modes=("Checkpoint file is missing or incompatible with the workflow.",),
        repair_hints=("Ask the user to pick an installed checkpoint or run capability resolution.",),
        requires_external_models=True,
    ),
    "CLIPTextEncode": _entry(
        "CLIPTextEncode",
        display_names=("CLIP Text Encode",),
        category="Conditioning",
        purpose="Encode prompt text into conditioning for a sampler.",
        inputs=(
            _port("clip", "CLIP model from a checkpoint or CLIP loader.", "CLIP"),
            _port("text", "Positive or negative prompt text.", "STRING"),
        ),
        outputs=(_port("conditioning", "Conditioning consumed by sampler nodes.", "CONDITIONING"),),
        parameter_strategies=("Keep positive and negative prompt nodes separate.",),
        compatible_upstream=("CheckpointLoaderSimple",),
        compatible_downstream=("KSampler",),
        failure_modes=("Missing CLIP link or empty text can produce poor or invalid results.",),
        repair_hints=("Link CLIP from the checkpoint and set prompt text explicitly.",),
    ),
    "EmptyLatentImage": _entry(
        "EmptyLatentImage",
        display_names=("Empty Latent Image",),
        category="Latent",
        purpose="Create an empty latent canvas for text-to-image sampling.",
        inputs=(
            _port("width", "Output width in pixels.", "INT"),
            _port("height", "Output height in pixels.", "INT"),
            _port("batch_size", "Number of latent images to create.", "INT"),
        ),
        outputs=(_port("latent", "Latent image consumed by sampler nodes.", "LATENT"),),
        parameter_strategies=("Use dimensions divisible by 8 and keep batch size at 1 by default.",),
        compatible_upstream=(),
        compatible_downstream=("KSampler",),
        failure_modes=("Large dimensions can exceed VRAM.",),
        repair_hints=("Reduce width, height, or batch size before retrying.",),
    ),
    "KSampler": _entry(
        "KSampler",
        display_names=("KSampler",),
        category="Sampling",
        purpose="Denoise latent input with a model and conditioning to produce sampled latent output.",
        inputs=(
            _port("model", "Diffusion model.", "MODEL"),
            _port("positive", "Positive conditioning.", "CONDITIONING"),
            _port("negative", "Negative conditioning.", "CONDITIONING"),
            _port("latent_image", "Initial latent image.", "LATENT"),
            _port("seed", "Sampling seed.", "INT"),
            _port("steps", "Sampling step count.", "INT"),
            _port("cfg", "Classifier-free guidance scale.", "FLOAT"),
            _port("sampler_name", "Sampler algorithm.", "COMBO"),
            _port("scheduler", "Scheduler algorithm.", "COMBO"),
            _port("denoise", "Denoise strength.", "FLOAT"),
        ),
        outputs=(_port("samples", "Sampled latent result.", "LATENT"),),
        parameter_strategies=("Default to conservative steps and CFG values until a recipe overrides them.",),
        compatible_upstream=("CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "VAEEncode"),
        compatible_downstream=("VAEDecode",),
        failure_modes=("Missing model, conditioning, or latent links make the workflow invalid.",),
        repair_hints=("Validate required sampler links against object_info before execution.",),
    ),
    "VAEDecode": _entry(
        "VAEDecode",
        display_names=("VAE Decode",),
        category="Image",
        purpose="Decode latent samples into images.",
        inputs=(
            _port("samples", "Latent samples to decode.", "LATENT"),
            _port("vae", "VAE used for decoding.", "VAE"),
        ),
        outputs=(_port("images", "Decoded image batch.", "IMAGE"),),
        parameter_strategies=("Use the VAE from the same checkpoint unless a recipe selects another VAE.",),
        compatible_upstream=("KSampler", "CheckpointLoaderSimple"),
        compatible_downstream=("SaveImage", "PreviewImage", "ImageScale"),
        failure_modes=("Mismatched or missing VAE can produce invalid decode results.",),
        repair_hints=("Link VAE from checkpoint or a compatible VAELoader.",),
    ),
    "VAEEncode": _entry(
        "VAEEncode",
        display_names=("VAE Encode",),
        category="Latent",
        purpose="Encode images into latent space for image-to-image workflows.",
        inputs=(
            _port("pixels", "Source image pixels.", "IMAGE"),
            _port("vae", "VAE used for encoding.", "VAE"),
        ),
        outputs=(_port("latent", "Encoded latent image.", "LATENT"),),
        parameter_strategies=("Use for image-to-image before KSampler with denoise below 1.",),
        compatible_upstream=("LoadImage", "CheckpointLoaderSimple"),
        compatible_downstream=("KSampler",),
        failure_modes=("Missing source image or VAE prevents latent encoding.",),
        repair_hints=("Load a source image and link VAE from the checkpoint.",),
    ),
    "SaveImage": _entry(
        "SaveImage",
        display_names=("Save Image",),
        category="Output",
        purpose="Save generated images to ComfyUI output storage.",
        inputs=(
            _port("images", "Images to save.", "IMAGE"),
            _port("filename_prefix", "Output filename prefix.", "STRING", required=False),
        ),
        outputs=(_port("saved_files", "Saved output files recorded by ComfyUI history.", "OUTPUT"),),
        parameter_strategies=("Use a short filename prefix such as Comfydex.",),
        compatible_upstream=("VAEDecode", "ImageScale", "ImageUpscaleWithModel"),
        compatible_downstream=(),
        failure_modes=("Missing images link means the workflow produces no saved output.",),
        repair_hints=("Ensure at least one image-producing node connects to SaveImage.",),
    ),
    "PreviewImage": _entry(
        "PreviewImage",
        display_names=("Preview Image",),
        category="Output",
        purpose="Preview images in the ComfyUI interface without requiring a saved final output.",
        inputs=(_port("images", "Images to preview.", "IMAGE"),),
        outputs=(_port("preview", "Previewed images visible in the UI.", "OUTPUT"),),
        parameter_strategies=("Use as a secondary output when visual inspection matters.",),
        compatible_upstream=("VAEDecode", "ImageScale", "ImageUpscaleWithModel"),
        compatible_downstream=(),
        failure_modes=("Preview-only workflows may not leave durable output files.",),
        repair_hints=("Add SaveImage when the user needs files collected by Comfydex.",),
    ),
    "LoadImage": _entry(
        "LoadImage",
        display_names=("Load Image",),
        category="Image",
        purpose="Load a source image for image-to-image, masking, or image processing.",
        inputs=(_port("image", "Image filename known to ComfyUI.", "COMBO"),),
        outputs=(
            _port("image", "Loaded image pixels.", "IMAGE"),
            _port("mask", "Optional alpha-derived mask.", "MASK", required=False),
        ),
        parameter_strategies=("Use only after confirming the image is available to ComfyUI.",),
        compatible_upstream=(),
        compatible_downstream=("VAEEncode", "ImageScale", "ImageCompositeMasked", "ImageToMask"),
        failure_modes=("Image filename is not available in ComfyUI input storage.",),
        repair_hints=("Ask the user to upload or provide a ComfyUI-visible image path.",),
    ),
    "LoadImageMask": _entry(
        "LoadImageMask",
        display_names=("Load Image Mask",),
        category="Mask",
        purpose="Load a mask from an image channel.",
        inputs=(
            _port("image", "Mask image filename known to ComfyUI.", "COMBO"),
            _port("channel", "Image channel to interpret as mask.", "COMBO"),
        ),
        outputs=(_port("mask", "Loaded mask.", "MASK"),),
        parameter_strategies=("Use the alpha channel when available for edit masks.",),
        compatible_upstream=(),
        compatible_downstream=("SetLatentNoiseMask", "ImageCompositeMasked", "MaskToImage"),
        failure_modes=("The selected channel may not contain useful mask data.",),
        repair_hints=("Ask for a mask image with a clear alpha or luminance channel.",),
    ),
    "ImageScale": _entry(
        "ImageScale",
        display_names=("Image Scale",),
        category="Image",
        purpose="Resize an image to an explicit width and height.",
        inputs=(
            _port("image", "Image to resize.", "IMAGE"),
            _port("width", "Target width.", "INT"),
            _port("height", "Target height.", "INT"),
            _port("upscale_method", "Resize method.", "COMBO"),
        ),
        outputs=(_port("image", "Resized image.", "IMAGE"),),
        parameter_strategies=("Keep aspect ratio in the caller before using explicit dimensions.",),
        compatible_upstream=("LoadImage", "VAEDecode"),
        compatible_downstream=("SaveImage", "PreviewImage", "VAEEncode"),
        failure_modes=("Extreme dimensions can consume excessive memory.",),
        repair_hints=("Use moderate dimensions or ImageScaleBy for proportional resizing.",),
    ),
    "ImageScaleBy": _entry(
        "ImageScaleBy",
        display_names=("Image Scale By",),
        category="Image",
        purpose="Resize an image by a scalar factor.",
        inputs=(
            _port("image", "Image to resize.", "IMAGE"),
            _port("scale_by", "Scale factor.", "FLOAT"),
            _port("upscale_method", "Resize method.", "COMBO"),
        ),
        outputs=(_port("image", "Resized image.", "IMAGE"),),
        parameter_strategies=("Use scale factors such as 0.5, 1.5, or 2.0.",),
        compatible_upstream=("LoadImage", "VAEDecode"),
        compatible_downstream=("SaveImage", "PreviewImage", "VAEEncode"),
        failure_modes=("Large scale factors can exceed memory.",),
        repair_hints=("Reduce scale factor or use tiled/upscale-model workflows in later recipes.",),
    ),
    "ImageInvert": _entry(
        "ImageInvert",
        display_names=("Image Invert",),
        category="Image",
        purpose="Invert image colors.",
        inputs=(_port("image", "Image to invert.", "IMAGE"),),
        outputs=(_port("image", "Inverted image.", "IMAGE"),),
        parameter_strategies=("Use for simple utility workflows and mask preparation previews.",),
        compatible_upstream=("LoadImage", "VAEDecode"),
        compatible_downstream=("SaveImage", "PreviewImage", "ImageToMask"),
        failure_modes=("Inverting the wrong source can make masks or colors unusable.",),
        repair_hints=("Preview before using inverted image as mask input.",),
    ),
    "ImageCompositeMasked": _entry(
        "ImageCompositeMasked",
        display_names=("Image Composite Masked",),
        category="Image",
        purpose="Composite a source image over a destination image using a mask.",
        inputs=(
            _port("destination", "Base image.", "IMAGE"),
            _port("source", "Image placed over the destination.", "IMAGE"),
            _port("mask", "Mask controlling the composite.", "MASK"),
            _port("x", "Horizontal placement.", "INT"),
            _port("y", "Vertical placement.", "INT"),
        ),
        outputs=(_port("image", "Composited image.", "IMAGE"),),
        parameter_strategies=("Default x and y to 0 unless a recipe calculates placement.",),
        compatible_upstream=("LoadImage", "MaskToImage", "LoadImageMask"),
        compatible_downstream=("SaveImage", "PreviewImage"),
        failure_modes=("Mask/image size mismatch can produce unexpected placement.",),
        repair_hints=("Scale source, destination, and mask to compatible dimensions first.",),
    ),
    "MaskToImage": _entry(
        "MaskToImage",
        display_names=("Mask To Image",),
        category="Mask",
        purpose="Convert a mask into an image for preview or image operations.",
        inputs=(_port("mask", "Mask to convert.", "MASK"),),
        outputs=(_port("image", "Image representation of the mask.", "IMAGE"),),
        parameter_strategies=("Use for previewing masks before edit workflows.",),
        compatible_upstream=("LoadImageMask", "ImageToMask"),
        compatible_downstream=("PreviewImage", "SaveImage", "ImageCompositeMasked"),
        failure_modes=("A blank mask produces a blank preview.",),
        repair_hints=("Inspect the mask preview before running an edit.",),
    ),
    "ImageToMask": _entry(
        "ImageToMask",
        display_names=("Image To Mask",),
        category="Mask",
        purpose="Convert an image channel into a mask.",
        inputs=(
            _port("image", "Image to convert.", "IMAGE"),
            _port("channel", "Channel used as mask data.", "COMBO"),
        ),
        outputs=(_port("mask", "Converted mask.", "MASK"),),
        parameter_strategies=("Use red, green, blue, or alpha based on source image structure.",),
        compatible_upstream=("LoadImage", "ImageInvert", "MaskToImage"),
        compatible_downstream=("SetLatentNoiseMask", "ImageCompositeMasked", "MaskToImage"),
        failure_modes=("Wrong channel selection can create an empty or inverted mask.",),
        repair_hints=("Preview the mask and switch channels when the mask is empty.",),
    ),
    "VAEEncodeForInpaint": _entry(
        "VAEEncodeForInpaint",
        display_names=("VAE Encode For Inpaint",),
        category="Latent",
        purpose="Encode an image and mask into latent space for inpainting.",
        inputs=(
            _port("pixels", "Source image pixels.", "IMAGE"),
            _port("vae", "VAE used for encoding.", "VAE"),
            _port("mask", "Inpaint mask.", "MASK"),
        ),
        outputs=(_port("latent", "Masked latent image for sampling.", "LATENT"),),
        parameter_strategies=("Use with masks that clearly identify the editable region.",),
        compatible_upstream=("LoadImage", "LoadImageMask", "CheckpointLoaderSimple"),
        compatible_downstream=("KSampler",),
        failure_modes=("Poor masks cause edits outside the intended region.",),
        repair_hints=("Preview mask and image alignment before sampling.",),
    ),
    "SetLatentNoiseMask": _entry(
        "SetLatentNoiseMask",
        display_names=("Set Latent Noise Mask",),
        category="Latent",
        purpose="Attach a mask to latent samples so sampling can respect an edit region.",
        inputs=(
            _port("samples", "Latent samples to annotate.", "LATENT"),
            _port("mask", "Noise mask.", "MASK"),
        ),
        outputs=(_port("latent", "Latent samples with noise mask.", "LATENT"),),
        parameter_strategies=("Use for inpaint variants that require explicit latent noise masks.",),
        compatible_upstream=("VAEEncode", "LoadImageMask", "ImageToMask"),
        compatible_downstream=("KSampler",),
        failure_modes=("Mask dimensions may not align with the latent image.",),
        repair_hints=("Encode image and mask through compatible image dimensions.",),
    ),
}


def list_node_semantics() -> list[dict[str, Any]]:
    return [
        entry.to_dict()
        for entry in sorted(_REGISTRY.values(), key=lambda item: item.node_type)
    ]


def get_node_semantics(node_type: str) -> dict[str, Any] | None:
    entry = _REGISTRY.get(node_type)
    return entry.to_dict() if entry else None


def validate_semantic_registry() -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    seen_display_names: set[tuple[str, str]] = set()
    for node_type, entry in _REGISTRY.items():
        if entry.node_type != node_type:
            errors.append({"node_type": node_type, "reason": "node_type_key_mismatch"})
        if not entry.display_names:
            errors.append({"node_type": node_type, "reason": "missing_display_names"})
        if not entry.category:
            errors.append({"node_type": node_type, "reason": "missing_category"})
        if not entry.purpose:
            errors.append({"node_type": node_type, "reason": "missing_purpose"})
        if not entry.inputs and not entry.outputs:
            errors.append({"node_type": node_type, "reason": "missing_ports"})
        for display_name in entry.display_names:
            key = (entry.node_type, display_name.lower())
            if key in seen_display_names:
                errors.append(
                    {
                        "node_type": node_type,
                        "reason": "duplicate_display_name",
                        "display_name": display_name,
                    }
                )
            seen_display_names.add(key)
    return {
        "status": "valid" if not errors else "invalid",
        "entry_count": len(_REGISTRY),
        "errors": errors,
    }
