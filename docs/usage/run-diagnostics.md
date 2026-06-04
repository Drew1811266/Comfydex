# Run Diagnostics

Use this flow after submission, when a run fails, when outputs are missing, or when comparing experiments.

## Diagnosis

Call `comfy_read_run` first, then `comfy_diagnose_run`. Diagnosis inspects run status, WebSocket events, fallback polling status, ComfyUI history status, missing outputs, missing node types, and detectable missing model references.

## Reports

Use `comfy_export_run_report` to write `runs/<run_id>/report.md`. Reports include run metadata, diagnosis summary, workflow summary, and output references. Report paths are derived from `run_id`; do not pass arbitrary file paths.

## Output Cleanup

Use `comfy_list_outputs` before cleanup. `comfy_cleanup_outputs` is dry-run by default and only deletes when `confirm=True`. Cleanup can filter by failed run ids or non-negative age thresholds and must never delete outside `runs_dir`.

## Batch Runs

Use `comfy_batch_submit` for parameter sweeps and `comfy_read_batch` to inspect child run statuses. Batch records are stored under `runs/.batches/` and should preserve partial failures for review.
