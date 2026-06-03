from comfydex_mcp.ui_workflows import (
    classify_workflow_payload,
    summarize_import_readiness,
)


def test_classify_workflow_payload_identifies_ui_with_evidence():
    result = classify_workflow_payload(
        {"nodes": [{"id": 1, "type": "SaveImage"}], "links": []}
    )

    assert result["kind"] == "ui"
    assert "nodes is a list" in result["evidence"]
    assert "links is a list" in result["evidence"]


def test_classify_workflow_payload_identifies_api_with_evidence():
    result = classify_workflow_payload({"1": {"class_type": "SaveImage", "inputs": {}}})

    assert result["kind"] == "api"
    assert result["evidence"] == ["node values include class_type"]


def test_classify_workflow_payload_reports_unknown_with_evidence():
    result = classify_workflow_payload({"nodes": {"1": {"type": "SaveImage"}}})

    assert result["kind"] == "unknown"
    assert result["evidence"]


def test_summarize_import_readiness_reports_ui_counts_with_object_info():
    result = summarize_import_readiness(
        {
            "nodes": [
                {"id": 1, "type": "SaveImage"},
                {"id": 2, "type": "CustomNode"},
                {"id": 3, "type": "SaveImage"},
            ],
            "links": [],
        },
        object_info={"SaveImage": {"input": {"required": {"images": ("IMAGE",)}}}},
    )

    assert result == {
        "kind": "ui",
        "nodes_total": 3,
        "known_node_types": ["SaveImage"],
        "unknown_node_types": ["CustomNode"],
        "node_types": {"CustomNode": 1, "SaveImage": 2},
        "conversion_ready": False,
    }


def test_summarize_import_readiness_does_not_mark_unknown_without_object_info():
    result = summarize_import_readiness(
        {
            "nodes": [
                {"id": 1, "type": "SaveImage"},
                {"id": 2, "type": "CustomNode"},
            ],
            "links": [],
        }
    )

    assert result["kind"] == "ui"
    assert result["nodes_total"] == 2
    assert result["known_node_types"] == []
    assert result["unknown_node_types"] == []
    assert result["node_types"] == {"CustomNode": 1, "SaveImage": 1}
    assert result["conversion_ready"] is True
