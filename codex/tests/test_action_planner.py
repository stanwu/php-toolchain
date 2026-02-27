from __future__ import annotations

from datetime import datetime

from core.models import Action, ActionType, AnalysisResult, RiskLevel
from planners.action_planner import ActionPlanner


def make_action(atype: ActionType, source: str, risk: RiskLevel, dest: str | None = None) -> Action:
    return Action(atype, source, dest, risk, f"reason for {source}")


# Simulate outputs from multiple analyzers
vendor_result = AnalysisResult(
    "vendor_analyzer",
    [
        make_action(ActionType.ADD_GITIGNORE, "vendor", RiskLevel.LOW),
    ],
    {},
)

backup_result = AnalysisResult(
    "backup_analyzer",
    [
        make_action(ActionType.DELETE, "backup_old.php", RiskLevel.LOW),
        make_action(ActionType.DELETE, "config-20230816.php", RiskLevel.MEDIUM),
    ],
    {},
)

duplicate_result = AnalysisResult(
    "duplicate_analyzer",
    [
        make_action(ActionType.DELETE, "utils_copy.php", RiskLevel.MEDIUM),
        # Duplicate of backup_old.php — should be deduplicated (keep LOW)
        make_action(ActionType.DELETE, "backup_old.php", RiskLevel.HIGH),
    ],
    {},
)

complexity_result = AnalysisResult(
    "complexity_analyzer",
    [
        make_action(ActionType.REPORT_ONLY, "saas/service.php", RiskLevel.HIGH),
    ],
    {},
)


def test_returns_action_plan() -> None:
    plan = ActionPlanner([vendor_result], project_dir="/tmp/project").build_plan()
    assert plan is not None
    assert hasattr(plan, "actions")


def test_plan_has_project_dir() -> None:
    plan = ActionPlanner([vendor_result], project_dir="/tmp/project").build_plan()
    assert plan.project_dir == "/tmp/project"


def test_plan_has_created_at() -> None:
    plan = ActionPlanner([vendor_result], project_dir="/tmp/project").build_plan()
    assert plan.created_at
    parsed = datetime.fromisoformat(plan.created_at)
    assert parsed.tzinfo is not None


def test_dedup_keeps_lower_risk() -> None:
    plan = ActionPlanner(
        [backup_result, duplicate_result], project_dir="/tmp/project"
    ).build_plan()
    matches = [a for a in plan.actions if a.source == "backup_old.php" and a.action_type == ActionType.DELETE]
    assert len(matches) == 1
    assert matches[0].risk_level == RiskLevel.LOW


def test_dedup_unique_sources_kept() -> None:
    plan = ActionPlanner(
        [vendor_result, backup_result, duplicate_result, complexity_result], project_dir="/tmp/project"
    ).build_plan()
    sources = {a.source for a in plan.actions}
    assert sources == {"vendor", "backup_old.php", "config-20230816.php", "utils_copy.php", "saas/service.php"}


def test_sort_gitignore_first() -> None:
    plan = ActionPlanner(
        [vendor_result, backup_result, duplicate_result, complexity_result], project_dir="/tmp/project"
    ).build_plan()
    assert plan.actions[0].action_type == ActionType.ADD_GITIGNORE


def test_sort_report_only_last() -> None:
    plan = ActionPlanner(
        [vendor_result, backup_result, duplicate_result, complexity_result], project_dir="/tmp/project"
    ).build_plan()
    assert plan.actions[-1].action_type == ActionType.REPORT_ONLY


def test_sort_low_before_medium() -> None:
    plan = ActionPlanner(
        [vendor_result, backup_result, duplicate_result, complexity_result], project_dir="/tmp/project"
    ).build_plan()
    deletes = [a for a in plan.actions if a.action_type == ActionType.DELETE]
    assert deletes[0].risk_level == RiskLevel.LOW
    assert any(a.risk_level == RiskLevel.MEDIUM for a in deletes[1:])


def test_summary_total() -> None:
    plan = ActionPlanner(
        [vendor_result, backup_result, duplicate_result, complexity_result], project_dir="/tmp/project"
    ).build_plan()
    summary = ActionPlanner([], project_dir="/tmp/project").summary(plan)
    assert summary["total"] == 5


def test_summary_by_risk() -> None:
    plan = ActionPlanner(
        [vendor_result, backup_result, duplicate_result, complexity_result], project_dir="/tmp/project"
    ).build_plan()
    summary = ActionPlanner([], project_dir="/tmp/project").summary(plan)
    assert summary["by_risk"]["LOW"] == 2
    assert summary["by_risk"]["MEDIUM"] == 2
    assert summary["by_risk"]["HIGH"] == 1


def test_summary_by_type() -> None:
    plan = ActionPlanner(
        [vendor_result, backup_result, duplicate_result, complexity_result], project_dir="/tmp/project"
    ).build_plan()
    summary = ActionPlanner([], project_dir="/tmp/project").summary(plan)
    assert summary["by_type"]["ADD_GITIGNORE"] == 1
    assert summary["by_type"]["DELETE"] == 3
    assert summary["by_type"]["REPORT_ONLY"] == 1


def test_empty_results() -> None:
    plan = ActionPlanner([], project_dir="/tmp/project").build_plan()
    assert plan.actions == []

