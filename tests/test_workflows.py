from pathlib import Path

import pytest

from comfydex_mcp.workflows import (
    classify_workflow,
    list_workflows,
    read_workflow,
    read_workflow_metadata,
    save_workflow,
    save_workflow_metadata,
    summarize_workflow,
    workflow_metadata,
    workflow_metadata_filename,
)


API_WORKFLOW = {
    "3": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "model.safetensors"},
    },
    "4": {
        "class_type": "SaveImage",
        "inputs": {"images": ["3", 0]},
    },
}


UI_WORKFLOW = {
    "last_node_id": 4,
    "nodes": [{"id": 3, "type": "CheckpointLoaderSimple"}],
    "links": [],
}


def test_classify_api_workflow():
    assert classify_workflow(API_WORKFLOW) == "api"


def test_classify_ui_workflow():
    assert classify_workflow(UI_WORKFLOW) == "ui"


def test_save_read_and_list_workflow(tmp_path: Path):
    save_workflow(tmp_path, "text2img.json", API_WORKFLOW)

    loaded = read_workflow(tmp_path, "text2img.json")
    listed = list_workflows(tmp_path)

    assert loaded["json"] == API_WORKFLOW
    assert loaded["kind"] == "api"
    assert listed[0]["name"] == "text2img.json"
    assert listed[0]["valid_json"] is True


def test_workflow_metadata_filename_uses_workflow_stem():
    assert workflow_metadata_filename("text2img.json") == "text2img.metadata.json"


def test_workflow_metadata_filename_rejects_nested_workflow_filename():
    with pytest.raises(ValueError, match="simple .json filename"):
        workflow_metadata_filename("../wf.json")


def test_workflow_metadata_defaults_manual_unknown_for_api_workflow():
    assert workflow_metadata("wf.json", API_WORKFLOW) == {
        "name": "wf.json",
        "kind": "api",
        "source": "manual",
        "submit_ready": True,
        "validation_status": "unknown",
    }


def test_manual_draft_workflow_remains_submit_ready(tmp_path: Path):
    save_workflow(tmp_path, "manual.draft.json", API_WORKFLOW)

    loaded = read_workflow(tmp_path, "manual.draft.json")

    assert loaded["metadata"]["source"] == "manual"
    assert loaded["metadata"]["submit_ready"] is True


def test_save_and_read_workflow_metadata_round_trip(tmp_path: Path):
    metadata = workflow_metadata(
        "wf.json",
        API_WORKFLOW,
        source="generated",
        validation_status="valid",
    )

    path = save_workflow_metadata(tmp_path, "wf.json", metadata)
    loaded = read_workflow_metadata(tmp_path, "wf.json", API_WORKFLOW)

    assert path == tmp_path / ".metadata" / "wf.metadata.json"
    assert loaded == {
        "name": "wf.json",
        "kind": "api",
        "source": "generated",
        "submit_ready": True,
        "validation_status": "valid",
    }


def test_save_workflow_metadata_rejects_auxiliary_dir_outside_workflows(
    monkeypatch,
    tmp_path: Path,
):
    workflows_dir = tmp_path / "workflows"
    external_dir = tmp_path / "external"
    workflows_dir.mkdir()
    external_dir.mkdir()
    original_resolve = Path.resolve

    def fake_resolve(path: Path, *args, **kwargs):
        if path == workflows_dir / ".metadata":
            return external_dir
        if path == workflows_dir / ".metadata" / "wf.metadata.json":
            return external_dir / "wf.metadata.json"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    with pytest.raises(ValueError, match="workflow path must stay inside workflows_dir"):
        save_workflow_metadata(
            workflows_dir,
            "wf.json",
            workflow_metadata("wf.json", API_WORKFLOW),
        )

    assert not (external_dir / "wf.metadata.json").exists()


def test_read_workflow_metadata_defaults_when_missing(tmp_path: Path):
    assert read_workflow_metadata(tmp_path, "wf.json", API_WORKFLOW) == {
        "name": "wf.json",
        "kind": "api",
        "source": "manual",
        "submit_ready": True,
        "validation_status": "unknown",
    }


