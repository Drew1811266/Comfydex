from comfydex_mcp.validation import validate_api_workflow


OBJECT_INFO = {
    "SaveImage": {"input": {"required": {"images": ("IMAGE",)}}},
    "KSampler": {"input": {"required": {"model": ("MODEL",), "seed": ("INT",)}}},
}


def test_validate_api_workflow_passes_valid_links():
    workflow = {
        "1": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "seed": 1}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    result = validate_api_workflow(workflow, OBJECT_INFO)

    assert result["status"] == "valid"
    assert result["errors"] == []


def test_validate_api_workflow_reports_missing_node_type():
    result = validate_api_workflow(
        {"1": {"class_type": "MissingNode", "inputs": {}}},
        OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "missing_object_info"


def test_validate_api_workflow_reports_missing_required_input():
    result = validate_api_workflow(
        {"1": {"class_type": "SaveImage", "inputs": {}}},
        OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["errors"][0]["input"] == "images"


def test_validate_api_workflow_reports_broken_link_reference():
    result = validate_api_workflow(
        {"1": {"class_type": "SaveImage", "inputs": {"images": ["99", 0]}}},
        OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "broken_link"


def test_validate_api_workflow_rejects_empty_workflow():
    result = validate_api_workflow({}, OBJECT_INFO)

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "workflow_not_object"
    assert result["nodes_checked"] == 0


def test_validate_api_workflow_warns_when_no_probable_output_node():
    result = validate_api_workflow(
        {"1": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 1}}},
        OBJECT_INFO,
    )

    assert result["status"] == "valid"
    assert result["errors"] == []
    assert result["warnings"] == [{"reason": "no_probable_output_node"}]
