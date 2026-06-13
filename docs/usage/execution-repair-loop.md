# Execution And Repair Loop

Comfydex `1.7.0` adds an Execution And Repair Loop for failed or incomplete workflow runs. The loop classifies failure evidence, builds a structured `repair_plan`, records repair history, and exposes conservative retry operations through MCP and the desktop app.

The repair loop is a recovery surface, not an automatic installer or model downloader. It keeps no silent downloads, no automatic downloads, no silent custom node installs, and no unconfirmed resubmission for confirmation-required cases.

## Failure Classes

Run diagnosis now exposes:

- `failure_class`
- `repair_summary`
- `retryable`

Repair plans can classify:

- `missing_model`
- `missing_node`
- `missing_outputs`
- `resource_failure`
- `invalid_parameter`
- `invalid_link`
- `fetch_failure`
- `execution_error`
- `unknown_failure`

Missing models and missing nodes are manual-action classes. Fetch failures and missing outputs can retry `fetch_outputs` without confirmation. Execution, parameter, link, and resource failures can prepare a resubmit retry, but require explicit confirmation.

## MCP Tools

Use these tools after a run fails or completes without registered outputs:

```text
comfy_plan_run_repair
comfy_retry_run_repair
comfy_read_repair_history
```

`comfy_plan_run_repair` reads the run record, workflow snapshot, optional live `object_info`, diagnosis, and returns:

```json
{
  "status": "planned",
  "diagnosis": {
    "failure_class": "resource_failure",
    "repair_summary": "Reduce workload settings such as resolution, batch size, or steps before retrying."
  },
  "repair_plan": {
    "failure_class": "resource_failure",
    "actions": [{ "kind": "reduce_workload" }],
    "retry": {
      "supported": true,
      "operation": "resubmit_workflow",
      "requires_confirmation": true
    }
  }
}
```

`comfy_retry_run_repair` builds a fresh plan before acting. It returns `requires_confirmation` when the retry would resubmit a workflow and `confirm` is not true.

`comfy_read_repair_history` reads `.comfydex/repair_history.jsonl` newest first. History records include the run id, workflow name, status, `failure_class`, retry support, and action count.

## Automation Integration

`comfy_generate_run_fetch` now attaches `diagnosis`, `repair_plan`, and repair history data to failed submit, wait, non-completed failed wait, and fetch responses.

Fetch-stage failures classify as `fetch_failure` and return `repair_plan.retry.operation == "fetch_outputs"`. Failed execution responses use the same `failure_class`, `repair_summary`, `repair_plan`, `actions`, `retry`, `requires_confirmation`, and `retry_result` language as direct MCP repair tools.

## Desktop

The desktop Runs repair panel uses the Python desktop bridge operations:

```text
plan_run_repair
retry_run_repair
read_repair_history
```

The Runs view can load a plan for the selected run, show the failure class, repair summary, actions, recent repair history, and a retry button when the plan supports retry. Confirmation-required retries are prepared first and require a second explicit confirm action.

## Safety Boundaries

- Do not use repair plans as permission to download models.
- Do not install custom nodes automatically from a repair action.
- Do not resubmit a workflow unless `requires_confirmation` has been shown and the user has confirmed.
- Do not treat unknown nodes as supported just because a retry is available.
- Do not claim output recovery until `comfy_fetch_outputs` returns output references or downloaded paths.
