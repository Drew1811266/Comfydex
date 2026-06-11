# Node Semantic Registry

The Node Semantic Registry is Comfydex's handwritten knowledge base for supported ComfyUI nodes. It explains what a node does, what its inputs and outputs mean, how it usually connects to nearby nodes, common failure modes, repair hints, whether it is safe for ordinary users, and whether it requires external model assets.

The registry is intentionally conservative. Unknown nodes are not treated as first-class supported nodes.

## Supported Native Nodes

Comfydex `1.3.0` includes first-class semantics for common native graph building blocks:

- `CheckpointLoaderSimple`
- `CLIPTextEncode`
- `EmptyLatentImage`
- `KSampler`
- `VAEDecode`
- `VAEEncode`
- `LoadImage`
- `LoadImageMask`
- `SaveImage`
- `PreviewImage`
- `ImageScale`
- `ImageScaleBy`
- `ImageInvert`
- `ImageCompositeMasked`
- `MaskToImage`
- `ImageToMask`
- `VAEEncodeForInpaint`
- `SetLatentNoiseMask`

These entries let Codex explain basic model loading, conditioning, latent creation, sampling, VAE encode/decode, image loading, image saving, preview, basic image operations, and basic mask operations.

## Functional Pack Entries

The registry also includes conservative semantic entries for common functional paths:

- `LoraLoader`
- `ControlNetLoader`
- `ControlNetApply`
- `ControlNetApplyAdvanced`
- `UpscaleModelLoader`
- `ImageUpscaleWithModel`
- `VAELoader`
- `IPAdapterUnifiedLoader`
- `IPAdapterAdvanced`

LoRA, ControlNet, upscale, VAE, and inpaint entries can be explained and matched against `object_info`. IP-Adapter entries are attributed to `ComfyUI_IPAdapter_plus` and marked as not first-class until capability resolution can verify the installed package contract.

## Unknown Node Behavior

Unknown nodes are not treated as first-class supported nodes.

If a node appears in ComfyUI `object_info` but does not exist in the registry, Comfydex reports it as unknown. It may still inspect the node structurally through `object_info`, but planning should not rely on it for first-class workflow generation unless a later scenario recipe explicitly allows structural passthrough.

## MCP Tools

Use `comfy_list_node_semantics` to list all supported registry entries.

Use `comfy_explain_node_semantics` to explain one node, such as `CheckpointLoaderSimple` or `KSampler`. Unknown nodes return `status: unsupported`.

Use `comfy_search_node_semantics` to search by node type, display name, category, purpose, or parameter strategy.

Use `comfy_validate_node_semantics` to compare the registry against live ComfyUI `object_info`. The result includes supported node types, missing supported node types, unknown node types, and the local registry validation report.

## object_info Matching

`object_info` matching is a verification layer, not the source of semantic truth. Comfydex uses registry entries to explain supported behavior, then uses live ComfyUI metadata to check what is actually installed.

Status meanings:

- `valid`: every registry node is visible and there are no unknown live node types.
- `partial`: at least one registry node is visible, but some supported entries are missing or live unknown nodes exist.
- `unsupported`: no registry node types are visible.
- `invalid_object_info`: the ComfyUI metadata payload was not a mapping.

This keeps Comfydex honest when a local ComfyUI installation differs from the supported first-class node set.
