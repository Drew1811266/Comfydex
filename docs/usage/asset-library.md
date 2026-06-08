# Asset Library Usage

Comfydex `0.6.0` adds a workspace-local asset library on top of the shared project index. Assets are indexed generated output files connected to runs, workflows, prompt text, model references, tags, ratings, favorites, sidecars, cleanup plans, reports, and comparisons.

## Reindex

Use `comfy_reindex_assets` after runs or output files change:

```text
comfy_reindex_assets
```

Set `include_sidecars=True` when Codex should also write sidecar JSON metadata under `.comfydex/assets/sidecars/`.

## Search

Use `comfy_search_assets` to filter by query, run id, workflow name, status, output type, tags, favorite state, minimum rating, and pagination.

The query searches filename, workflow name, prompt text, notes, tags, and model references.

## Metadata

Use `comfy_update_asset_metadata` to update user annotations.

Tags are normalized, ratings must be from 1 to 5, favorite must be boolean, and notes are length-limited. Reindexing preserves tags, rating, favorite state, and notes for stable asset ids.

## Sidecars

Use `comfy_write_asset_sidecars` to write deterministic JSON sidecars for selected assets or all indexed assets.

Sidecars include asset id, run id, workflow name, output path, filename, size, prompt text, model references, tags, rating, favorite state, and notes.

## Cleanup

Use `comfy_plan_asset_cleanup` for asset-level cleanup. It is dry-run by default and returns candidates without deleting files.

Only call it with `confirm=True` after inspecting candidates. Confirmed cleanup rechecks every file path before deletion and never deletes run records, workflow snapshots, sidecars, reports, or database rows directly.

## Reports And Comparison

Use `comfy_export_asset_library_report` to write `.comfydex/reports/asset-library-report.md`.

Use `comfy_compare_assets` to compare two assets by run, workflow, status, prompt text, model references, file size, tags, rating, and favorite state.
