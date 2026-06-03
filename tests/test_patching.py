import copy

import pytest

from comfydex_mcp.patching import patch_workflow


OBJECT_INFO = {
    "ImageSource": {"input": {"required": {}}, "output": ["IMAGE"]},
    "SaveImage": {
        "input": {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING",),
            }
        },
        "output": [],
    },
    "KSampler": {
        "input": {
            "required": {
                "seed": ("INT",),
                "steps": ("INT",),
            }
        },
        "output": ["IMAGE"],
    },
}


def sample_workflow():
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {"seed": 42, "steps": 20},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "Comfydex"},
        },
    }


def test_set_input_patches_copy_and_reports_applied_operation():
    workflow = sample_workflow()
    original = copy.deepcopy(workflow)
    operation = {"op": "set_input", "node_id": "1", "input": "seed", "value": 123}

    result = patch_workflow(workflow, [operation])

    assert result["status"] == "patched"
    assert result["workflow"]["1"]["inputs"]["seed"] == 123
    assert workflow == original
    assert result["operations_applied"] == [operation]
    assert result["validation"] is None
    assert result["submit_ready"] is False


def test_set_input_report_records_old_and_new_values():
    result = patch_workflow(
        sample_workflow(),
        [{"op": "set_input", "node_id": "1", "input": "seed", "value": 123}],
    )

    assert result["report"]["status"] == "patched"
    assert result["report"]["errors"] == []
    assert result["report"]["changes"] == [
        {
            "op": "set_input",
            "node_id": "1",
            "input": "seed",
            "old_value": 42,
            "new_value": 123,
        }
    ]


def test_set_input_preserves_unrelated_nodes_inputs_and_links():
    workflow = sample_workflow()

    result = patch_workflow(
        workflow,
        [{"op": "set_input", "node_id": "1", "input": "seed", "value": 999}],
    )

    assert result["workflow"]["1"]["inputs"]["steps"] == 20
    assert result["workflow"]["2"] == workflow["2"]
    assert result["workflow"]["2"]["inputs"]["images"] == ["1", 0]


def test_add_node_adds_new_node_with_inputs():
    workflow = sample_workflow()
    operation = {
        "op": "add_node",
        "node_id": "9",
        "class_type": "SaveImage",
        "inputs": {"images": ["1", 0], "filename_prefix": "extra"},
    }

    result = patch_workflow(workflow, [operation])

    assert result["workflow"]["9"] == {
        "class_type": "SaveImage",
        "inputs": {"images": ["1", 0], "filename_prefix": "extra"},
    }
    assert result["operations_applied"] == [operation]


def test_add_node_rejects_existing_node_id():
    with pytest.raises(ValueError, match="already exists"):
        patch_workflow(
            sample_workflow(),
            [
                {
                    "op": "add_node",
                    "node_id": "1",
                    "class_type": "SaveImage",
                    "inputs": {},
                }
            ],
        )


def test_add_link_sets_target_input_and_preserves_other_inputs():
    workflow = {
        "1": {"class_type": "ImageSource", "inputs": {}},
        "2": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "Comfydex"},
        },
    }

    result = patch_workflow(
        workflow,
        [
            {
                "op": "add_link",
                "source_node_id": "1",
                "output_slot": 0,
                "target_node_id": "2",
                "input": "images",
            }
        ],
    )

    assert result["workflow"]["2"]["inputs"] == {
        "filename_prefix": "Comfydex",
        "images": ["1", 0],
    }


def test_add_link_rejects_non_object_source_node():
    workflow = {
        "1": "not-a-node",
        "2": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "Comfydex"},
        },
    }

    with pytest.raises(ValueError, match="source node must be an object"):
        patch_workflow(
            workflow,
            [
                {
                    "op": "add_link",
                    "source_node_id": "1",
                    "output_slot": 0,
                    "target_node_id": "2",
                    "input": "images",
                }
            ],
        )


def test_add_link_rejects_null_source_node():
    workflow = {
        "1": None,
        "2": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "Comfydex"},
        },
    }

    with pytest.raises(ValueError, match="source node must be an object"):
        patch_workflow(
            workflow,
            [
                {
                    "op": "add_link",
                    "source_node_id": "1",
                    "output_slot": 0,
                    "target_node_id": "2",
                    "input": "images",
                }
            ],
        )


def test_add_link_rejects_non_object_target_node():
    workflow = {
        "1": {"class_type": "ImageSource", "inputs": {}},
        "2": "not-a-node",
    }

    with pytest.raises(ValueError, match="target node must be an object"):
        patch_workflow(
            workflow,
            [
                {
                    "op": "add_link",
                    "source_node_id": "1",
                    "output_slot": 0,
                    "target_node_id": "2",
                    "input": "images",
                }
            ],
        )


def test_remove_input_deletes_input_and_reports_removed_operation():
    result = patch_workflow(
        sample_workflow(),
        [{"op": "remove_input", "node_id": "1", "input": "seed"}],
    )

    assert "seed" not in result["workflow"]["1"]["inputs"]
    assert result["operations_applied"] == [
        {"op": "remove_input", "node_id": "1", "input": "seed", "status": "removed"}
    ]


@pytest.mark.parametrize(
    "operation,match",
    [
        ({"op": "rename_node", "node_id": "1"}, "unsupported operation"),
        ({"op": "set_input", "input": "seed", "value": 1}, "node_id"),
        ({"op": "remove_input", "node_id": "1"}, "input"),
    ],
)
def test_invalid_operations_raise_stable_value_errors(operation, match):
    with pytest.raises(ValueError, match=match):
        patch_workflow(sample_workflow(), [operation])


def test_invalid_operation_can_return_structured_failure_report():
    result = patch_workflow(
        sample_workflow(),
        [{"op": "set_input", "input": "seed", "value": 1}],
        raise_on_error=False,
    )

    assert result["status"] == "failed"
    assert result["submit_ready"] is False
    assert result["validation"] is None
    assert result["operations_applied"] == []
    assert result["report"] == {
        "status": "failed",
        "changes": [],
        "errors": [{"message": "operation must include node_id"}],
    }


def test_invalid_operations_payload_can_return_structured_failure_report():
    result = patch_workflow(
        sample_workflow(),
        {"op": "set_input"},
        raise_on_error=False,
    )

    assert result["status"] == "failed"
    assert result["submit_ready"] is False
    assert result["workflow"] == sample_workflow()
    assert result["operations_applied"] == []
    assert result["validation"] is None
    assert result["report"] == {
        "status": "failed",
        "changes": [],
        "errors": [{"message": "operations must be a list"}],
    }


def test_validation_invalid_keeps_patched_workflow_as_draft_and_not_submit_ready():
    result = patch_workflow(
        sample_workflow(),
        [{"op": "remove_input", "node_id": "2", "input": "images"}],
        object_info=OBJECT_INFO,
    )

    assert result["status"] == "invalid"
    assert result["submit_ready"] is False
    assert result["workflow"]["2"]["inputs"] == {"filename_prefix": "Comfydex"}
    assert result["validation"]["status"] == "invalid"
    assert any(
        error["reason"] == "missing_required_input" and error["input"] == "images"
        for error in result["validation"]["errors"]
    )


def test_validation_valid_marks_submit_ready():
    result = patch_workflow(
        sample_workflow(),
        [{"op": "set_input", "node_id": "1", "input": "seed", "value": 123}],
        object_info=OBJECT_INFO,
    )

    assert result["status"] == "patched"
    assert result["submit_ready"] is True
    assert result["validation"]["status"] == "valid"
