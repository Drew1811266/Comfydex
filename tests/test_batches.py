from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from comfydex_mcp.batches import (
    create_batch_record,
    read_batch_record,
    update_batch_run,
    variation_to_operations,
)


def test_create_batch_record_writes_queued_runs(tmp_path: Path):
    now = datetime(2026, 6, 4, 1, 2, 3, tzinfo=timezone.utc)

    record = create_batch_record(
        tmp_path,
        "Night Batch!",
        "source.json",
        [
            {"node_id": "1", "inputs": {"seed": 42}},
            {"changes": [{"op": "set_input", "node_id": "2", "input": "cfg", "value": 7}]},
        ],
        now=now,
    )

    assert record["batch_id"] == "2026-06-04T01-02-03_night-batch"
    assert record["label"] == "Night Batch!"
    assert record["workflow_name"] == "source.json"
    assert record["status"] == "queued"
    assert record["runs"] == [
        {
            "index": 0,
            "parameters": {"node_id": "1", "inputs": {"seed": 42}},
            "status": "queued",
            "run_id": None,
        },
        {
            "index": 1,
            "parameters": {
                "changes": [
                    {"op": "set_input", "node_id": "2", "input": "cfg", "value": 7}
                ]
            },
            "status": "queued",
            "run_id": None,
        },
    ]
    assert (tmp_path / ".batches" / record["batch_id"] / "batch.json").is_file()
    assert read_batch_record(tmp_path, record["batch_id"]) == record


def test_create_batch_record_avoids_same_second_label_collisions(tmp_path: Path):
    now = datetime(2026, 6, 4, 1, 2, 3, tzinfo=timezone.utc)

    first = create_batch_record(tmp_path, "Same", "a.json", [{"node_id": "1", "inputs": {"seed": 1}}], now=now)
    second = create_batch_record(tmp_path, "Same", "b.json", [{"node_id": "1", "inputs": {"seed": 2}}], now=now)

    assert first["batch_id"] == "2026-06-04T01-02-03_same"
    assert second["batch_id"] == "2026-06-04T01-02-03_same-2"
    assert read_batch_record(tmp_path, first["batch_id"])["workflow_name"] == "a.json"
    assert read_batch_record(tmp_path, second["batch_id"])["workflow_name"] == "b.json"


@pytest.mark.parametrize("batch_id", ["../escape", "..\\escape", "/escape", "bad:name"])
def test_read_batch_record_rejects_traversal(tmp_path: Path, batch_id: str):
    with pytest.raises(ValueError, match="batch_id"):
        read_batch_record(tmp_path, batch_id)


def test_update_batch_run_summarizes_terminal_statuses(tmp_path: Path):
    now = datetime(2026, 6, 4, 1, 2, 3, tzinfo=timezone.utc)
    record = create_batch_record(
        tmp_path,
        "Batch",
        "source.json",
        [
            {"node_id": "1", "inputs": {"seed": 1}},
            {"node_id": "1", "inputs": {"seed": 2}},
        ],
        now=now,
    )

    partial = update_batch_run(tmp_path, record["batch_id"], 0, None, "failed")
    assert partial["status"] == "partial"
    assert partial["runs"][0]["status"] == "failed"

    failed = update_batch_run(tmp_path, record["batch_id"], 1, None, "failed")
    assert failed["status"] == "failed"

    record = create_batch_record(
        tmp_path,
        "Complete",
        "source.json",
        [
            {"node_id": "1", "inputs": {"seed": 3}},
            {"node_id": "1", "inputs": {"seed": 4}},
        ],
        now=now,
    )
    started = update_batch_run(tmp_path, record["batch_id"], 0, "run-a", "completed")
    assert started["status"] == "running"

    completed = update_batch_run(tmp_path, record["batch_id"], 1, "run-b", "completed")

    assert completed["status"] == "completed"
    assert [run["run_id"] for run in completed["runs"]] == ["run-a", "run-b"]


def test_update_batch_run_reports_running_for_submitted_queued_runs(tmp_path: Path):
    record = create_batch_record(
        tmp_path,
        "Queued",
        "source.json",
        [
            {"node_id": "1", "inputs": {"seed": 1}},
            {"node_id": "1", "inputs": {"seed": 2}},
        ],
        now=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )

    updated = update_batch_run(tmp_path, record["batch_id"], 0, "run-a", "queued")

    assert updated["status"] == "running"
    assert updated["runs"][0]["status"] == "queued"
    assert updated["runs"][0]["run_id"] == "run-a"


