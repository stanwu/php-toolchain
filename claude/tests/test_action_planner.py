import pytest
from core.models import Action, ActionPlan, ActionType, AnalysisResult, RiskLevel
from planners.action_planner import ActionPlanner


def make_action(atype: ActionType, source: str, risk: RiskLevel, dest: str | None = None) -> Action:
    return Action(atype, source, dest, risk, f"reason for {source}")


# Simulate outputs from multiple analyzers
vendor_result = AnalysisResult("vendor_analyzer", [
    make_action(ActionType.ADD_GITIGNORE, "vendor", RiskLevel.LOW),
], {})

backup_result = AnalysisResult("backup_analyzer", [
    make_action(ActionType.DELETE, "backup_old.php", RiskLevel.LOW),
    make_action(ActionType.DELETE, "config-20230816.php", RiskLevel.MEDIUM),
], {})

duplicate_result = AnalysisResult("duplicate_analyzer", [
    make_action(ActionType.DELETE, "utils_copy.php", RiskLevel.MEDIUM),
    # Duplicate of backup_old.php — should be deduplicated (keep LOW)
    make_action(ActionType.DELETE, "backup_old.php", RiskLevel.HIGH),
], {})

complexity_result = AnalysisResult("complexity_analyzer", [
    make_action(ActionType.REPORT_ONLY, "saas/service.php", RiskLevel.HIGH),
], {})

ALL_RESULTS = [vendor_result, backup_result, duplicate_result, complexity_result]


@pytest.fixture
def planner() -> ActionPlanner:
    return ActionPlanner(ALL_RESULTS, "/var/www/myproject")


@pytest.fixture
def plan(planner: ActionPlanner) -> ActionPlan:
    return planner.build_plan()


def test_returns_action_plan(plan: ActionPlan) -> None:
    assert isinstance(plan, ActionPlan)


def test_plan_has_project_dir(plan: ActionPlan) -> None:
    assert plan.project_dir == "/var/www/myproject"


def test_plan_has_created_at(plan: ActionPlan) -> None:
    assert isinstance(plan.created_at, str)
    assert len(plan.created_at) > 0
    # Must be a valid ISO 8601 string containing timezone info
    assert "T" in plan.created_at


def test_dedup_keeps_lower_risk(plan: ActionPlan) -> None:
    backup_actions = [a for a in plan.actions if a.source == "backup_old.php"]
    assert len(backup_actions) == 1
    assert backup_actions[0].risk_level == RiskLevel.LOW


def test_dedup_unique_sources_kept(plan: ActionPlan) -> None:
    sources = {a.source for a in plan.actions}
    assert "vendor" in sources
    assert "backup_old.php" in sources
    assert "config-20230816.php" in sources
    assert "utils_copy.php" in sources
    assert "saas/service.php" in sources


def test_sort_gitignore_first(plan: ActionPlan) -> None:
    assert plan.actions[0].action_type == ActionType.ADD_GITIGNORE


def test_sort_report_only_last(plan: ActionPlan) -> None:
    assert plan.actions[-1].action_type == ActionType.REPORT_ONLY


def test_sort_low_before_medium(plan: ActionPlan) -> None:
    delete_actions = [a for a in plan.actions if a.action_type == ActionType.DELETE]
    risks = [a.risk_level for a in delete_actions]
    # Verify LOW appears before any MEDIUM in the DELETE section
    low_indices = [i for i, r in enumerate(risks) if r == RiskLevel.LOW]
    medium_indices = [i for i, r in enumerate(risks) if r == RiskLevel.MEDIUM]
    assert low_indices and medium_indices
    assert max(low_indices) < min(medium_indices)


def test_summary_total(planner: ActionPlanner, plan: ActionPlan) -> None:
    s = planner.summary(plan)
    # 5 unique sources after deduplication
    assert s["total"] == 5


def test_summary_by_risk(planner: ActionPlanner, plan: ActionPlan) -> None:
    s = planner.summary(plan)
    # LOW: vendor(ADD_GITIGNORE) + backup_old.php(DELETE) = 2
    # MEDIUM: config-20230816.php(DELETE) + utils_copy.php(DELETE) = 2
    # HIGH: saas/service.php(REPORT_ONLY) = 1
    assert s["by_risk"]["LOW"] == 2
    assert s["by_risk"]["MEDIUM"] == 2
    assert s["by_risk"]["HIGH"] == 1


def test_summary_by_type(planner: ActionPlanner, plan: ActionPlan) -> None:
    s = planner.summary(plan)
    assert s["by_type"]["ADD_GITIGNORE"] == 1
    assert s["by_type"]["DELETE"] == 3
    assert s["by_type"]["MOVE"] == 0
    assert s["by_type"]["REPORT_ONLY"] == 1


def test_empty_results() -> None:
    planner = ActionPlanner([], "/tmp/project")
    plan = planner.build_plan()
    assert isinstance(plan, ActionPlan)
    assert len(plan.actions) == 0
