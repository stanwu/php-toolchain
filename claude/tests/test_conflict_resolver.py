import pytest

from core.models import Action, ActionPlan, ActionType, RiskLevel
from planners.conflict_resolver import ConflictResolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_action(
    atype: ActionType,
    source: str,
    risk: RiskLevel = RiskLevel.LOW,
    dest: str | None = None,
    reason: str = "r",
) -> Action:
    return Action(atype, source, dest, risk, reason)


def make_plan(*actions: Action) -> ActionPlan:
    return ActionPlan(actions=list(actions))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_conflicts_unchanged() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "file1.php"),
        make_action(ActionType.MOVE, "file2.php", dest="archive/file2.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    assert len(resolved.actions) == 2


def test_delete_move_conflict_removes_delete() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php"),
        make_action(ActionType.MOVE, "utils.php", dest="archive/utils.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    types = [a.action_type for a in resolved.actions]
    assert ActionType.DELETE not in types


def test_delete_move_conflict_marks_move() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php"),
        make_action(ActionType.MOVE, "utils.php", dest="archive/utils.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    move = next(a for a in resolved.actions if a.action_type == ActionType.MOVE)
    assert move.conflict is True


def test_delete_move_conflict_upgrades_risk() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php"),
        make_action(ActionType.MOVE, "utils.php", dest="archive/utils.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    move = next(a for a in resolved.actions if a.action_type == ActionType.MOVE)
    assert move.risk_level == RiskLevel.HIGH


def test_duplicate_move_keeps_first() -> None:
    plan = make_plan(
        make_action(ActionType.MOVE, "foo.php", dest="dest1/foo.php"),
        make_action(ActionType.MOVE, "foo.php", dest="dest2/foo.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    moves = [a for a in resolved.actions if a.action_type == ActionType.MOVE]
    assert len(moves) == 1
    assert moves[0].destination == "dest1/foo.php"


def test_redundant_delete_under_gitignore_removed() -> None:
    plan = make_plan(
        make_action(ActionType.ADD_GITIGNORE, "vendor"),
        make_action(ActionType.DELETE, "vendor/x.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    types = [a.action_type for a in resolved.actions]
    assert ActionType.DELETE not in types


def test_delete_outside_gitignore_dir_kept() -> None:
    plan = make_plan(
        make_action(ActionType.ADD_GITIGNORE, "vendor"),
        make_action(ActionType.DELETE, "app/x.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    types = [a.action_type for a in resolved.actions]
    assert ActionType.DELETE in types


def test_move_chain_reordered() -> None:
    # A→B and B→C: B→C must execute first
    plan = make_plan(
        make_action(ActionType.MOVE, "a.php", dest="b.php"),
        make_action(ActionType.MOVE, "b.php", dest="c.php"),
    )
    resolved = ConflictResolver(plan).resolve()
    moves = [a for a in resolved.actions if a.action_type == ActionType.MOVE]
    sources = [m.source for m in moves]
    assert sources.index("b.php") < sources.index("a.php")


def test_conflict_report_populated() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "utils.php"),
        make_action(ActionType.MOVE, "utils.php", dest="archive/utils.php"),
    )
    resolver = ConflictResolver(plan)
    resolver.resolve()
    report = resolver.conflict_report()
    assert len(report) == 1


def test_conflict_report_empty_if_clean() -> None:
    plan = make_plan(
        make_action(ActionType.DELETE, "file1.php"),
    )
    resolver = ConflictResolver(plan)
    resolver.resolve()
    assert resolver.conflict_report() == []


def test_returns_action_plan() -> None:
    plan = make_plan()
    result = ConflictResolver(plan).resolve()
    assert isinstance(result, ActionPlan)