def test_update_batch_run_reports_running_when_any_run_is_running(tmp_path: Path):
    record = create_batch_record(
        tmp_path,
        "Running",
        "source.json",
        [
            {"node_id": "1", "inputs": {"seed": 1}},
            {"node_id": "1", "inputs": {"seed": 2}},
        ],
        now=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )

    updated = update_batch_run(tmp_path, record["batch_id"], 0, "run-a", "running")

    assert updated["status"] == "running"
    assert updated["runs"][0]["run_id"] == "run-a"


def test_update_batch_run_records_error_text(tmp_path: Path):
    record = create_batch_record(
        tmp_path,
        "Error",
        "source.json",
        [{"node_id": "1", "inputs": {"seed": 1}}],
        now=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )

    updated = update_batch_run(
        tmp_path,
        record["batch_id"],
        0,
        "run-a",
        "failed",
        error="submit exploded",
    )

    assert updated["runs"][0]["status"] == "failed"
    assert updated["runs"][0]["run_id"] == "run-a"
    assert updated["runs"][0]["error"] == "submit exploded"


def test_update_batch_run_rejects_out_of_range_index_and_unsupported_status(tmp_path: Path):
    record = create_batch_record(
        tmp_path,
        "Batch",
        "source.json",
        [{"node_id": "1", "inputs": {"seed": 1}}],
        now=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="index"):
        update_batch_run(tmp_path, record["batch_id"], 2, None, "failed")
    with pytest.raises(ValueError, match="unsupported"):
        update_batch_run(tmp_path, record["batch_id"], 0, None, "cancelled")


def test_read_and_write_reject_redirected_batch_json(monkeypatch, tmp_path: Path):
    record = create_batch_record(
        tmp_path,
        "Safe",
        "source.json",
        [{"node_id": "1", "inputs": {"seed": 1}}],
        now=datetime(2026, 6, 4, tzinfo=timezone.utc),
    )
    batch_json = tmp_path / ".batches" / record["batch_id"] / "batch.json"
    original_text = batch_json.read_text(encoding="utf-8")

    def fake_is_symlink(path: Path):
        return path == batch_json

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(ValueError, match="batch.json"):
        read_batch_record(tmp_path, record["batch_id"])
    with pytest.raises(ValueError, match="batch.json"):
        update_batch_run(tmp_path, record["batch_id"], 0, "run-a", "failed")

    assert batch_json.read_text(encoding="utf-8") == original_text
    assert json.loads(original_text)["runs"][0]["run_id"] is None


def test_variation_to_operations_sorts_node_inputs():
    operations = variation_to_operations(
        {"node_id": "1", "inputs": {"steps": 20, "cfg": 7, "seed": 42}}
    )

    assert operations == [
        {"op": "set_input", "node_id": "1", "input": "cfg", "value": 7},
        {"op": "set_input", "node_id": "1", "input": "seed", "value": 42},
        {"op": "set_input", "node_id": "1", "input": "steps", "value": 20},
    ]


def test_variation_to_operations_normalizes_changes():
    operations = variation_to_operations(
        {
            "changes": [
                {"op": "set_input", "node_id": 1, "input": "seed", "value": 42},
                {"op": "set_input", "node_id": "2", "input": "cfg", "value": 7},
            ]
        }
    )

    assert operations == [
        {"op": "set_input", "node_id": "1", "input": "seed", "value": 42},
        {"op": "set_input", "node_id": "2", "input": "cfg", "value": 7},
    ]


@pytest.mark.parametrize(
    "variation",
    [
        {},
        {"node_id": "1", "inputs": {}},
        {"node_id": "", "inputs": {"seed": 1}},
        {"node_id": "1", "inputs": {1: "bad"}},
        {"node_id": "1", "inputs": {"seed": 1}, "extra": True},
        {"changes": []},
        {"changes": [{"op": "remove_input", "node_id": "1", "input": "seed"}]},
        {"changes": [{"op": "set_input", "node_id": "1", "input": "seed"}]},
        {
            "changes": [
                {
                    "op": "set_input",
                    "node_id": "1",
                    "input": "seed",
                    "value": 1,
                    "extra": True,
                }
            ]
        },
    ],
)
def test_variation_to_operations_rejects_malformed_variations(variation: dict):
    with pytest.raises(ValueError):
        variation_to_operations(variation)