def test_read_workflow_metadata_uses_current_payload_for_name_and_kind(tmp_path: Path):
    save_workflow_metadata(
        tmp_path,
        "wf.json",
        {
            "name": "stale.json",
            "kind": "ui",
            "source": "generated",
            "submit_ready": False,
            "validation_status": "invalid",
        },
    )

    loaded = read_workflow_metadata(tmp_path, "wf.json", API_WORKFLOW)

    assert loaded == {
        "name": "wf.json",
        "kind": "api",
        "source": "generated",
        "submit_ready": False,
        "validation_status": "invalid",
    }


def test_read_workflow_includes_metadata_fields(tmp_path: Path):
    save_workflow(tmp_path, "wf.json", API_WORKFLOW)

    loaded = read_workflow(tmp_path, "wf.json")

    assert loaded["metadata"] == {
        "name": "wf.json",
        "kind": "api",
        "source": "manual",
        "submit_ready": True,
        "validation_status": "unknown",
    }


def test_workflow_metadata_persists_source_and_validation_status(tmp_path: Path):
    save_workflow(
        tmp_path,
        "generated.json",
        API_WORKFLOW,
        source="generated",
        validation_status="valid",
    )

    loaded = read_workflow(tmp_path, "generated.json")

    assert loaded["metadata"]["source"] == "generated"
    assert loaded["metadata"]["validation_status"] == "valid"
    assert loaded["metadata"]["submit_ready"] is True


def test_read_workflow_uses_default_metadata_when_metadata_json_is_invalid(
    tmp_path: Path,
):
    save_workflow(tmp_path, "wf.json", API_WORKFLOW)
    (tmp_path / ".metadata" / "wf.metadata.json").write_text("{", encoding="utf-8")

    loaded = read_workflow(tmp_path, "wf.json")

    assert loaded["metadata"] == {
        "name": "wf.json",
        "kind": "api",
        "source": "manual",
        "submit_ready": True,
        "validation_status": "unknown",
    }


def test_draft_workflow_metadata_fails_closed_when_missing_or_corrupt(tmp_path: Path):
    save_workflow(
        tmp_path,
        "partial.api.converted-draft.json",
        API_WORKFLOW,
        source="converted",
        validation_status="partial",
    )
    metadata_path = tmp_path / ".metadata" / "partial.api.converted-draft.metadata.json"

    metadata_path.unlink()
    missing_metadata = read_workflow(
        tmp_path, "partial.api.converted-draft.json"
    )["metadata"]

    assert missing_metadata["source"] == "converted"
    assert missing_metadata["submit_ready"] is False

    metadata_path.write_text("{", encoding="utf-8")
    corrupt_metadata = read_workflow(
        tmp_path, "partial.api.converted-draft.json"
    )["metadata"]

    assert corrupt_metadata["source"] == "converted"
    assert corrupt_metadata["submit_ready"] is False


def test_read_workflow_ignores_metadata_fields_with_invalid_types(tmp_path: Path):
    save_workflow(tmp_path, "wf.json", API_WORKFLOW)
    save_workflow_metadata(
        tmp_path,
        "wf.json",
        {
            "source": ["generated"],
            "validation_status": {"status": "valid"},
            "submit_ready": "yes",
        },
    )

    loaded = read_workflow(tmp_path, "wf.json")

    assert loaded["metadata"] == {
        "name": "wf.json",
        "kind": "api",
        "source": "manual",
        "submit_ready": True,
        "validation_status": "unknown",
    }


def test_summarize_workflow_finds_node_types_and_models():
    summary = summarize_workflow(API_WORKFLOW)

    assert summary["node_count"] == 2
    assert summary["node_types"] == {
        "CheckpointLoaderSimple": 1,
        "SaveImage": 1,
    }
    assert summary["model_references"] == ["model.safetensors"]


def test_summarize_ui_workflow_counts_nodes_and_model_widgets():
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets_values": ["model.safetensors"],
            },
            {"id": 2, "type": "PreviewImage"},
        ],
        "links": [],
    }

    summary = summarize_workflow(workflow)

    assert summary["node_count"] == 2
    assert summary["node_types"] == {
        "CheckpointLoaderSimple": 1,
        "PreviewImage": 1,
    }
    assert summary["model_references"] == ["model.safetensors"]


def test_save_rejects_ui_workflow_when_api_required(tmp_path: Path):
    with pytest.raises(ValueError, match="API prompt JSON"):
        save_workflow(tmp_path, "ui.json", UI_WORKFLOW, require_api=True)
