from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from comfydex_mcp.assets import search_assets, update_asset_metadata
from comfydex_mcp.config import ComfydexConfig
from comfydex_mcp.core.database import open_database
from comfydex_mcp.core.indexer import reindex_project
from comfydex_mcp.core.project import project_context_from_config
from comfydex_mcp.runs import create_run, register_outputs, update_status


CAT_WORKFLOW = {
    "3": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sdxl.safetensors"},
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "cinematic cat", "clip": ["3", 1]},
    },
    "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
}
DOG_WORKFLOW = {
    "3": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "realistic.safetensors"},
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "studio dog", "clip": ["3", 1]},
    },
    "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
}


def _config(tmp_path: Path) -> ComfydexConfig:
    return ComfydexConfig(
        workspace=tmp_path,
        base_url="http://127.0.0.1:8188",
        workflows_dir=tmp_path / "workflows",
        runs_dir=tmp_path / "runs",
        headers={},
        request_timeout_seconds=30,
        websocket_timeout_seconds=600,
    )


def _write_run_with_output(
    cfg: ComfydexConfig,
    workflow_name: str,
    workflow: dict,
    filename: str,
    timestamp: datetime,
) -> None:
    run = create_run(
        cfg.runs_dir,
        workflow_name,
        workflow,
        cfg.base_url,
        f"prompt-{filename}",
        now=timestamp,
    )
    update_status(cfg.runs_dir, run["run_id"], "completed")
    output_path = cfg.runs_dir / run["run_id"] / "outputs" / "images" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(filename, encoding="utf-8")
    register_outputs(
        cfg.runs_dir,
        run["run_id"],
        [
            {
                "filename": filename,
                "type": "images",
                "subfolder": "images",
                "downloaded_path": str(output_path),
            }
        ],
    )


def _indexed_context(tmp_path: Path):
    cfg = _config(tmp_path)
    _write_run_with_output(
        cfg,
        "cat.json",
        CAT_WORKFLOW,
        "cat.png",
        datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )
    _write_run_with_output(
        cfg,
        "dog.json",
        DOG_WORKFLOW,
        "dog.png",
        datetime(2026, 6, 8, 12, 1, tzinfo=timezone.utc),
    )
    ctx = project_context_from_config(cfg)
    reindex_project(ctx)
    return ctx


def _asset_id_for_filename(ctx, filename: str) -> str:
    with open_database(ctx.database_path) as db:
        row = db.execute(
            "SELECT asset_id FROM asset_records WHERE filename = ?",
            (filename,),
        ).fetchone()
    return row["asset_id"]


def test_search_assets_filters_query_tags_favorite_and_rating(tmp_path: Path):
    ctx = _indexed_context(tmp_path)
    cat_id = _asset_id_for_filename(ctx, "cat.png")
    dog_id = _asset_id_for_filename(ctx, "dog.png")
    update_asset_metadata(
        ctx,
        cat_id,
        tags=["keeper", "cat"],
        rating=5,
        favorite=True,
        notes="best output",
    )
    update_asset_metadata(ctx, dog_id, tags=["dog"], rating=3, favorite=False)

    cat_result = search_assets(ctx, {"query": "cinematic", "limit": 10})
    tagged_result = search_assets(ctx, {"tags": ["keeper", "cat"], "favorite": True})
    rated_result = search_assets(ctx, {"min_rating": 4})

    assert cat_result["total"] == 1
    assert cat_result["assets"][0]["asset_id"] == cat_id
    assert tagged_result["assets"][0]["asset_id"] == cat_id
    assert rated_result["assets"][0]["asset_id"] == cat_id


def test_search_assets_orders_by_favorite_rating_modified_and_filename(tmp_path: Path):
    ctx = _indexed_context(tmp_path)
    cat_id = _asset_id_for_filename(ctx, "cat.png")
    dog_id = _asset_id_for_filename(ctx, "dog.png")
    update_asset_metadata(ctx, cat_id, rating=5, favorite=True)
    update_asset_metadata(ctx, dog_id, rating=5, favorite=False)

    result = search_assets(ctx, {"limit": 10})

    assert [asset["asset_id"] for asset in result["assets"]] == [cat_id, dog_id]


def test_update_asset_metadata_normalizes_and_preserves_across_reindex(
    tmp_path: Path,
):
    ctx = _indexed_context(tmp_path)
    asset_id = _asset_id_for_filename(ctx, "cat.png")

    updated = update_asset_metadata(
        ctx,
        asset_id,
        tags=[" keeper ", "cat", "keeper"],
        rating=5,
        favorite=True,
        notes=" best   output ",
    )
    reindex_project(ctx)
    result = search_assets(ctx, {"tags": ["keeper"]})

    assert updated["tags"] == ["cat", "keeper"]
    assert updated["rating"] == 5
    assert updated["favorite"] is True
    assert updated["notes"] == "best output"
    assert result["assets"][0]["asset_id"] == asset_id
    assert result["assets"][0]["tags"] == ["cat", "keeper"]
    assert result["assets"][0]["favorite"] is True


@pytest.mark.parametrize("rating", [0, 6, "5", True])
def test_update_asset_metadata_rejects_invalid_rating(
    tmp_path: Path,
    rating,
):
    ctx = _indexed_context(tmp_path)
    asset_id = _asset_id_for_filename(ctx, "cat.png")

    with pytest.raises(ValueError, match="rating"):
        update_asset_metadata(ctx, asset_id, rating=rating)


def test_update_asset_metadata_rejects_invalid_tags(tmp_path: Path):
    ctx = _indexed_context(tmp_path)
    asset_id = _asset_id_for_filename(ctx, "cat.png")

    with pytest.raises(ValueError, match="tags"):
        update_asset_metadata(ctx, asset_id, tags=["valid", "x" * 41])


@pytest.mark.parametrize(
    "filters",
    [
        {"limit": 0},
        {"limit": 501},
        {"offset": -1},
        {"min_rating": 6},
    ],
)
def test_search_assets_rejects_invalid_filters(tmp_path: Path, filters: dict):
    ctx = _indexed_context(tmp_path)

    with pytest.raises(ValueError):
        search_assets(ctx, filters)
