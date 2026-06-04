from comfydex_mcp.diagnostics import diagnose_run


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
