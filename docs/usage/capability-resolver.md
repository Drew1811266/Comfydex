# Capability Resolver

The Capability Resolver checks whether a requested workflow can run on the local ComfyUI environment before Codex builds or submits it. It combines a workspace model inventory, live node inventory from ComfyUI `object_info`, workflow generation planning, and a conservative install plan.

The resolver is intentionally conservative. It performs no silent downloads, does not install custom nodes, and does not mutate ComfyUI. It only reports what is present, what is missing, and which manual review actions should be recorded in the audit log.

## Inputs

Use a short workflow intent and any known generation parameters:

```json
{
  "intent": "text to image",
  "parameters": {
    "checkpoint_name": "sdxl.safetensors",
    "positive_prompt": "a small cabin beside a lake"
  }
}
```

If `model_roots` is omitted, Comfydex scans `workspace/models`.

## Model Inventory

Use `comfy_model_inventory` to scan local model files. The model inventory includes supported model extensions, inferred model type, filename, absolute path, and file size.

Model type inference recognizes common folders and filenames for:

- checkpoint
- lora
- controlnet
- upscale
- vae
- ipadapter

Missing roots are reported instead of treated as fatal errors.

## Node Inventory

`comfy_resolve_capabilities` calls live ComfyUI `object_info` and derives a node inventory. The node inventory records visible node types and semantic coverage from the Node Semantic Registry.

This keeps planning honest: a node can be semantically supported by Comfydex but still missing from the user's current ComfyUI installation.

## Capability Report

Use `comfy_resolve_capabilities` to produce a report with:

- `status`
- `can_run_now`
- selected workflow generation plan
- model inventory
- node inventory
- missing models
- missing nodes
- missing information

`can_run_now` is true only when required nodes are visible in `object_info`, required named models are present in the scanned inventory, and the generation plan has no unresolved required inputs.

## Conservative Install Plan

Use `comfy_create_install_plan` with a capability report. The conservative install plan is a review artifact, not an installer.

Missing models create manual model actions. Missing nodes create manual custom node actions with `restart_required: true`. Every action has `requires_confirmation: true` and `automatic: false`.

Comfydex 1.4 has no silent downloads and no automatic custom node installation.

## Audit Log

Use `comfy_record_install_audit` to record an accepted or rejected plan decision. Use `comfy_read_install_audit` to read recent entries.

The audit log is workspace-local and append-only:

```text
.comfydex/install_audit.jsonl
```

The desktop Install Plan panel in Settings shows capability status, missing models, missing nodes, conservative install plan actions, record accepted/rejected buttons, and recent audit log entries.

## Desktop Review

The desktop Install Plan panel uses the same Python desktop bridge operations as the MCP tools:

- `capability_report`
- `create_install_plan`
- `record_install_audit`
- `read_install_audit`

The panel records decisions. It does not install models, download files, or modify ComfyUI packages.
