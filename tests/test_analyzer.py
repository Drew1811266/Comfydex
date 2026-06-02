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
