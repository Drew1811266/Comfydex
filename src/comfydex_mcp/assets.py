from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .core.database import migrate_project, open_database
from .core.project import ProjectContext
from .core.store import get_asset_row, list_asset_rows, update_asset_annotation

ASSET_ID_PATTERN = re.compile(r"[a-f0-9]{64}")
TEXT_MAX_LENGTH = 1000
TAG_MAX_LENGTH = 40
TAG_MAX_COUNT = 40
DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def search_assets(
    context: ProjectContext,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = _normalize_filters(filters or {})
    migrate_project(context)
    with open_database(context.database_path) as db:
        rows = [_asset_from_row(row) for row in list_asset_rows(db)]

    assets = [
        asset
        for asset in rows
        if _matches_filters(asset, normalized)
    ]
    assets.sort(
        key=lambda asset: (
            -int(asset["favorite"]),
            -(asset["rating"] or 0),
            -float(asset["modified_time"]),
            asset["filename"],
        )
    )
    total = len(assets)
    limit = normalized["limit"]
    offset = normalized["offset"]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "assets": assets[offset : offset + limit],
    }


def get_asset(context: ProjectContext, asset_id: str) -> dict[str, Any]:
    safe_asset_id = _safe_asset_id(asset_id)
    migrate_project(context)
    with open_database(context.database_path) as db:
        row = get_asset_row(db, safe_asset_id)
    if row is None:
        raise ValueError(f"unknown asset_id: {safe_asset_id}")
    return _asset_from_row(row)


def update_asset_metadata(
    context: ProjectContext,
    asset_id: str,
    *,
    tags: list[str] | None = None,
    rating: int | None = None,
    favorite: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    safe_asset_id = _safe_asset_id(asset_id)
    updates: dict[str, Any] = {}
    if tags is not None:
        updates["tags_json"] = json.dumps(_normalize_tags(tags), separators=(",", ":"))
    if rating is not None:
        updates["rating"] = _normalize_rating(rating)
    if favorite is not None:
        updates["favorite"] = 1 if _normalize_favorite(favorite) else 0
    if notes is not None:
        updates["notes"] = _normalize_notes(notes)

    migrate_project(context)
    with open_database(context.database_path) as db:
        if get_asset_row(db, safe_asset_id) is None:
            raise ValueError(f"unknown asset_id: {safe_asset_id}")
        if updates:
            updates["updated_at"] = _now()
            update_asset_annotation(db, safe_asset_id, updates)
        row = get_asset_row(db, safe_asset_id)
    return _asset_from_row(row)


def _normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(filters, dict):
        raise ValueError("filters must be a dictionary")
    limit = filters.get("limit", DEFAULT_LIMIT)
    offset = filters.get("offset", 0)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError("limit must be between 1 and 500")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be greater than or equal to 0")
    min_rating = filters.get("min_rating")
    if min_rating is not None:
        min_rating = _normalize_rating(min_rating)
    favorite = filters.get("favorite")
    if favorite is not None:
        favorite = _normalize_favorite(favorite)
    tags = filters.get("tags")
    if tags is not None:
        tags = _normalize_tags(tags)
    return {
        "query": _clean_text(filters.get("query"), "").casefold(),
        "run_id": _clean_text(filters.get("run_id"), ""),
        "workflow_name": _clean_text(filters.get("workflow_name"), ""),
        "status": _clean_text(filters.get("status"), ""),
        "type": _clean_text(filters.get("type"), ""),
        "tags": tags,
        "favorite": favorite,
        "min_rating": min_rating,
        "limit": limit,
        "offset": offset,
    }


def _matches_filters(asset: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters["run_id"] and asset["run_id"] != filters["run_id"]:
        return False
    if filters["workflow_name"] and asset["workflow_name"] != filters["workflow_name"]:
        return False
    if filters["status"] and asset["status"] != filters["status"]:
        return False
    if filters["type"] and asset["type"] != filters["type"]:
        return False
    if filters["favorite"] is not None and asset["favorite"] is not filters["favorite"]:
        return False
    if filters["min_rating"] is not None and (
        asset["rating"] is None or asset["rating"] < filters["min_rating"]
    ):
        return False
    if filters["tags"] is not None and not set(filters["tags"]).issubset(asset["tags"]):
        return False
    query = filters["query"]
    if query and query not in _searchable_text(asset):
        return False
    return True


def _searchable_text(asset: dict[str, Any]) -> str:
    values = [
        asset["filename"],
        asset.get("workflow_name") or "",
        asset["prompt_text"],
        asset["notes"],
        " ".join(asset["tags"]),
        " ".join(asset["model_references"]),
    ]
    return " ".join(values).casefold()


def _asset_from_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    tags = _json_list(data.get("tags_json"))
    model_references = _json_list(data.get("model_references_json"))
    return {
        "asset_id": str(data["asset_id"]),
        "output_id": str(data["output_id"]),
        "run_id": str(data["run_id"]),
        "workflow_name": data.get("workflow_name"),
        "status": str(data["status"]),
        "prompt_text": str(data.get("prompt_text") or ""),
        "model_references": model_references,
        "path": str(data["path"]),
        "filename": str(data["filename"]),
        "type": str(data["type"]),
        "subfolder": str(data.get("subfolder") or ""),
        "size_bytes": int(data["size_bytes"]),
        "modified_time": float(data["modified_time"]),
        "content_hash": str(data.get("content_hash") or ""),
        "sidecar_path": data.get("sidecar_path"),
        "thumbnail_path": data.get("thumbnail_path"),
        "thumbnail_status": str(data.get("thumbnail_status") or "not_supported"),
        "tags": tags,
        "rating": data.get("rating"),
        "favorite": bool(data.get("favorite")),
        "notes": str(data.get("notes") or ""),
        "indexed_at": str(data["indexed_at"]),
        "updated_at": str(data["updated_at"]),
    }


def _safe_asset_id(value: str) -> str:
    if not isinstance(value, str) or not ASSET_ID_PATTERN.fullmatch(value):
        raise ValueError("asset_id must be a 64-character lowercase hex identifier")
    return value


def _normalize_tags(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > TAG_MAX_COUNT:
        raise ValueError("tags must be a list with at most 40 entries")
    tags: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("tags must contain strings")
        tag = _clean_text(item, "")
        if not tag or len(tag) > TAG_MAX_LENGTH:
            raise ValueError("tags must be non-empty strings up to 40 characters")
        if tag not in tags:
            tags.append(tag)
    return sorted(tags)


def _normalize_rating(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValueError("rating must be an integer from 1 to 5")
    return value


def _normalize_favorite(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("favorite must be a boolean")
    return value


def _normalize_notes(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("notes must be a string")
    return _clean_text(value, "")


def _clean_text(value: Any, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, (str, int, float, bool)):
        return default
    text = " ".join(str(value).split())
    if not text:
        return default
    if len(text) > TEXT_MAX_LENGTH:
        return text[: TEXT_MAX_LENGTH - 3].rstrip() + "..."
    return text


def _json_list(value: Any) -> list[str]:
    try:
        loaded = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return sorted(str(item) for item in loaded if isinstance(item, str))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
