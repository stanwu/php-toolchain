import pytest
from datetime import datetime, timezone
from typing import Optional

from planners.action_planner import ActionPlanner
from core.models import AnalysisResult, Action, ActionType, RiskLevel, ActionPlan

# Helper to create actions for tests
def make_action(atype: ActionType, source: str, risk: RiskLevel, dest: Optional[str] = None) -> Action:
    return Action(action_type=atype, source=source, destination=dest, risk_level=risk, reason=f"reason for {source}")

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
PROJECT_DIR = "/path/to/project"

@pytest.fixture
def planner() -> ActionPlanner:
    return ActionPlanner(results=ALL_RESULTS, project_dir=PROJECT_DIR)

@pytest.fixture
def plan(planner: ActionPlanner) -> ActionPlan:
    return planner.build_plan()

def test_returns_action_plan(plan: ActionPlan):
    assert isinstance(plan, ActionPlan)

def test_plan_has_project_dir(plan: ActionPlan):
    assert plan.project_dir == PROJECT_DIR

def test_plan_has_created_at(plan: ActionPlan):
    assert isinstance(plan.created_at, str)
    assert len(plan.created_at) > 0
    # Check if it's a valid ISO 8601 format
    parsed_time = datetime.fromisoformat(plan.created_at)
    assert parsed_time.tzinfo is not None

def test_dedup_keeps_lower_risk(plan: ActionPlan):
    actions = [a for a in plan.actions if a.source == "backup_old.php"]
    assert len(actions) == 1
    assert actions[0].risk_level == RiskLevel.LOW
    assert actions[0].action_type == ActionType.DELETE

def test_dedup_unique_sources_kept(plan: ActionPlan):
    sources = {a.source for a in plan.actions}
    expected_sources = {"vendor", "backup_old.php", "config-20230816.php", "utils_copy.php", "saas/service.php"}
    assert sources == expected_sources

def test_sort_gitignore_first(plan: ActionPlan):
    assert plan.actions[0].action_type == ActionType.ADD_GITIGNORE
    assert plan.actions[0].source == "vendor"

def test_sort_report_only_last(plan: ActionPlan):
    assert plan.actions[-1].action_type == ActionType.REPORT_ONLY
    assert plan.actions[-1].source == "saas/service.php"

def test_sort_low_before_medium(plan: ActionPlan):
    delete_actions = [a for a in plan.actions if a.action_type == ActionType.DELETE]
    
    # backup_old.php (LOW) should come before config-20230816.php (MEDIUM)
    # and utils_copy.php (MEDIUM)
    low_risk_delete = next(a for a in delete_actions if a.risk_level == RiskLevel.LOW)
    medium_risk_deletes = [a for a in delete_actions if a.risk_level == RiskLevel.MEDIUM]

    low_risk_index = plan.actions.index(low_risk_delete)
    medium_risk_indices = [plan.actions.index(a) for a in medium_risk_deletes]

    assert all(low_risk_index < i for i in medium_risk_indices)

    # Also check alphabetical sort within medium risk
    medium_sources = [a.source for a in medium_risk_deletes]
    assert sorted(medium_sources) == medium_sources # e.g. 'config...' before 'utils...'

def test_summary(planner: ActionPlanner, plan: ActionPlan):
    summary = planner.summary(plan)
    assert summary["total"] == 5
    assert summary["by_risk"] == {"LOW": 2, "MEDIUM": 2, "HIGH": 1}
    assert summary["by_type"] == {
        "ADD_GITIGNORE": 1,
        "DELETE": 3,
        "MOVE": 0,
        "REPORT_ONLY": 1
    }

def test_summary_total(planner: ActionPlanner, plan: ActionPlan):
    summary = planner.summary(plan)
    assert summary["total"] == 5

def test_summary_by_risk(planner: ActionPlanner, plan: ActionPlan):
    summary = planner.summary(plan)
    assert summary["by_risk"] == {"LOW": 2, "MEDIUM": 2, "HIGH": 1}

def test_summary_by_type(planner: ActionPlanner, plan: ActionPlan):
    summary = planner.summary(plan)
    assert summary["by_type"] == {
        "ADD_GITIGNORE": 1,
        "DELETE": 3,
        "MOVE": 0,
        "REPORT_ONLY": 1
    }

def test_empty_results():
    empty_planner = ActionPlanner(results=[], project_dir="/dev/null")
    plan = empty_planner.build_plan()
    summary = empty_planner.summary(plan)
    
    assert isinstance(plan, ActionPlan)
    assert len(plan.actions) == 0
    assert summary["total"] == 0
    assert summary["by_risk"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    assert summary["by_type"] == {"DELETE": 0, "MOVE": 0, "ADD_GITIGNORE": 0, "REPORT_ONLY": 0}
