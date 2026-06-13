from __future__ import annotations

from comfydex_mcp.user_guidance import (
    explain_asset_comparison_for_user,
    explain_capability_report_for_user,
    explain_generation_plan_for_user,
    explain_repair_plan_for_user,
    summarize_assets_for_user,
)


def test_explain_generation_plan_for_user_hides_node_graph_by_default():
    plan = {
        "selected_template_id": "sdxl-text-to-image",
        "mode": "text-to-image",
        "parameters": {
            "checkpoint_name": "sdxl.safetensors",
            "positive_prompt": "cinematic lake",
            "width": 1024,
            "height": 768,
            "steps": 24,
        },
        "missing_information": [],
        "policy": {"decision": "allowed", "reasons": []},
    }

    result = explain_generation_plan_for_user(plan)

    assert result["title"] == "Ready to create an image"
    assert "1024 x 768" in result["summary"]
    assert result["severity"] == "ok"
    assert result["technical"]["template_id"] == "sdxl-text-to-image"
    assert not any("KSampler" in item for item in result["bullets"])


def test_explain_generation_plan_for_user_lists_missing_items():
    result = explain_generation_plan_for_user(
        {
            "selected_template_id": "basic-text-to-image",
            "mode": "text-to-image",
            "parameters": {},
            "missing_information": ["checkpoint_name", "positive_prompt"],
            "policy": {"decision": "blocked", "reasons": ["validation_not_submit_ready"]},
        }
    )

    assert result["title"] == "More information is needed"
    assert result["severity"] == "blocked"
    assert "Choose a checkpoint model" in result["next_actions"]
    assert "Write the prompt" in result["next_actions"]


def test_explain_repair_plan_for_user_translates_failure_class():
    result = explain_repair_plan_for_user(
        {
            "failure_class": "missing_model",
            "summary": "checkpoint_name missing.safetensors was not found",
            "actions": [{"kind": "install_model", "target": "missing.safetensors"}],
            "retry": {"supported": False},
        }
    )

    assert result["title"] == "A model is missing"
    assert result["severity"] == "blocked"
    assert "missing.safetensors" in " ".join(result["bullets"])
    assert result["technical"]["failure_class"] == "missing_model"


def test_explain_capability_report_for_user_reports_ready_and_missing():
    ready = explain_capability_report_for_user(
        {
            "status": "ready",
            "can_run_now": True,
            "missing_models": [],
            "missing_nodes": [],
            "missing_information": [],
        }
    )
    missing = explain_capability_report_for_user(
        {
            "status": "missing_requirements",
            "can_run_now": False,
            "missing_models": [{"filename": "z-image.safetensors"}],
            "missing_nodes": [{"node_type": "ZImageSampler"}],
            "missing_information": [],
        }
    )

    assert ready["title"] == "Ready to run"
    assert ready["severity"] == "ok"
    assert missing["title"] == "Setup is needed first"
    assert missing["severity"] == "blocked"
    assert "z-image.safetensors" in " ".join(missing["bullets"])
    assert "ZImageSampler" in " ".join(missing["technical"]["missing_nodes"])


def test_summarize_assets_for_user_and_compare_summary():
    assets = [
        {
            "filename": "a.png",
            "favorite": True,
            "rating": 5,
            "tags": ["keeper"],
            "model_references": ["z-image.safetensors"],
        },
        {
            "filename": "b.png",
            "favorite": False,
            "rating": 3,
            "tags": ["draft"],
            "model_references": ["z-image.safetensors"],
        },
    ]

    summary = summarize_assets_for_user({"total": 2, "assets": assets})
    comparison = explain_asset_comparison_for_user(
        {
            "left": assets[0],
            "right": assets[1],
            "differences": {"rating": {"left": 5, "right": 3, "changed": True}},
        }
    )

    assert summary["title"] == "2 outputs indexed"
    assert "1 favorite" in summary["summary"]
    assert "z-image.safetensors" in " ".join(summary["bullets"])
    assert comparison["title"] == "Outputs are different"
    assert comparison["severity"] == "warn"
    assert "rating" in comparison["technical"]["changed_fields"]
