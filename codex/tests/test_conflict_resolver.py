from __future__ import annotations

from core.models import Action, ActionPlan, ActionType, RiskLevel
from planners.conflict_resolver import ConflictResolver


def make_action(
    atype: ActionType, source: str, risk: RiskLevel = RiskLevel.LOW, dest: str | None = None, reason: str = "r"
) -> Action:
    return Action(atype, source, dest, risk, reason)


def make_plan(*actions: Action) -> ActionPlan:
    return ActionPlan(actions=list(actions))


def test_returns_action_plan() -> None:
    plan = make_plan(make_action(ActionType.DELETE, "a.php"))
    resolved = ConflictResolver(plan).resolve()
    assert isinstance(resolved, ActionPlan)


def test_no_conflicts_unchanged() -> None:
    plan = make_plan(
        make_action(ActionType.ADD_GITIGNORE, "vendor"),
        make_action(ActionType.DELETE, "app/x.php"),
        make_action(ActionType.MOVE, "a.php", dest="b.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    assert len(resolved.actions) == len(plan.actions)


def test_delete_move_conflict_removes_delete() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php"),
        make_action(ActionType.MOVE, "utils.php", dest="lib/utils.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    assert [a.action_type for a in resolved.actions] == [ActionType.MOVE]


def test_delete_move_conflict_marks_move() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php"),
        make_action(ActionType.MOVE, "utils.php", dest="lib/utils.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    assert resolved.actions[0].action_type == ActionType.MOVE
    assert resolved.actions[0].conflict is True


def test_delete_move_conflict_upgrades_risk() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php", risk=RiskLevel.LOW),
        make_action(ActionType.MOVE, "utils.php", risk=RiskLevel.LOW, dest="lib/utils.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    assert resolved.actions[0].risk_level == RiskLevel.HIGH


def test_duplicate_move_keeps_first() -> None:
    first = make_action(ActionType.MOVE, "foo.php", risk=RiskLevel.MEDIUM, dest="a/foo.php")
    second = make_action(ActionType.MOVE, "foo.php", risk=RiskLevel.HIGH, dest="b/foo.php")
    plan = make_plan(first, second)
    resolved = ConflictResolver(plan).resolve()
    assert len(resolved.actions) == 1
    assert resolved.actions[0].destination == "a/foo.php"


def test_redundant_delete_under_gitignore_removed() -> None:
    plan = make_plan(
        make_action(ActionType.ADD_GITIGNORE, "vendor"),
        make_action(ActionType.DELETE, "vendor/x.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    assert len(resolved.actions) == 1
    assert resolved.actions[0].action_type == ActionType.ADD_GITIGNORE


def test_delete_outside_gitignore_dir_kept() -> None:
    plan = make_plan(
        make_action(ActionType.ADD_GITIGNORE, "vendor"),
        make_action(ActionType.DELETE, "app/x.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    assert any(a.action_type == ActionType.DELETE and a.source == "app/x.php" for a in resolved.actions)


def test_move_chain_reordered() -> None:
    # A->B, and B->C must happen first.
    move_a = make_action(ActionType.MOVE, "A.php", dest="B.php")
    move_b = make_action(ActionType.MOVE, "B.php", dest="C.php")
    plan = make_plan(move_a, move_b)
    resolved = ConflictResolver(plan).resolve()
    assert [a.source for a in resolved.actions] == ["B.php", "A.php"]
    assert [a.destination for a in resolved.actions] == ["C.php", "B.php"]


def test_conflict_report_populated() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php"),
        make_action(ActionType.MOVE, "utils.php", dest="lib/utils.php"),
    )
    resolver = ConflictResolver(plan)
    resolver.resolve()
    report = resolver.conflict_report()
    assert len(report) == 1
    assert report[0]["type"] == "DELETE_MOVE_SAME_SOURCE"


def test_conflict_report_empty_if_clean() -> None:
    plan = make_plan(make_action(ActionType.DELETE, "a.php"))
    resolver = ConflictResolver(plan)
    resolver.resolve()
    assert resolver.conflict_report() == []

