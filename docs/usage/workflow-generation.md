# Workflow Generation Usage

Comfydex `0.4.0` adds a deterministic workflow generation engine. Codex still
interprets natural language, while Comfydex turns the request into a structured
plan, validates generated workflow JSON, records safe repairs, and returns a
submit policy.

## Plan First

Use `comfy_plan_workflow_generation` before saving or running a workflow. The
plan shows the selected template, candidate templates, normalized parameters,
missing information, assumptions, and safety constraints.

## Generate

Use `comfy_generate_workflow` after required inputs are present. It builds the
API prompt JSON, validates it against ComfyUI object metadata when available,
applies safe mechanical repairs, and saves the workflow only when the submit
policy allows it.

Repairable examples include clamping excessive step counts to the configured
limit. Blocking examples include dimensions that exceed the configured pixel
limit, missing required inputs, invalid API shape, or unavailable node metadata.

## Submit Policy

Use `comfy_evaluate_submit_policy` for an existing workflow before submission.

Submit policy decisions are:

- `allowed`: validated, submit-ready, single-run, and inside configured safety
  limits.
- `requires_confirmation`: structurally valid, but a high-risk condition such
  as overwriting an existing workflow requires explicit confirmation.
- `blocked`: not submit-ready, invalid, missing required information, or outside
  configured safety limits.

Do not submit workflows with `blocked` policy. Ask for explicit user
confirmation before submitting workflows with `requires_confirmation`.
