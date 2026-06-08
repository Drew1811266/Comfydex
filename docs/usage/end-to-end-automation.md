# End-To-End Automation Usage

Comfydex `0.9.0` adds `comfy_generate_run_fetch` for the safe one-call path from a natural-language request to a generated workflow, submitted run, completion wait, fetched outputs, and project reindex.

The tool is intended for low-risk single-run work. It does not replace the lower-level tools. Use `comfy_plan_workflow_generation`, `comfy_generate_workflow`, `comfy_evaluate_submit_policy`, `comfy_submit_workflow`, `comfy_wait_for_run`, and `comfy_fetch_outputs` when a workflow needs manual inspection between stages.

## Tool

```text
comfy_generate_run_fetch
```

Primary arguments:

- `name`: target workflow JSON filename under the configured workflow directory.
- `intent`: natural-language workflow intent.
- `parameters`: structured generation parameters such as `checkpoint_name`, `positive_prompt`, `width`, `height`, and `steps`.
- `template_id`: optional explicit workflow template.
- `constraints`: generation constraints such as `max_steps`, `max_pixels`, and overwrite policy.
- `run_label`: optional label for the run record.
- `confirm_risky_actions`: default `False`; required before medium-risk actions proceed.
- `wait_for_completion`: default `True`; waits through WebSocket and HTTP fallback.
- `fetch_outputs`: default `True`; fetches or registers output references after completion.
- `download_outputs`: default `True`; downloads output files through ComfyUI `/view`.
- `use_object_info`: default `True`; validates with ComfyUI `/object_info` when reachable.

## Safe Low-Risk Flow

Use the tool when the request has all required inputs and no risky policy reasons:

```text
comfy_generate_run_fetch
name: city.json
intent: text to image
parameters:
  checkpoint_name: model.safetensors
  positive_prompt: cinematic city at night
```

Expected successful response:

```json
{
  "status": "completed",
  "stage": "completed",
  "saved_workflow": "city.json",
  "run": {"status": "completed"},
  "outputs": {"outputs": []},
  "index": {"status": "completed"}
}
```

The tool saves the workflow, submits it, waits for the run, calls `comfy_fetch_outputs`, and runs `reindex` so the new workflow, run, and assets are visible through project and desktop views.

## Confirmation Required

When policy returns `requires_confirmation`, the tool stops before saving or submitting:

```json
{
  "status": "requires_confirmation",
  "stage": "policy",
  "policy": {
    "decision": "requires_confirmation",
    "reasons": ["workflow_overwrite"]
  },
  "next_actions": [
    "Set confirm_risky_actions=true after reviewing policy.reasons to overwrite the existing workflow."
  ]
}
```

Pass `confirm_risky_actions=True` only after reviewing `policy.reasons`, generation validation, and the target workflow name. This flag can allow medium-risk actions such as workflow overwrite or unknown validation state, but it cannot override a `blocked` policy.

## Object Info Unavailable

When `use_object_info=True` and ComfyUI `/object_info` cannot be loaded, the tool performs structural generation only and includes `object_info_unavailable` in policy reasons:

```json
{
  "status": "requires_confirmation",
  "object_info_warning": {
    "reason": "object_info_unavailable",
    "error": "object info down"
  },
  "policy": {
    "decision": "requires_confirmation",
    "reasons": ["object_info_unavailable"]
  }
}
```

This prevents unknown validation from silently auto-running. Use `confirm_risky_actions=True` only when the workflow is simple, the node classes are known to the user, and the generated JSON has been reviewed.

## Wait And Fetch Controls

Set `wait_for_completion=False` to stop after submission:

```text
wait_for_completion: false
fetch_outputs: false
```

The response returns `status: submitted` and `next_actions` that point to `comfy_wait_for_run` and `comfy_fetch_outputs`.

Set `fetch_outputs=False` when the run should complete but output download should be delayed. Later, call:

```text
comfy_fetch_outputs
run_id: <returned run_id>
```

## Recovery

The automation result keeps failures recoverable:

- Submit failure returns `status: failed`, `stage: submit`, and a failed run record when one was created.
- Wait failure returns `status: failed`, `stage: wait`, and the latest readable run record.
- Fetch failure returns `status: failed`, `stage: fetch`, and next actions for retrying `comfy_fetch_outputs`.
- Reindex failure is reported as `index_warning` and does not hide a completed run.

For failed runs, inspect:

```text
comfy_read_run
comfy_diagnose_run
```

For completed runs with missing local files, retry:

```text
comfy_fetch_outputs
comfy_reindex_project
```

## Boundaries

`comfy_generate_run_fetch` does not:

- submit batches,
- automate cleanup deletion,
- edit ComfyUI UI workflow graphs,
- bypass blocked policy,
- write outside configured workflow and run directories,
- expose configured request headers.
