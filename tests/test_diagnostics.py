from comfydex_mcp.diagnostics import compare_runs, diagnose_run


def test_diagnose_run_explains_failed_submission_and_missing_node_type():
    run = {
        "run_id": "r1",
        "status": "failed",
        "events": [{"type": "submission_error", "error": "Missing node type: CustomSampler"}],
        "outputs": [],
    }
    workflow = {
        "1": {"class_type": "KnownNode", "inputs": {}},
        "2": {"class_type": "CustomSampler", "inputs": {}},
        "3": {"class_type": 123, "inputs": {}},
        "4": "not a node",
    }

    result = diagnose_run(run, workflow, object_info={"KnownNode": {}})

    assert result["run_id"] == "r1"
    assert result["status"] == "failed"
    assert "submission_error" in result["signals"]
    assert "missing_outputs" not in result["signals"]
    assert result["missing_node_types"] == ["CustomSampler"]
    assert "Missing node type: CustomSampler" in result["summary"]


def test_diagnose_run_reports_missing_outputs_for_completed_run():
    run = {"run_id": "r2", "status": "completed", "events": [], "outputs": []}

    result = diagnose_run(run)

    assert "missing_outputs" in result["signals"]


def test_diagnose_run_does_not_report_missing_outputs_when_completed_outputs_exist():
    run = {
        "run_id": "r3",
        "status": "completed",
        "events": [],
        "outputs": [{"filename": "image.png"}],
    }

    result = diagnose_run(run)

    assert "missing_outputs" not in result["signals"]


def test_diagnose_run_deduplicates_and_sorts_missing_node_types():
    run = {"run_id": "r4", "status": "running", "events": [], "outputs": []}
    workflow = {
        "1": {"class_type": "BetaMissing", "inputs": {}},
        "2": {"class_type": "KnownNode", "inputs": {}},
        "3": {"class_type": "AlphaMissing", "inputs": {}},
        "4": {"class_type": "BetaMissing", "inputs": {}},
        "5": {"class_type": None, "inputs": {}},
        "6": ["not", "a", "node"],
    }

    result = diagnose_run(run, workflow, object_info={"KnownNode": {}})
    malformed_workflow_result = diagnose_run(run, workflow=["not", "a", "workflow"], object_info={})

    assert result["missing_node_types"] == ["AlphaMissing", "BetaMissing"]
    assert malformed_workflow_result["missing_node_types"] == []


def test_diagnose_run_truncates_event_text_without_dumping_full_event():
    long_message = "node crashed while sampling " + ("x" * 1000)
    run = {
        "run_id": "r5",
        "status": "failed",
        "events": [
            {
                "type": "execution_error",
                "message": long_message,
                "payload": {"debug_dump": "full event dump " + ("y" * 1000)},
            }
        ],
        "outputs": [],
    }

    result = diagnose_run(run)

    assert "execution_error" in result["signals"]
    assert "node crashed while sampling" in result["summary"]
    assert "full event dump" not in result["summary"]
    assert len(result["summary"]) <= 360


def test_diagnose_run_handles_malformed_run_records():
    for malformed_run in (None, [], "bad"):
        result = diagnose_run(malformed_run)

        assert result["status"] == "unknown"
        assert result["signals"] == []
        assert result["missing_node_types"] == []
        assert result["summary"] == "Run None status is unknown."


def test_diagnose_run_ignores_invalid_event_types_and_sorts_signals():
    run = {
        "run_id": "r6",
        "status": "failed",
        "events": [
            {"type": "websocket_error", "message": "socket closed"},
            {"type": None, "message": "ignored"},
            {"type": "", "message": "ignored"},
            {"type": 3, "message": "ignored"},
            {"type": "execution_error", "message": "node failed"},
        ],
        "outputs": [],
    }

    result = diagnose_run(run)

    assert result["signals"] == ["execution_error", "websocket_error"]


