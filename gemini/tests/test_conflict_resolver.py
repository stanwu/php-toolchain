import pytest
from core.models import Action, ActionPlan, ActionType, RiskLevel
from planners.conflict_resolver import ConflictResolver

# Helper to create actions for tests
def make_action(atype: ActionType, source: str, risk: RiskLevel = RiskLevel.LOW, dest: str | None = None, reason: str = "r") -> Action:
    return Action(action_type=atype, source=source, destination=dest, risk_level=risk, reason=reason)

# Helper to create a plan from actions
def make_plan(*actions: Action) -> ActionPlan:
    return ActionPlan(actions=list(actions))

def test_returns_action_plan():
    plan = make_plan()
    resolver = ConflictResolver(plan)
    result = resolver.resolve()
    assert isinstance(result, ActionPlan)

def test_no_conflicts_unchanged():
    actions = [
        make_action(ActionType.DELETE, "a.php"),
        make_action(ActionType.MOVE, "b.php", dest="c.php"),
    ]
    plan = make_plan(*actions)
    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()
    assert len(resolved_plan.actions) == 2

def test_delete_move_conflict_removes_delete():
    action1 = make_action(ActionType.DELETE, "utils.php")
    action2 = make_action(ActionType.MOVE, "utils.php", dest="helpers/utils.php")
    plan = make_plan(action1, action2)
    
    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()
    
    assert len(resolved_plan.actions) == 1
    assert resolved_plan.actions[0].action_type == ActionType.MOVE

def test_delete_move_conflict_marks_move():
    action1 = make_action(ActionType.DELETE, "utils.php")
    action2 = make_action(ActionType.MOVE, "utils.php", dest="helpers/utils.php", risk=RiskLevel.MEDIUM)
    plan = make_plan(action1, action2)

    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()
    
    kept_action = resolved_plan.actions[0]
    assert kept_action.conflict is True

def test_delete_move_conflict_upgrades_risk():
    action1 = make_action(ActionType.DELETE, "utils.php")
    action2 = make_action(ActionType.MOVE, "utils.php", dest="helpers/utils.php", risk=RiskLevel.MEDIUM)
    plan = make_plan(action1, action2)

    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()
    
    kept_action = resolved_plan.actions[0]
    assert kept_action.risk_level == RiskLevel.HIGH

def test_duplicate_move_keeps_first():
    action1 = make_action(ActionType.MOVE, "foo.php", dest="bar.php")
    action2 = make_action(ActionType.MOVE, "foo.php", dest="baz.php")
    plan = make_plan(action1, action2)

    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()

    assert len(resolved_plan.actions) == 1
    kept_action = resolved_plan.actions[0]
    assert kept_action.destination == "bar.php"
    assert kept_action.conflict is True

def test_redundant_delete_under_gitignore_removed():
    action1 = make_action(ActionType.ADD_GITIGNORE, "vendor")
    action2 = make_action(ActionType.DELETE, "vendor/x.php")
    plan = make_plan(action1, action2)

    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()

    assert len(resolved_plan.actions) == 1
    assert resolved_plan.actions[0].action_type == ActionType.ADD_GITIGNORE

def test_delete_outside_gitignore_dir_kept():
    action1 = make_action(ActionType.ADD_GITIGNORE, "vendor")
    action2 = make_action(ActionType.DELETE, "app/x.php")
    plan = make_plan(action1, action2)

    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()

    assert len(resolved_plan.actions) == 2
    assert any(a.action_type == ActionType.DELETE for a in resolved_plan.actions)

def test_move_chain_reordered():
    # A -> B, B -> C should become B -> C, then A -> B
    action_A_to_B = make_action(ActionType.MOVE, "a.php", dest="b.php")
    action_B_to_C = make_action(ActionType.MOVE, "b.php", dest="c.php")
    plan = make_plan(action_A_to_B, action_B_to_C)

    resolver = ConflictResolver(plan)
    resolved_plan = resolver.resolve()
    
    final_actions = resolved_plan.actions
    assert len(final_actions) == 2
    
    # B->C must come before A->B
    pos_B_to_C = final_actions.index(action_B_to_C)
    pos_A_to_B = final_actions.index(action_A_to_B)
    
    assert pos_B_to_C < pos_A_to_B
    assert action_A_to_B.conflict is True
    assert action_B_to_C.conflict is True

def test_conflict_report_populated():
    action1 = make_action(ActionType.DELETE, "utils.php")
    action2 = make_action(ActionType.MOVE, "utils.php", dest="helpers/utils.php")
    plan = make_plan(action1, action2)

    resolver = ConflictResolver(plan)
    resolver.resolve()
    report = resolver.conflict_report()

    assert len(report) == 1
    conflict = report[0]
    assert conflict["type"] == "DELETE+MOVE same source"
    assert conflict["source"] == "utils.php"

def test_conflict_report_empty_if_clean():
    plan = make_plan(make_action(ActionType.DELETE, "a.php"))
    resolver = ConflictResolver(plan)
    resolver.resolve()
    report = resolver.conflict_report()
    assert len(report) == 0
