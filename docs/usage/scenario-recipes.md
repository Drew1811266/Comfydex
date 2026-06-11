# Scenario Recipe Registry

The Scenario Recipe Registry is the 1.5 layer between natural-language workflow intent and deterministic workflow templates. It lets Codex explain which scenario it selected before it builds or submits a workflow.

Recipes describe common ComfyUI scenarios such as text-to-image, SDXL text-to-image, LoRA text-to-image, image-to-image, image upscale, and ControlNet pose. Each recipe maps to a built-in template, required inputs, required model types, required nodes, examples, and safety notes.

## Tool Order

Use recipe tools before workflow generation when the user describes a scenario in natural language:

1. `comfy_list_workflow_recipes`
2. `comfy_search_workflow_recipes`
3. `comfy_suggest_workflow_recipes`
4. `comfy_resolve_recipe_capabilities`
5. `comfy_plan_workflow_generation`
6. `comfy_generate_workflow`

`comfy_suggest_workflow_recipes` returns recipe candidates from the intent and supplied parameters. `comfy_plan_workflow_generation` includes the selected recipe id and uses the recipe-to-template mapping to boost the matching workflow template when no explicit `template_id` is supplied.

## Recipe Candidates

A suggestion result includes:

- `recipe_id`
- `template_id`
- `score`
- `reasons`

The recipe candidates list is explainable. Reasons can come from intent phrases, tags, model parameters such as `checkpoint_name` or `lora_name`, required input parameters, and recipe name words.

Explicit `template_id` still wins over recipe scoring. Use it when the user has named the template or when a previous plan must be reproduced exactly.

## Selected Recipe Id

Generated workflow plans include:

- `recipe_candidates`
- `selected_recipe_id`
- `selected_template_id`
- `candidate_templates`
- `missing_information`
- `semantic_coverage`

The selected recipe id is the recipe candidate mapped to the selected template. It is `null` when no recipe candidate explains the selected template, such as when a caller supplies only an explicit template override.

## Recipe-Aware Capability Checks

Use `comfy_resolve_recipe_capabilities` for recipe-aware capability checks before relying on a local model or custom node. The tool combines the recipe requirements, live ComfyUI `object_info`, local model inventory, and the existing Capability Resolver report.

The check reports missing required inputs, missing model files, missing node types, and whether the recipe can run now. If a recipe cannot run, use `comfy_create_install_plan` only to create a conservative review artifact.

## Boundaries

The Scenario Recipe Registry is not an installer or marketplace.

- It performs no automatic downloads.
- It does not install custom nodes.
- It does not mutate ComfyUI.
- It does not persist user-authored recipes in 1.5.
- It does not generate UI workflow canvas graphs.