def test_compare_runs_reports_changed_seed_status_and_output_count():
    left_run = {"run_id": "left", "status": "completed", "outputs": [{"filename": "left.png"}]}
    right_run = {
        "run_id": "right",
        "status": "failed",
        "outputs": [{"filename": "right-1.png"}, {"filename": "right-2.png"}],
    }
    left_workflow = {
        "2": {"class_type": "KSampler", "inputs": {"steps": 20, "seed": 111}},
    }
    right_workflow = {
        "2": {"class_type": "KSampler", "inputs": {"steps": 20, "seed": 222}},
    }

    result = compare_runs(left_run, right_run, left_workflow, right_workflow)

    assert result["left_run_id"] == "left"
    assert result["right_run_id"] == "right"
    assert result["status_changed"] == {"left": "completed", "right": "failed"}
    assert result["output_count_changed"] == {"left": 1, "right": 2}
    assert result["input_changes"] == [{"node_id": "2", "input": "seed", "left": 111, "right": 222}]


def test_compare_runs_reports_no_changes_as_empty_diff():
    left_run = {"run_id": "left", "status": "completed", "outputs": [{"filename": "left.png"}]}
    right_run = {"run_id": "right", "status": "completed", "outputs": [{"filename": "right.png"}]}
    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 123, "steps": 20}},
    }

    result = compare_runs(left_run, right_run, workflow, workflow)

    assert result["status_changed"] is None
    assert result["output_count_changed"] is None
    assert result["input_changes"] == []
    assert result["node_changes"] == []
    assert result["node_type_changes"] == []
    assert result["model_reference_changes"] == []


def test_compare_runs_reports_node_add_remove_and_type_changes():
    left_workflow = {
        "1": {"class_type": "SharedNode", "inputs": {}},
        "2": {"class_type": "RemovedNode", "inputs": {}},
        "3": {"class_type": "OldType", "inputs": {}},
    }
    right_workflow = {
        "1": {"class_type": "SharedNode", "inputs": {}},
        "3": {"class_type": "NewType", "inputs": {}},
        "4": {"class_type": "AddedNode", "inputs": {}},
    }

    result = compare_runs({}, {}, left_workflow, right_workflow)

    assert result["node_changes"] == [
        {"node_id": "2", "change": "removed"},
        {"node_id": "4", "change": "added"},
    ]
    assert result["node_type_changes"] == [{"node_id": "3", "left": "OldType", "right": "NewType"}]


def test_compare_runs_reports_model_reference_input_changes_separately():
    left_workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "2": {"class_type": "LoraLoader", "inputs": {"lora_name": "detail-v1.safetensors"}},
    }
    right_workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "anime.safetensors"}},
        "2": {"class_type": "LoraLoader", "inputs": {"lora_name": "detail-v1.safetensors"}},
    }

    result = compare_runs({}, {}, left_workflow, right_workflow)

    expected_change = {
        "node_id": "1",
        "input": "ckpt_name",
        "left": "base.safetensors",
        "right": "anime.safetensors",
    }
    assert expected_change in result["input_changes"]
    assert result["model_reference_changes"] == [expected_change]


def test_compare_runs_handles_malformed_runs_and_workflows():
    empty_result = compare_runs(None, [], "bad workflow", None)

    assert empty_result["left_run_id"] is None
    assert empty_result["right_run_id"] is None
    assert empty_result["status_changed"] is None
    assert empty_result["output_count_changed"] is None
    assert empty_result["input_changes"] == []
    assert empty_result["node_changes"] == []
    assert empty_result["node_type_changes"] == []
    assert empty_result["model_reference_changes"] == []

    left_workflow = {
        "1": {"class_type": "StableNode", "inputs": ["not", "a", "dict"]},
        "2": "not a node",
    }
    right_workflow = {
        "1": {"class_type": "StableNode", "inputs": None},
        "2": "not a node",
    }

    malformed_inputs_result = compare_runs(
        {"run_id": "left", "outputs": "not a list"},
        {"run_id": "right", "outputs": {"not": "a list"}},
        left_workflow,
        right_workflow,
    )

    assert malformed_inputs_result["status_changed"] is None
    assert malformed_inputs_result["output_count_changed"] is None
    assert malformed_inputs_result["input_changes"] == []
    assert malformed_inputs_result["node_changes"] == []
    assert malformed_inputs_result["node_type_changes"] == []
    assert malformed_inputs_result["model_reference_changes"] == []
