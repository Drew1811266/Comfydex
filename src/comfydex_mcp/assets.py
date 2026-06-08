from __future__ import annotations

import json
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core.database import migrate_project, open_database
from .core.project import ProjectContext
from .core.store import get_asset_row, list_asset_rows, update_asset_annotation
from .paths import ensure_directory, is_redirected_path

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


def write_asset_sidecars(
    context: ProjectContext,
    asset_ids: list[str] | None = None,
) -> dict[str, Any]:
    assets = _selected_assets(context, asset_ids=asset_ids)
    sidecar_dir = _sidecar_dir(context)
    written: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for asset in assets:
        path = sidecar_dir / f"{asset['asset_id']}.json"
        try:
            _write_json_atomic(path, _sidecar_payload(asset))
        except OSError as exc:
            errors.append(
                {
                    "asset_id": asset["asset_id"],
                    "path": str(path),
                    "message": f"{exc.__class__.__name__}: {exc}",
                }
            )
            continue
        _record_sidecar_path(context, asset["asset_id"], path)
        written.append({"asset_id": asset["asset_id"], "path": str(path)})

    return {
        "status": "completed" if not errors else "completed_with_errors",
        "written_count": len(written),
        "written": written,
        "errors": errors,
    }


def plan_asset_cleanup(
    context: ProjectContext,
    filters: dict[str, Any] | None = None,
    asset_ids: list[str] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    assets = _selected_assets(context, filters=filters, asset_ids=asset_ids)
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    deleted: list[str] = []
    base = context.runs_dir.resolve()

    for asset in assets:
        delete_path, reason = _safe_delete_path(Path(asset["path"]), base)
        if delete_path is None:
            skipped.append({**asset, "reason": reason})
            continue
        candidates.append(asset)
        if not confirm:
            continue
        try:
            delete_path.unlink()
        except OSError:
            skipped.append({**asset, "reason": "delete_failed"})
            continue
        deleted.append(str(delete_path.resolve()))

    return {
        "dry_run": not confirm,
        "candidates": candidates,
        "deleted": deleted,
        "skipped": skipped,
    }


def export_asset_library_report(
    context: ProjectContext,
    filters: dict[str, Any] | None = None,
) -> dict[str, str]:
    result = search_assets(context, {**(filters or {}), "limit": MAX_LIMIT, "offset": 0})
    assets = result["assets"]
    favorite_count = sum(1 for asset in assets if asset["favorite"])
    rated = [asset["rating"] for asset in assets if asset["rating"] is not None]
    average_rating = sum(rated) / len(rated) if rated else 0
    lines = [
        "# Comfydex Asset Library Report",
        "",
        "## Summary",
        "",
        f"- Total assets: {result['total']}",
        f"- Assets in report: {len(assets)}",
        f"- Favorites: {favorite_count}",
        f"- Average rating: {average_rating:.2f}" if rated else "- Average rating: none",
        "",
        "## Assets",
        "",
        "| Filename | Workflow | Status | Rating | Favorite | Tags |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for asset in assets:
        lines.append(
            "| "
            + " | ".join(
                [
                    asset["filename"],
                    asset.get("workflow_name") or "",
                    asset["status"],
                    str(asset["rating"] or ""),
                    "favorite" if asset["favorite"] else "",
                    ", ".join(asset["tags"]),
                ]
            )
            + " |"
        )
    lines.append("")
    markdown = "\n".join(lines)
    report_dir = _report_dir(context)
    path = report_dir / "asset-library-report.md"
    _write_text_atomic(path, markdown)
    return {"path": str(path), "markdown": markdown}


def compare_assets(
    context: ProjectContext,
    left_asset_id: str,
    right_asset_id: str,
) -> dict[str, Any]:
    left = get_asset(context, left_asset_id)
    right = get_asset(context, right_asset_id)
    fields = {
        "status": (left["status"], right["status"]),
        "workflow_name": (left.get("workflow_name"), right.get("workflow_name")),
        "prompt_text": (left["prompt_text"], right["prompt_text"]),
        "model_references": (left["model_references"], right["model_references"]),
        "size_bytes": (left["size_bytes"], right["size_bytes"]),
        "tags": (left["tags"], right["tags"]),
        "rating": (left["rating"], right["rating"]),
        "favorite": (left["favorite"], right["favorite"]),
    }
    return {
        "left": left,
        "right": right,
        "differences": {
            name: {"left": values[0], "right": values[1], "changed": values[0] != values[1]}
            for name, values in fields.items()
        },
    }


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
    date_from = _normalize_date(filters.get("date_from"), "date_from")
    date_to = _normalize_date(filters.get("date_to"), "date_to")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("date_from must be earlier than or equal to date_to")
    return {
        "query": _clean_text(filters.get("query"), "").casefold(),
        "run_id": _clean_text(filters.get("run_id"), ""),
        "workflow_name": _clean_text(filters.get("workflow_name"), ""),
        "status": _clean_text(filters.get("status"), ""),
        "type": _clean_text(filters.get("type"), ""),
        "tags": tags,
        "favorite": favorite,
        "min_rating": min_rating,
        "date_from": date_from,
        "date_to": date_to,
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
    if (
        filters["date_from"] is not None
        and asset["modified_time"] < filters["date_from"]
    ):
        return False
    if filters["date_to"] is not None and asset["modified_time"] > filters["date_to"]:
        return False
    query = filters["query"]
    if query and query not in _searchable_text(asset):
        return False
    return True


def _selected_assets(
    context: ProjectContext,
    *,
    filters: dict[str, Any] | None = None,
    asset_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if asset_ids is not None:
        if not isinstance(asset_ids, list):
            raise ValueError("asset_ids must be a list")
        return [get_asset(context, _safe_asset_id(asset_id)) for asset_id in asset_ids]
    return search_assets(context, {**(filters or {}), "limit": MAX_LIMIT, "offset": 0})[
        "assets"
    ]


def _sidecar_dir(context: ProjectContext) -> Path:
    directory = ensure_directory(context.state_dir / "assets" / "sidecars")
    _require_safe_child_dir(directory, context.state_dir)
    return directory


def _report_dir(context: ProjectContext) -> Path:
    directory = ensure_directory(context.state_dir / "reports")
    _require_safe_child_dir(directory, context.state_dir)
    return directory


def _require_safe_child_dir(path: Path, base: Path) -> None:
    if is_redirected_path(path):
        raise ValueError("asset library path must not be redirected")
    try:
        path.resolve().relative_to(base.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("asset library path must stay inside the project state directory") from exc


def _sidecar_payload(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": asset["asset_id"],
        "output_id": asset["output_id"],
        "run_id": asset["run_id"],
        "workflow_name": asset.get("workflow_name"),
        "status": asset["status"],
        "path": asset["path"],
        "filename": asset["filename"],
        "type": asset["type"],
        "subfolder": asset["subfolder"],
        "size_bytes": asset["size_bytes"],
        "modified_time": asset["modified_time"],
        "content_hash": asset["content_hash"],
        "prompt_text": asset["prompt_text"],
        "model_references": asset["model_references"],
        "tags": asset["tags"],
        "rating": asset["rating"],
        "favorite": asset["favorite"],
        "notes": asset["notes"],
    }


def _record_sidecar_path(context: ProjectContext, asset_id: str, path: Path) -> None:
    with open_database(context.database_path) as db:
        update_asset_annotation(
            db,
            asset_id,
            {"sidecar_path": str(path), "updated_at": _now()},
        )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, text: str) -> None:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=path.parent,
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        if is_redirected_path(path):
            raise ValueError("asset library output path must not be redirected")
        path.resolve().relative_to(path.parent.resolve())
        tmp_path.replace(path)
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass


def _safe_delete_path(path: Path, base: Path) -> tuple[Path | None, str | None]:
    try:
        resolved = path.resolve()
        resolved.relative_to(base)
    except (OSError, RuntimeError, ValueError):
        return None, "escaped"
    if is_redirected_path(path):
        return None, "redirected"
    try:
        path_stat = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unreadable"
    if not stat.S_ISREG(path_stat.st_mode):
        return None, "not_file"
    if is_redirected_path(path):
        return None, "redirected"
    return resolved, None


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


def _normalize_date(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an ISO timestamp")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


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
