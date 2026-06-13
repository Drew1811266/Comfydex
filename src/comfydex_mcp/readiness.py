from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .generation import plan_workflow_generation
from .recipes import get_workflow_recipe
from .ui_graphs import build_ui_workflow_from_plan

READINESS_VERSION = "2.0.0"


@dataclass(frozen=True)
class FirstClassScenario:
    scenario_id: str
    name: str
    recipe_ids: tuple[str, ...]
    sample_intent: str
    sample_parameters: dict[str, Any]
    required_2_0: bool = True

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["recipe_ids"] = list(self.recipe_ids)
        value["sample_parameters"] = deepcopy(self.sample_parameters)
        return value


FIRST_CLASS_SCENARIOS: tuple[FirstClassScenario, ...] = (
    FirstClassScenario(
        "text-to-image",
        "Text To Image",
        ("text-to-image-basic", "text-to-image-sdxl", "text-to-image-lora"),
        "text to image of a clean product photo",
        {
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "clean product photo",
        },
    ),
    FirstClassScenario(
        "image-to-image",
        "Image To Image",
        ("image-to-image-basic",),
        "image to image variation",
        {
            "checkpoint_name": "model.safetensors",
            "image": "input.png",
            "positive_prompt": "soft lighting",
        },
    ),
    FirstClassScenario(
        "portrait",
        "Portrait",
        ("portrait-basic",),
        "portrait photo",
        {
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "portrait photo",
        },
    ),
    FirstClassScenario(
        "character-consistency",
        "Character Consistency",
        ("character-consistency-lora",),
        "consistent character sheet",
        {
            "checkpoint_name": "model.safetensors",
            "lora_name": "character.safetensors",
            "positive_prompt": "consistent character",
        },
    ),
    FirstClassScenario(
        "product-image",
        "Product Image",
        ("product-image-basic",),
        "product image on white background",
        {
            "checkpoint_name": "model.safetensors",
            "positive_prompt": "product on white background",
        },
    ),
    FirstClassScenario(
        "controlnet",
        "ControlNet",
        ("controlnet-pose",),
        "controlnet pose image",
        {
            "checkpoint_name": "model.safetensors",
            "controlnet_name": "pose.safetensors",
            "pose_image": "pose.png",
            "positive_prompt": "dancer",
        },
    ),
    FirstClassScenario(
        "inpainting",
        "Inpainting",
        ("inpainting-basic",),
        "inpaint masked area",
        {
            "checkpoint_name": "model.safetensors",
            "image": "input.png",
            "mask": "mask.png",
            "positive_prompt": "remove object",
        },
    ),
    FirstClassScenario(
        "upscaling",
        "Upscaling",
        ("image-upscale",),
        "upscale image",
        {"image": "input.png", "upscale_model_name": "4x.pth"},
    ),
    FirstClassScenario(
        "background-replacement",
        "Background Replacement",
        ("background-replacement-inpaint",),
        "replace image background",
        {
            "checkpoint_name": "model.safetensors",
            "image": "input.png",
            "mask": "mask.png",
            "positive_prompt": "studio background",
        },
    ),
)


def list_first_class_scenarios() -> list[dict[str, Any]]:
    return [scenario.to_dict() for scenario in FIRST_CLASS_SCENARIOS]


def build_20_readiness_report() -> dict[str, Any]:
    scenarios = [_scenario_readiness(scenario) for scenario in FIRST_CLASS_SCENARIOS]
    ready_count = sum(1 for scenario in scenarios if scenario["status"] == "ready")
    acceptance = _acceptance_criteria(scenarios)
    all_criteria_ready = all(item["status"] == "ready" for item in acceptance)
    status = (
        "ready_for_2_0"
        if ready_count == len(scenarios) and all_criteria_ready
        else "needs_work"
    )
    return {
        "readiness_version": READINESS_VERSION,
        "status": status,
        "summary": {
            "scenario_count": len(scenarios),
            "ready_count": ready_count,
            "needs_work_count": len(scenarios) - ready_count,
        },
        "scenarios": scenarios,
        "acceptance_criteria": acceptance,
        "next_steps": _next_steps(scenarios, acceptance),
    }


def _scenario_readiness(scenario: FirstClassScenario) -> dict[str, Any]:
    recipe_ids = list(scenario.recipe_ids)
    if not recipe_ids:
        return {
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "status": "missing_recipe",
            "recipe_ids": [],
            "ready_recipe_ids": [],
            "gaps": ["recipe"],
            "build_checks": [],
        }

    checks = [_buildability_for_recipe(scenario, recipe_id) for recipe_id in recipe_ids]
    ready_recipe_ids = [
        str(check["recipe_id"]) for check in checks if check["status"] == "ready"
    ]
    if ready_recipe_ids:
        status = "ready"
        gaps: list[str] = []
    else:
        status = "partial"
        gaps = _unique_gap_list(checks)
    return {
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "status": status,
        "recipe_ids": recipe_ids,
        "ready_recipe_ids": ready_recipe_ids,
        "gaps": gaps,
        "build_checks": checks,
    }


