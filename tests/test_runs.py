import json
from datetime import datetime, timezone
from pathlib import Path

from comfydex_mcp.runs import (
    append_event,
    create_run,
    list_runs,
    read_run,
    register_outputs,
    update_status,
)


def test_create_run_writes_record_and_workflow_snapshot(tmp_path: Path):
    run = create_run(
        runs_dir=tmp_path,
        workflow_name="text2img.json",
        workflow_json={"1": {"class_type": "SaveImage", "inputs": {}}},
        base_url="http://127.0.0.1:8188",
        prompt_id="abc123",
        client_id="client-1",
        label="text2img",
        now=datetime(2026, 6, 2, 2, 30, tzinfo=timezone.utc),
    )

    assert run["run_id"] == "2026-06-02T02-30-00_text2img"
    assert run["client_id"] == "client-1"
    assert (tmp_path / run["run_id"] / "run.json").is_file()
    assert (tmp_path / run["run_id"] / "workflow.json").is_file()
    assert (tmp_path / run["run_id"] / "outputs").is_dir()


def test_update_status_and_append_event(tmp_path: Path):
    run = create_run(tmp_path, "wf.json", {}, "http://127.0.0.1:8188", "p1", now=datetime(2026, 6, 2, tzinfo=timezone.utc))

    update_status(tmp_path, run["run_id"], "running")
    append_event(tmp_path, run["run_id"], {"type": "executing", "data": {"node": "3"}})
    loaded = read_run(tmp_path, run["run_id"])

    assert loaded["status"] == "running"
    assert loaded["events"][0]["type"] == "executing"


def test_create_run_avoids_same_second_label_collisions(tmp_path: Path):
    now = datetime(2026, 6, 2, 2, 30, tzinfo=timezone.utc)
    first = create_run(tmp_path, "first.json", {"first": True}, "http://127.0.0.1:8188", "p1", label="same", now=now)
    second = create_run(tmp_path, "second.json", {"second": True}, "http://127.0.0.1:8188", "p2", label="same", now=now)

    assert first["run_id"] == "2026-06-02T02-30-00_same"
    assert second["run_id"] == "2026-06-02T02-30-00_same-2"
    assert first["run_id"] != second["run_id"]
    assert read_run(tmp_path, first["run_id"])["prompt_id"] == "p1"
    assert read_run(tmp_path, second["run_id"])["prompt_id"] == "p2"
    assert json.loads((tmp_path / first["run_id"] / "workflow.json").read_text(encoding="utf-8")) == {"first": True}
    assert json.loads((tmp_path / second["run_id"] / "workflow.json").read_text(encoding="utf-8")) == {"second": True}


def test_register_outputs_updates_run(tmp_path: Path):
    run = create_run(tmp_path, "wf.json", {}, "http://127.0.0.1:8188", "p1", now=datetime(2026, 6, 2, tzinfo=timezone.utc))

    register_outputs(
        tmp_path,
        run["run_id"],
        [{"filename": "image.png", "subfolder": "", "type": "output", "downloaded_path": "outputs/image.png"}],
    )

    loaded = read_run(tmp_path, run["run_id"])
    assert loaded["outputs"][0]["filename"] == "image.png"


def test_list_runs_sorts_by_updated_time(tmp_path: Path):
    first = create_run(tmp_path, "a.json", {}, "http://127.0.0.1:8188", "a", now=datetime(2026, 6, 2, 1, tzinfo=timezone.utc))
    second = create_run(tmp_path, "b.json", {}, "http://127.0.0.1:8188", "b", now=datetime(2026, 6, 2, 2, tzinfo=timezone.utc))

    rows = list_runs(tmp_path)

    assert [row["run_id"] for row in rows] == [second["run_id"], first["run_id"]]
