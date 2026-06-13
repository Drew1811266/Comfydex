from comfydex_mcp.repairs import build_run_repair_plan, classify_run_failure


def test_classify_missing_model_from_diagnosis():
    diagnosis = {
        "signals": ["fallback_used", "history_failed", "missing_model_reference"],
        "missing_model_references": ["base.safetensors"],
        "missing_node_types": [],
    }

    result = classify_run_failure(diagnosis)

    assert result["failure_class"] == "missing_model"
    assert result["retryable"] is False
    assert "base.safetensors" in result["summary"]


def test_repair_plan_for_missing_node_requires_install_plan():
    diagnosis = {
        "signals": ["submission_error"],
        "missing_node_types": ["CustomSampler"],
        "missing_model_references": [],
    }

    result = build_run_repair_plan("run-1", diagnosis)

    assert result["status"] == "manual_action_required"
    assert result["failure_class"] == "missing_node"
    assert result["actions"][0]["kind"] == "install_node"
    assert result["actions"][0]["requires_confirmation"] is True
    assert result["retry"]["supported"] is False


def test_repair_plan_for_missing_outputs_can_retry_fetch():
    diagnosis = {
        "signals": ["missing_outputs"],
        "missing_node_types": [],
        "missing_model_references": [],
    }

    result = build_run_repair_plan("run-2", diagnosis)

    assert result["status"] == "retry_available"
    assert result["failure_class"] == "missing_outputs"
    assert result["retry"] == {
        "supported": True,
        "operation": "fetch_outputs",
        "arguments": {"run_id": "run-2"},
        "requires_confirmation": False,
    }


def test_repair_plan_for_resource_failure_suggests_lower_cost_retry():
    diagnosis = {
        "signals": ["execution_error", "history_failed"],
        "summary": "CUDA out of memory while sampling",
        "missing_node_types": [],
        "missing_model_references": [],
    }

    result = build_run_repair_plan("run-3", diagnosis)

    assert result["failure_class"] == "resource_failure"
    assert any(action["kind"] == "reduce_workload" for action in result["actions"])
    assert result["retry"]["operation"] == "resubmit_workflow"
    assert result["retry"]["requires_confirmation"] is True


def test_repair_plan_for_invalid_parameter_requires_parameter_review():
    diagnosis = {
        "signals": ["history_failed"],
        "summary": "KSampler sampler_name not in list",
        "missing_node_types": [],
        "missing_model_references": [],
    }

    result = build_run_repair_plan("run-4", diagnosis, workflow_name="bad.json")

    assert result["failure_class"] == "invalid_parameter"
    assert result["actions"][0]["kind"] == "adjust_parameter"
    assert result["retry"]["arguments"] == {"run_id": "run-4", "workflow_name": "bad.json"}


def test_repair_plan_for_invalid_link_requires_graph_inspection():
    diagnosis = {
        "signals": ["history_failed"],
        "summary": "Bad link type mismatch between LATENT and IMAGE",
        "missing_node_types": [],
        "missing_model_references": [],
    }

    result = build_run_repair_plan("run-5", diagnosis)

    assert result["failure_class"] == "invalid_link"
    assert result["actions"][0]["kind"] == "inspect_links"


def test_repair_plan_for_fetch_failure_retries_outputs():
    result = build_run_repair_plan(
        "run-6",
        {"signals": [], "missing_node_types": [], "missing_model_references": []},
        stage="fetch",
        error="download failed",
    )

    assert result["failure_class"] == "fetch_failure"
    assert result["retry"]["operation"] == "fetch_outputs"
    assert result["retry"]["requires_confirmation"] is False
