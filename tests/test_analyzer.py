from comfydex_mcp.analyzer import analyze_workflow


def test_analyze_reports_missing_node_types():
    workflow = {
        "1": {"class_type": "KnownNode", "inputs": {}},
        "2": {"class_type": "MissingNode", "inputs": {"x": ["1", 0]}},
    }
    object_info = {"KnownNode": {"input": {"required": {}}}}

    result = analyze_workflow(workflow, object_info)

    assert result["missing_node_types"] == ["MissingNode"]
    assert result["links"] == [{"from_node": "1", "from_slot": 0, "to_node": "2", "input": "x"}]


def test_analyze_detects_required_input_issues():
    workflow = {
        "1": {"class_type": "KnownNode", "inputs": {"present": "value"}},
    }
    object_info = {
        "KnownNode": {
            "input": {
                "required": {
                    "present": ["STRING", {}],
                    "missing": ["STRING", {}],
                }
            }
        }
    }

    result = analyze_workflow(workflow, object_info)

    assert result["input_issues"] == [
        {"node_id": "1", "node_type": "KnownNode", "missing_input": "missing"}
    ]


def test_analyze_detects_potential_output_nodes():
    workflow = {
        "1": {"class_type": "KSampler", "inputs": {}},
        "9": {"class_type": "SaveImage", "inputs": {}},
    }

    result = analyze_workflow(workflow)

    assert result["potential_output_nodes"] == [{"node_id": "9", "node_type": "SaveImage"}]


def test_analyze_detects_output_nodes_from_object_info_metadata():
    workflow = {
        "9": {"class_type": "PreviewImage", "inputs": {}},
    }
    object_info = {"PreviewImage": {"output_node": True, "input": {"required": {}}}}

    result = analyze_workflow(workflow, object_info)

    assert result["potential_output_nodes"] == [{"node_id": "9", "node_type": "PreviewImage"}]


def test_analyze_accepts_numeric_link_source_ids():
    workflow = {
        "3": {"class_type": "ConsumerNode", "inputs": {"x": [2, 0]}},
    }

    result = analyze_workflow(workflow)

    assert result["links"] == [{"from_node": "2", "from_slot": 0, "to_node": "3", "input": "x"}]


def test_analyze_ignores_malformed_object_info_required_inputs():
    workflow = {
        "1": {"class_type": "KnownNode", "inputs": {}},
    }

    result_with_none_node = analyze_workflow(workflow, {"KnownNode": None})
    result_with_none_input = analyze_workflow(workflow, {"KnownNode": {"input": None}})

    assert isinstance(result_with_none_node, dict)
    assert result_with_none_node["input_issues"] == []
    assert isinstance(result_with_none_input, dict)
    assert result_with_none_input["input_issues"] == []
