from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from comfydex_mcp import outputs
from comfydex_mcp.outputs import cleanup_outputs, list_outputs


def _write_output(
    runs_dir: Path,
    run_id: str,
    relative_output: str,
    content: str = "x",
) -> Path:
    output = runs_dir / run_id / "outputs" / Path(relative_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    run_record = runs_dir / run_id / "run.json"
    run_record.write_text('{"run_id": "' + run_id + '"}\n', encoding="utf-8")
    return output


def _paths(rows: list[dict]) -> list[Path]:
    return [Path(row["path"]).resolve() for row in rows]


def _patch_redirects(monkeypatch, redirected: set[Path]) -> None:
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path: Path) -> bool:
        if path in redirected:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)


def _symlink_or_fake(link: Path, target: Path, redirected: set[Path]) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (NotImplementedError, OSError):
        if target.is_dir():
            link.mkdir(exist_ok=True)
            (link / "placeholder.png").write_text(
                "fake redirected output",
                encoding="utf-8",
            )
        else:
            link.write_text("fake redirected output", encoding="utf-8")
        redirected.add(link)


def test_list_outputs_lists_real_output_files_and_keeps_paths_inside_runs_dir(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    output = _write_output(runs_dir, "run-a", "output/nested/image.png", "abc")
    (runs_dir / "run-a" / "run.json").write_text("{}", encoding="utf-8")

    result = list_outputs(runs_dir)

    assert len(result) == 1
    row = result[0]
    assert row["run_id"] == "run-a"
    assert row["filename"] == "image.png"
    assert row["size"] == 3
    assert row["type"] == "output"
    assert isinstance(row["modified_time"], float)
    assert Path(row["path"]).resolve() == output.resolve()
    Path(row["path"]).resolve().relative_to(runs_dir.resolve())


def test_cleanup_outputs_dry_run_by_default_does_not_delete_candidates(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    output = _write_output(runs_dir, "run-a", "output/image.png")

    result = cleanup_outputs(runs_dir, confirm=False)

    assert result["dry_run"] is True
    assert _paths(result["candidates"]) == [output.resolve()]
    assert result["deleted"] == []
    assert output.exists()


def test_cleanup_outputs_confirmed_deletes_candidate(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    output = _write_output(runs_dir, "run-a", "output/image.png")

    result = cleanup_outputs(runs_dir, confirm=True)

    assert result["dry_run"] is False
    assert [Path(path).resolve() for path in result["deleted"]] == [output.resolve()]
    assert not output.exists()


def test_cleanup_outputs_older_than_seconds_only_selects_old_files(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    old_output = _write_output(runs_dir, "run-a", "output/old.png", "old")
    new_output = _write_output(runs_dir, "run-a", "output/new.png", "new")
    old_time = time.time() - 7200
    os.utime(old_output, (old_time, old_time))

    result = cleanup_outputs(runs_dir, older_than_seconds=3600)

    assert _paths(result["candidates"]) == [old_output.resolve()]
    assert old_output.exists()
    assert new_output.exists()


def test_cleanup_outputs_failed_run_ids_only_selects_specified_run_outputs(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    failed_output = _write_output(runs_dir, "failed-run", "output/image.png")
    other_output = _write_output(runs_dir, "completed-run", "output/image.png")

    result = cleanup_outputs(runs_dir, failed_run_ids=["failed-run"])

    assert _paths(result["candidates"]) == [failed_output.resolve()]
    assert failed_output.exists()
    assert other_output.exists()


def test_list_outputs_ignores_directories_without_safe_run_record(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    valid_output = _write_output(runs_dir, "run-a", "output/image.png")
    stray_output = runs_dir / "not-a-run" / "outputs" / "output" / "stray.png"
    stray_output.parent.mkdir(parents=True)
    stray_output.write_text("stray", encoding="utf-8")
    batch_output = runs_dir / ".batches" / "batch-a" / "outputs" / "output" / "batch.png"
    batch_output.parent.mkdir(parents=True)
    batch_output.write_text("batch", encoding="utf-8")

    result = list_outputs(runs_dir)

    assert _paths(result) == [valid_output.resolve()]
    assert stray_output.exists()
    assert batch_output.exists()


def test_cleanup_outputs_rejects_negative_or_bool_age_threshold(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    _write_output(runs_dir, "run-a", "output/image.png")

    for value in (-1, True, False):
        with pytest.raises(ValueError, match="older_than_seconds"):
            cleanup_outputs(runs_dir, confirm=True, older_than_seconds=value)


def test_redirected_output_file_or_directory_is_not_listed_or_deleted(
    monkeypatch,
    tmp_path: Path,
):
    runs_dir = tmp_path / "runs"
    real_output = _write_output(runs_dir, "run-a", "output/real.png", "real")
    external_file = tmp_path / "outside" / "secret.png"
    external_file.parent.mkdir()
    external_file.write_text("secret", encoding="utf-8")
    external_dir = tmp_path / "outside-dir"
    external_dir.mkdir()
    external_nested = external_dir / "nested.png"
    external_nested.write_text("nested", encoding="utf-8")

    redirected: set[Path] = set()
    link_file = runs_dir / "run-a" / "outputs" / "output" / "linked.png"
    link_dir = runs_dir / "run-a" / "outputs" / "linked-dir"
    _symlink_or_fake(link_file, external_file, redirected)
    _symlink_or_fake(link_dir, external_dir, redirected)
    _patch_redirects(monkeypatch, redirected)

    listed = list_outputs(runs_dir)
    result = cleanup_outputs(runs_dir, confirm=True)

    assert _paths(listed) == [real_output.resolve()]
    assert [Path(path).resolve() for path in result["deleted"]] == [
        real_output.resolve()
    ]
    assert not real_output.exists()
    assert external_file.exists()
    assert external_nested.exists()
    assert link_file.exists()
    assert link_dir.exists()


def test_cleanup_outputs_rechecks_candidate_before_delete_and_skips_redirected_path(
    monkeypatch,
    tmp_path: Path,
):
    runs_dir = tmp_path / "runs"
    candidate = _write_output(runs_dir, "run-a", "output/image.png")
    external_file = tmp_path / "outside" / "secret.png"
    external_file.parent.mkdir()
    external_file.write_text("secret", encoding="utf-8")
    redirected: set[Path] = set()
    _patch_redirects(monkeypatch, redirected)
    original_list_outputs = outputs.list_outputs

    def list_then_redirect(path: Path) -> list[dict]:
        rows = original_list_outputs(path)
        candidate.unlink()
        _symlink_or_fake(candidate, external_file, redirected)
        return rows

    monkeypatch.setattr(outputs, "list_outputs", list_then_redirect)

    result = outputs.cleanup_outputs(runs_dir, confirm=True)

    assert result["deleted"] == []
    assert [Path(row["path"]).resolve() for row in result["skipped"]] == [
        candidate.resolve()
    ]
    assert external_file.exists()
    assert candidate.exists()
