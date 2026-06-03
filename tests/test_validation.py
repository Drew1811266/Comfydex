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


def test_validate_api_workflow_reports_invalid_class_type_without_raising():
    result = validate_api_workflow(
        {"1": {"class_type": ["SaveImage"], "inputs": {}}},
        OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["errors"][0]["reason"] == "invalid_class_type"


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


def test_validate_api_workflow_reports_invalid_output_slot():
    object_info = {
        "Source": {"input": {"required": {}}, "output": ["IMAGE"]},
        "SaveImage": {"input": {"required": {"images": ("IMAGE",)}}},
    }

    negative_slot = validate_api_workflow(
        {
            "1": {"class_type": "Source", "inputs": {}},
            "2": {"class_type": "SaveImage", "inputs": {"images": ["1", -1]}},
        },
        object_info,
    )
    out_of_range_slot = validate_api_workflow(
        {
            "1": {"class_type": "Source", "inputs": {}},
            "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 99]}},
        },
        object_info,
    )

    assert negative_slot["status"] == "invalid"
    assert any(
        error["reason"] == "invalid_output_slot"
        for error in negative_slot["errors"]
    )
    assert out_of_range_slot["status"] == "invalid"
    assert any(
        error["reason"] == "invalid_output_slot"
        for error in out_of_range_slot["errors"]
    )


def test_validate_api_workflow_reports_malformed_link_reference():
    object_info = {
        "Source": {"input": {"required": {}}, "output": ["IMAGE"]},
        "SaveImage": {"input": {"required": {"images": ("IMAGE",)}}},
    }

    malformed_values = ([1, 0], ["1", "bad"], ["1", True])

    for malformed_value in malformed_values:
        result = validate_api_workflow(
            {
                "1": {"class_type": "Source", "inputs": {}},
                "2": {
                    "class_type": "SaveImage",
                    "inputs": {"images": malformed_value},
                },
            },
            object_info,
        )

        assert result["status"] == "invalid"
        assert any(
            error["reason"] == "invalid_link_reference"
            and error["input"] == "images"
            for error in result["errors"]
        )


def test_validate_api_workflow_reports_non_link_value_for_link_input():
    object_info = {
        "Source": {"input": {"required": {}}, "output": ["IMAGE"]},
        "SaveImage": {"input": {"required": {"images": ("IMAGE",)}}},
    }

    malformed_values = ("not-a-link", 123, {"node": "1"})

    for malformed_value in malformed_values:
        result = validate_api_workflow(
            {
                "1": {"class_type": "Source", "inputs": {}},
                "2": {
                    "class_type": "SaveImage",
                    "inputs": {"images": malformed_value},
                },
            },
            object_info,
        )

        assert result["status"] == "invalid"
        assert any(
            error["reason"] == "invalid_link_reference"
            and error["input"] == "images"
            for error in result["errors"]
        )


def test_validate_api_workflow_reports_invalid_widget_literal_type():
    object_info = {
        "Counter": {
            "input": {
                "required": {
                    "steps": ("INT",),
                    "cfg": ("FLOAT",),
                    "enabled": ("BOOL",),
                    "label": ("STRING",),
                }
            }
        }
    }
    workflow = {
        "1": {
            "class_type": "Counter",
            "inputs": {
                "steps": "wide",
                "cfg": "strong",
                "enabled": "yes",
                "label": {"text": "bad"},
            },
        }
    }

    result = validate_api_workflow(workflow, object_info)

    assert result["status"] == "invalid"
    assert {
        (error["input"], error["reason"])
        for error in result["errors"]
    } == {
        ("steps", "invalid_input_value"),
        ("cfg", "invalid_input_value"),
        ("enabled", "invalid_input_value"),
        ("label", "invalid_input_value"),
    }


def test_validate_api_workflow_accepts_valid_widget_literals_and_links():
    object_info = {
        "IntSource": {"input": {"required": {}}, "output": ["INT"]},
        "Counter": {
            "input": {
                "required": {
                    "steps": ("INT",),
                    "cfg": ("FLOAT",),
                    "enabled": ("BOOLEAN",),
                    "label": ("STRING",),
                }
            }
        },
    }
    workflow = {
        "1": {"class_type": "IntSource", "inputs": {}},
        "2": {
            "class_type": "Counter",
            "inputs": {
                "steps": ["1", 0],
                "cfg": 7.0,
                "enabled": True,
                "label": "ok",
            },
        },
    }

    result = validate_api_workflow(workflow, object_info)

    assert result["status"] == "valid"


def test_validate_api_workflow_reports_link_type_mismatch():
    object_info = {
        "ModelSource": {"input": {"required": {}}, "output": ["MODEL"]},
        "SaveImage": {"input": {"required": {"images": ("IMAGE",)}}},
    }
    workflow = {
        "1": {"class_type": "ModelSource", "inputs": {}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0]}},
    }

    result = validate_api_workflow(workflow, object_info)

    assert result["status"] == "invalid"
    assert any(
        error["reason"] == "link_type_mismatch"
        and error["source_type"] == "MODEL"
        and error["target_types"] == ["IMAGE"]
        for error in result["errors"]
    )


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
