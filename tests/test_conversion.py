from pathlib import Path

import pytest

from comfydex_mcp.conversion import (
    convert_ui_to_api,
    explain_conversion_gaps,
    save_conversion_report,
)


OBJECT_INFO = {
    "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ("STRING",)}}},
    "SaveImage": {
        "input": {
            "required": {"images": ("IMAGE",)},
            "optional": {"filename_prefix": ("STRING",)},
        }
    },
}


def test_convert_ui_to_api_maps_widgets_and_links():
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets_values": ["model.safetensors"],
            },
            {"id": 2, "type": "SaveImage", "widgets_values": ["ComfyUI"]},
        ],
        "links": [[7, 1, 0, 2, 0, "IMAGE"]],
    }

    result = convert_ui_to_api(ui, OBJECT_INFO, "sample.ui.json", "sample.api.json")

    assert result["report"]["status"] == "converted"
    assert result["workflow"]["1"]["inputs"]["ckpt_name"] == "model.safetensors"
    assert result["workflow"]["2"]["inputs"]["images"] == ["1", 0]


def test_convert_ui_to_api_reports_missing_object_info_without_fake_workflow():
    ui = {"nodes": [{"id": 1, "type": "CustomNode"}], "links": []}

    result = convert_ui_to_api(ui, OBJECT_INFO, "bad.ui.json", "bad.api.json")

    assert result["workflow"] is None
    assert result["report"]["status"] == "failed"
    assert result["report"]["gaps"][0]["reason"] == "missing_object_info"


def test_save_conversion_report_writes_reports_directory(tmp_path: Path):
    report = {
        "source_workflow": "a.ui.json",
        "target_workflow": "a.api.json",
        "status": "failed",
        "gaps": [],
    }
    path = save_conversion_report(tmp_path, "a.ui.json", report)

    assert path == tmp_path / ".reports" / "a.ui.conversion.json"
    assert path.exists()


def test_explain_conversion_gaps_returns_text_and_gaps():
    report = {
        "status": "partial",
        "gaps": [
            {
                "node_id": "7",
                "node_type": "CustomNode",
                "reason": "missing_object_info",
            }
        ],
    }

    result = explain_conversion_gaps(report)

    assert result["gap_count"] == 1
    assert "CustomNode" in result["summary"]


def test_convert_ui_to_api_validation_failure_has_draft_without_workflow():
    ui = {"nodes": [{"id": 1, "type": "SaveImage", "widgets_values": []}], "links": []}

    result = convert_ui_to_api(ui, OBJECT_INFO, "missing.ui.json", "missing.api.json")

    assert result["workflow"] is None
    assert result["draft_workflow"]["1"]["class_type"] == "SaveImage"
    assert result["report"]["status"] == "partial"
    assert result["report"]["validation"]["status"] == "invalid"
    assert any(
        gap["reason"] == "validation_error"
        and gap["details"]["reason"] == "missing_required_input"
        for gap in result["report"]["gaps"]
    )


def test_convert_ui_to_api_does_not_fill_required_link_input_from_widget():
    ui = {
        "nodes": [
            {"id": 1, "type": "SaveImage", "widgets_values": ["ComfyUI"]},
        ],
        "links": [],
    }

    result = convert_ui_to_api(ui, OBJECT_INFO, "unsafe.ui.json", "unsafe.api.json")

    assert result["workflow"] is None
    assert result["report"]["status"] == "partial"
    assert any(
        gap["reason"] == "missing_required_link" and gap["input"] == "images"
        for gap in result["report"]["gaps"]
    )


def test_convert_ui_to_api_uses_ui_input_names_for_link_slots():
    object_info = {
        "ModelSource": {"input": {"required": {}}},
        "ConditioningSource": {"input": {"required": {}}},
        "KSampler": {
            "input": {
                "required": {
                    "model": ("MODEL",),
                    "seed": ("INT",),
                    "positive": ("CONDITIONING",),
                }
            }
        },
    }
    ui = {
        "nodes": [
            {"id": 1, "type": "ModelSource"},
            {"id": 2, "type": "ConditioningSource"},
            {
                "id": 3,
                "type": "KSampler",
                "inputs": [
                    {"name": "model"},
                    {"name": "positive"},
                    {"name": "seed"},
                ],
                "widgets_values": [123],
            },
        ],
        "links": [
            [10, 1, 0, 3, 0, "MODEL"],
            [11, 2, 0, 3, 1, "CONDITIONING"],
        ],
    }

    result = convert_ui_to_api(ui, object_info, "ksampler.ui.json", "ksampler.api.json")

    assert result["report"]["status"] == "converted"
    assert result["workflow"]["3"]["inputs"]["model"] == ["1", 0]
    assert result["workflow"]["3"]["inputs"]["positive"] == ["2", 0]
    assert result["workflow"]["3"]["inputs"]["seed"] == 123


def test_convert_ui_to_api_rejects_malformed_source_slot():
    ui = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets_values": ["model.safetensors"],
            },
            {"id": 2, "type": "SaveImage", "widgets_values": []},
        ],
        "links": [[7, 1, "bad", 2, 0, "IMAGE"]],
    }

    result = convert_ui_to_api(ui, OBJECT_INFO, "bad-link.ui.json", "bad-link.api.json")

    assert result["workflow"] is None
    assert result["report"]["status"] == "partial"
    assert any(gap["reason"] == "malformed_link" for gap in result["report"]["gaps"])


def test_convert_ui_to_api_consumes_widget_slot_when_widget_input_is_linked():
    object_info = {
        "IntSource": {"input": {"required": {}}, "output": ["INT"]},
        "Counter": {
            "input": {
                "required": {
                    "seed": ("INT",),
                    "steps": ("INT",),
                }
            }
        },
    }
    ui = {
        "nodes": [
            {"id": 1, "type": "IntSource"},
            {
                "id": 2,
                "type": "Counter",
                "inputs": [{"name": "seed"}, {"name": "steps"}],
                "widgets_values": [111, 222],
            },
        ],
        "links": [[7, 1, 0, 2, 0, "INT"]],
    }

    result = convert_ui_to_api(ui, object_info, "linked-widget.ui.json", "api.json")

    assert result["report"]["status"] == "converted"
    assert result["workflow"]["2"]["inputs"]["seed"] == ["1", 0]
    assert result["workflow"]["2"]["inputs"]["steps"] == 222


def test_save_conversion_report_rejects_traversal_source_names(tmp_path: Path):
    report = {"status": "failed", "gaps": []}

    with pytest.raises(ValueError, match="simple .json filename"):
        save_conversion_report(tmp_path, "../a.ui.json", report)
