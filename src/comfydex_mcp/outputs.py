from __future__ import annotations

import os
import stat
import time
from pathlib import Path
from typing import Any

from .paths import is_redirected_path


def _inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _safe_lstat(path: Path, base: Path) -> os.stat_result | None:
    if is_redirected_path(path) or not _inside(path, base):
        return None
    try:
        return path.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return None


def _iter_real_files(directory: Path, base: Path) -> list[tuple[Path, os.stat_result]]:
    directory_stat = _safe_lstat(directory, base)
    if directory_stat is None or not stat.S_ISDIR(directory_stat.st_mode):
        return []

    files: list[tuple[Path, os.stat_result]] = []
    try:
        entries = sorted(directory.iterdir(), key=lambda path: str(path))
    except OSError:
        return files

    for entry in entries:
        entry_stat = _safe_lstat(entry, base)
        if entry_stat is None:
            continue
        if stat.S_ISDIR(entry_stat.st_mode):
            files.extend(_iter_real_files(entry, base))
        elif stat.S_ISREG(entry_stat.st_mode):
            files.append((entry, entry_stat))
    return files


def _output_type(path: Path, outputs_dir: Path) -> str:
    relative = path.resolve().relative_to(outputs_dir.resolve())
    return relative.parts[0] if len(relative.parts) > 1 else "output"


def list_outputs(runs_dir: Path) -> list[dict[str, Any]]:
    base = runs_dir.resolve()
    runs_stat = _safe_lstat(runs_dir, base)
    if runs_stat is None or not stat.S_ISDIR(runs_stat.st_mode):
        return []

    rows: list[dict[str, Any]] = []
    try:
        run_dirs = sorted(runs_dir.iterdir(), key=lambda path: str(path))
    except OSError:
        return rows

    for run_dir in run_dirs:
        run_stat = _safe_lstat(run_dir, base)
        if run_stat is None or not stat.S_ISDIR(run_stat.st_mode):
            continue

        outputs_dir = run_dir / "outputs"
        for output, output_stat in _iter_real_files(outputs_dir, base):
            if not _inside(output, base) or is_redirected_path(output):
                continue
            rows.append(
                {
                    "run_id": run_dir.name,
                    "path": str(output.resolve()),
                    "filename": output.name,
                    "size": output_stat.st_size,
                    "modified_time": output_stat.st_mtime,
                    "type": _output_type(output, outputs_dir),
                }
            )

    return rows


def _safe_delete_path(path: Path, base: Path) -> tuple[Path | None, str | None]:
    if not _inside(path, base):
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
    if is_redirected_path(path) or not _inside(path, base):
        return None, "redirected"
    return path, None


def cleanup_outputs(
    runs_dir: Path,
    confirm: bool = False,
    failed_run_ids: list[str] | None = None,
    older_than_seconds: int | None = None,
) -> dict[str, Any]:
    candidates = list_outputs(runs_dir)

    if failed_run_ids is not None:
        failed_ids = set(failed_run_ids)
        candidates = [row for row in candidates if row["run_id"] in failed_ids]

    if older_than_seconds is not None:
        cutoff = time.time() - older_than_seconds
        candidates = [row for row in candidates if row["modified_time"] < cutoff]

    deleted: list[str] = []
    skipped: list[dict[str, Any]] = []
    if confirm:
        base = runs_dir.resolve()
        for row in candidates:
            path = Path(row["path"])
            delete_path, reason = _safe_delete_path(path, base)
            if delete_path is None:
                skipped.append({**row, "reason": reason})
                continue
            try:
                delete_path.unlink()
            except OSError:
                skipped.append({**row, "reason": "delete_failed"})
                continue
            deleted.append(str(delete_path.resolve()))

    return {
        "dry_run": not confirm,
        "candidates": candidates,
        "deleted": deleted,
        "skipped": skipped,
    }
