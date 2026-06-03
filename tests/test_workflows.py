from pathlib import Path

import pytest

from comfydex_mcp.workflows import (
    classify_workflow,
    list_workflows,
    read_workflow,
    save_workflow,
    summarize_workflow,
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
