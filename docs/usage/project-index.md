# Project Index Usage

Comfydex `0.3.0` adds a workspace-local project index for workflows, runs,
outputs, batches, and recoverable indexing errors.

The index database lives at:

```text
.comfydex/comfydex.db
```

The database is an index, not the only project record. Comfydex still preserves
JSON workflow files, run records, batch records, and output files as
compatibility records.

## Status

Use `comfy_project_status` to inspect the active workspace, configured
workflow/run directories, database path, schema version, record counts, error
count, and last reindex timestamp.

`comfy_project_status` is local-only. It does not call ComfyUI.

## Reindex

Use `comfy_reindex_project` when:

- a workflow JSON file was edited outside Comfydex,
- run or batch records were copied into the workspace,
- output files were added or removed manually,
- project status shows stale counts,
- corrupt JSON needs to be surfaced as index errors.

`comfy_reindex_project` rebuilds the SQLite rows from the compatibility records.
It does not delete workflow files, run records, batch records, or output files.

## Error Handling

Corrupt JSON is reported through the returned `errors` list and the project
status error count. Reindexing skips unsafe or unreadable records and leaves the
original files in place for developer inspection.

If the database itself cannot be opened or migrated, fix the local filesystem or
database path issue first, then run `comfy_reindex_project` again.
