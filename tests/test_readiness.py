from comfydex_mcp.readiness import (
    FIRST_CLASS_SCENARIOS,
    build_20_readiness_report,
    list_first_class_scenarios,
)


def test_first_class_scenarios_match_2_0_acceptance_list():
    scenario_ids = {scenario["scenario_id"] for scenario in list_first_class_scenarios()}

    assert scenario_ids == {
        "text-to-image",
        "image-to-image",
        "portrait",
        "character-consistency",
        "product-image",
        "controlnet",
        "inpainting",
        "upscaling",
        "background-replacement",
    }
    assert len(FIRST_CLASS_SCENARIOS) == 9


def test_readiness_report_marks_existing_graph_scenarios_ready():
    report = build_20_readiness_report()
    by_id = {item["scenario_id"]: item for item in report["scenarios"]}

    assert report["readiness_version"] == "1.9.0"
    assert report["status"] == "needs_work"
    assert by_id["text-to-image"]["status"] == "ready"
    assert by_id["image-to-image"]["status"] == "ready"
    assert by_id["controlnet"]["status"] == "ready"
    assert by_id["upscaling"]["status"] == "ready"
    assert by_id["inpainting"]["status"] == "missing_recipe"
    assert "recipe" in by_id["inpainting"]["gaps"]
    assert report["summary"]["ready_count"] >= 4
    assert report["summary"]["scenario_count"] == 9


def test_readiness_report_tracks_acceptance_criteria():
    report = build_20_readiness_report()
    criteria = {item["criterion_id"]: item for item in report["acceptance_criteria"]}

    assert criteria["ordinary_user_docs"]["status"] in {"ready", "needs_work"}
    assert criteria["scenario_coverage"]["status"] == "needs_work"
    assert criteria["live_bridge_push"]["status"] == "ready"
    assert criteria["repair_loop"]["status"] == "ready"
    assert "Scenario coverage is not complete." in report["next_steps"]
