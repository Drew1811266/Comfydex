# Ordinary User Guidance

Comfydex 1.8 adds a plain-language layer on top of technical workflow data so a normal ComfyUI user can ask for common text-to-image work without reading the internal node graph first.

## Common Path

1. Describe the image and provide the model name when it is known.
2. Use `quality_preset`, `aspect_ratio`, and `style_preset` instead of hand-tuning width, height, steps, and prompt style text.
3. Review the `user_guidance` object before generating or running. It contains `title`, `summary`, `severity`, `bullets`, `next_actions`, and a compact `technical` section.
4. Generate and run with `comfy_generate_run_fetch` for low-risk single-run tasks.
5. Review `output_summary` after outputs are fetched and indexed.

## Presets And Defaults

Use `comfy_list_generation_presets` to inspect supported preset names.

- `quality_preset`: `draft`, `balanced`, or `high`.
- `aspect_ratio`: `square`, `portrait`, `landscape`, or `wide`.
- `style_preset`: `photographic`, `cinematic`, `illustration`, or `product`.

Generation plans include `resolved_defaults` so Codex can explain which size, step count, CFG value, GPU class, model family, and preset decisions were applied. Explicit numeric values still win over defaults.

## Missing Items And Setup

Capability and generation summaries use plain labels for common missing inputs:

- checkpoint model instead of `checkpoint_name`
- prompt instead of `positive_prompt`
- input image instead of `image`

Technical node names, policy reasons, and validation details remain available under `technical`, `generation`, `policy`, and related payloads.

## Canvas Replacement

Live Bridge push responses include `canvas_replacement`. It tells the user whether replacing the visible ComfyUI canvas requires review, including unsaved-canvas diagnostics when the frontend reports them. A forced push still records the diagnostic codes so the decision is visible afterward.

## Assets And Comparison

Use `comfy_summarize_assets` to get a searchable asset result with a plain output-library summary. `comfy_compare_assets` now includes a human-readable comparison summary alongside the changed technical fields.

The desktop app displays these summaries in the Project, Generated, Runs, and Assets views. It remains a local workbench, not a full ComfyUI graph editor.