def _buildability_for_recipe(
    scenario: FirstClassScenario,
    recipe_id: str,
) -> dict[str, Any]:
    recipe = get_workflow_recipe(recipe_id)
    if recipe is None:
        return {
            "recipe_id": recipe_id,
            "status": "missing_recipe",
            "template_id": None,
            "semantic_status": "unknown",
            "ui_graph_status": "not_run",
            "missing_information": [],
            "gaps": ["recipe"],
        }

    try:
        plan = plan_workflow_generation(
            scenario.sample_intent,
            scenario.sample_parameters,
            template_id=str(recipe["template_id"]),
        )
        build = build_ui_workflow_from_plan(plan)
    except Exception as exc:  # pragma: no cover - defensive report shaping
        return {
            "recipe_id": recipe_id,
            "status": "partial",
            "template_id": recipe.get("template_id"),
            "semantic_status": "unknown",
            "ui_graph_status": "error",
            "missing_information": [],
            "gaps": ["exception"],
            "error": f"{exc.__class__.__name__}: {exc}",
        }

    missing_information = [
        str(item) for item in plan.get("missing_information", []) if item
    ]
    semantic_coverage = plan.get("semantic_coverage", {})
    semantic_status = str(semantic_coverage.get("status", "unknown"))
    ui_graph_status = str(build.get("status", "unknown"))
    gaps: list[str] = []
    if missing_information:
        gaps.append("missing_information")
    if semantic_status != "supported":
        gaps.append("semantic_coverage")
    if ui_graph_status != "valid":
        gaps.append("ui_graph")

    summary = build.get("summary") if isinstance(build.get("summary"), dict) else {}
    return {
        "recipe_id": recipe_id,
        "status": "ready" if not gaps else "partial",
        "template_id": recipe.get("template_id"),
        "semantic_status": semantic_status,
        "ui_graph_status": ui_graph_status,
        "missing_information": missing_information,
        "node_count": summary.get("node_count", 0),
        "link_count": summary.get("link_count", 0),
        "gaps": gaps,
    }


def _acceptance_criteria(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_scenarios_ready = all(scenario["status"] == "ready" for scenario in scenarios)
    return [
        _criterion(
            "ordinary_user_docs",
            "Ordinary-user documentation",
            _doc_status(),
            [
                "README and usage docs explain readiness statuses and do not claim unsupported scenarios are complete."
            ],
        ),
        _criterion(
            "scenario_coverage",
            "First-class scenario coverage",
            "ready" if all_scenarios_ready else "needs_work",
            [
                "All 2.0 first-class scenarios must have a ready recipe, semantic coverage, and valid UI graph dry run."
            ],
        ),
        _criterion(
            "capability_reports",
            "Capability and missing requirement reports",
            "ready",
            ["Capability resolver and install planner are available before execution."],
        ),
        _criterion(
            "install_confirmation",
            "Install plan confirmation",
            "ready",
            ["Install plans require confirmation and record audit entries by default."],
        ),
        _criterion(
            "live_bridge_push",
            "Live Bridge push path",
            "ready",
            ["Generated UI workflows can be handed to the existing Live Bridge push path."],
        ),
        _criterion(
            "repair_loop",
            "Execution and repair loop",
            "ready",
            ["Failed runs can be classified and converted into conservative repair plans."],
        ),
        _criterion(
            "desktop_visibility",
            "Desktop readiness visibility",
            _desktop_visibility_status(),
            [
                "Desktop should show readiness status, scenario coverage, and remaining gaps."
            ],
        ),
        _criterion(
            "release_validation",
            "Release validation metadata",
            _release_doc_status(),
            ["1.9 release checklist and readiness tests must be present."],
        ),
    ]


def _criterion(
    criterion_id: str,
    label: str,
    status: str,
    details: list[str],
) -> dict[str, Any]:
    return {
        "criterion_id": criterion_id,
        "label": label,
        "status": status,
        "details": details,
    }


def _doc_status() -> str:
    root = _repo_root()
    usage = root / "docs" / "usage" / "2.0-readiness-gate.md"
    readme = root / "README.md"
    if not usage.is_file() or not readme.is_file():
        return "needs_work"
    text = usage.read_text(encoding="utf-8") + "\n" + readme.read_text(encoding="utf-8")
    return "ready" if "2.0 Readiness Gate" in text else "needs_work"


def _desktop_visibility_status() -> str:
    root = _repo_root()
    bridge = root / "src" / "comfydex_mcp" / "desktop_bridge.py"
    api = root / "desktop" / "src" / "lib" / "api.ts"
    settings = root / "desktop" / "src" / "views" / "SettingsView.tsx"
    required = (
        (bridge, "twenty_readiness_report"),
        (api, "getTwentyReadinessReport"),
        (settings, "2.0 readiness"),
    )
    for path, marker in required:
        if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
            return "needs_work"
    return "ready"


def _release_doc_status() -> str:
    root = _repo_root()
    checklist = root / "docs" / "release" / "2.0-release-checklist.md"
    tests = root / "tests" / "test_readiness.py"
    return "ready" if checklist.is_file() and tests.is_file() else "needs_work"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _next_steps(
    scenarios: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> list[str]:
    steps: list[str] = []
    missing_scenarios = [
        str(scenario["scenario_id"])
        for scenario in scenarios
        if scenario["status"] != "ready"
    ]
    if missing_scenarios:
        steps.append("Scenario coverage is not complete.")
        steps.append("Add or repair recipes for: " + ", ".join(missing_scenarios) + ".")

    incomplete_criteria = [
        str(item["criterion_id"])
        for item in acceptance
        if item["status"] != "ready"
    ]
    if incomplete_criteria:
        steps.append(
            "Complete readiness criteria: " + ", ".join(incomplete_criteria) + "."
        )
    if not steps:
        steps.append("Prepare the final 2.0 release candidate.")
    return steps


def _unique_gap_list(checks: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for check in checks:
        for gap in check.get("gaps", []):
            if isinstance(gap, str) and gap not in gaps:
                gaps.append(gap)
    return gaps
