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


def test_readiness_report_marks_all_first_class_scenarios_ready():
    report = build_20_readiness_report()

    assert report["readiness_version"] == "2.0.0"
    assert report["status"] == "ready_for_2_0"
    assert report["summary"] == {
        "scenario_count": 9,
        "ready_count": 9,
        "needs_work_count": 0,
    }
    assert {item["status"] for item in report["scenarios"]} == {"ready"}


def test_readiness_report_tracks_acceptance_criteria():
    report = build_20_readiness_report()
    criteria = {item["criterion_id"]: item for item in report["acceptance_criteria"]}

    assert {item["status"] for item in criteria.values()} == {"ready"}
    assert criteria["scenario_coverage"]["status"] == "ready"
    assert "Prepare the final 2.0 release candidate." in report["next_steps"]
