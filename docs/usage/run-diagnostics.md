# Run Diagnostics

Use this flow after submission, when a run fails, when outputs are missing, or when comparing experiments.

## Diagnosis

Call `comfy_read_run` first, then `comfy_diagnose_run`. Diagnosis inspects run status, WebSocket events, fallback polling status, ComfyUI history status, missing outputs, missing node types, and detectable missing model references.

Required inputs: a valid `run_id`; optional `use_object_info` when missing-node detection should call ComfyUI object metadata. The `run_id` must refer to a run directory under the configured `runs_dir`.

## Reports

Use `comfy_export_run_report` to write `runs/<run_id>/report.md`. Reports include run metadata, diagnosis summary, workflow summary, and output references. Report paths are derived from `run_id`; do not pass arbitrary file paths.

Required inputs: a valid `run_id` with both `run.json` and `workflow.json` snapshots. The report target is derived as `runs/<run_id>/report.md`.

## Output Cleanup

Use `comfy_list_outputs` before cleanup. `comfy_cleanup_outputs` is dry-run by default and only deletes when `confirm=True`. Cleanup can filter by failed run ids or non-negative age thresholds and must never delete outside `runs_dir`.

Required inputs: optional `failed_run_ids`, optional non-negative `older_than_seconds`, and `confirm=True` only after reviewing dry-run candidates.

## Batch Runs

Use `comfy_batch_submit` for parameter sweeps and `comfy_read_batch` to inspect child run statuses. Batch records are stored under `runs/.batches/` and should preserve partial failures for review.

Required inputs: `workflow_name`, parameter `variations`, and an optional `batch_label`. Read results back with `batch_id`.
