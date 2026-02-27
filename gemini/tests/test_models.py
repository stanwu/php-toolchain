import pytest
from core.models import (
    FileRecord,
    Action,
    ActionPlan,
    DuplicateGroup,
    ActionType,
    RiskLevel,
    validate_action,
)

def test_file_record_roundtrip():
    """to_dict() → from_dict() preserves all fields"""
    original = FileRecord(path="a/b.php", max_depth=10, total_branches=20, exists_on_disk=False)
    d = original.to_dict()
    reconstructed = FileRecord.from_dict(d)
    assert original == reconstructed

def test_action_roundtrip():
    """Same for Action (including Enum fields)"""
    original = Action(
        action_type=ActionType.MOVE,
        source="a/b.php",
        destination="c/d.php",
        risk_level=RiskLevel.MEDIUM,
        reason="Refactoring",
        conflict=True
    )
    d = original.to_dict()
    assert d['action_type'] == "MOVE"
    assert d['risk_level'] == "MEDIUM"
    reconstructed = Action.from_dict(d)
    assert original == reconstructed

def test_action_plan_roundtrip():
    """ActionPlan with 2 actions survives roundtrip"""
    action1 = Action(
        action_type=ActionType.DELETE,
        source="a/b.php",
        destination=None,
        risk_level=RiskLevel.HIGH,
        reason="Obsolete file"
    )
    action2 = Action(
        action_type=ActionType.MOVE,
        source="c/d.php",
        destination="e/f.php",
        risk_level=RiskLevel.LOW,
        reason="Restructure"
    )
    original = ActionPlan(
        actions=[action1, action2],
        created_at="2026-02-27T12:00:00Z",
        project_dir="/path/to/project"
    )
    d = original.to_dict()
    reconstructed = ActionPlan.from_dict(d)
    assert original == reconstructed
    assert len(reconstructed.actions) == 2
    assert reconstructed.actions[0].risk_level == RiskLevel.HIGH

def test_duplicate_group_roundtrip():
    """DuplicateGroup roundtrip"""
    original = DuplicateGroup(
        sha256="abc",
        files=["a.php", "b.php"],
        canonical="a.php",
        copies=["b.php"]
    )
    d = original.to_dict()
    reconstructed = DuplicateGroup.from_dict(d)
    assert original == reconstructed

def test_validate_action_move_no_dest():
    """MOVE with destination=None → returns error"""
    action = Action(
        action_type=ActionType.MOVE,
        source="a.php",
        destination=None,
        risk_level=RiskLevel.LOW,
        reason="test"
    )
    errors = validate_action(action)
    assert len(errors) > 0
    assert "MOVE action must have a non-empty destination." in errors[0]

def test_validate_action_delete_with_dest():
    """DELETE with destination set → returns error"""
    action = Action(
        action_type=ActionType.DELETE,
        source="a.php",
        destination="b.php",
        risk_level=RiskLevel.LOW,
        reason="test"
    )
    errors = validate_action(action)
    assert len(errors) > 0
    assert "DELETE action must not have a destination." in errors[0]

def test_validate_action_empty_reason():
    """Empty reason → returns error"""
    action = Action(
        action_type=ActionType.DELETE,
        source="a.php",
        destination=None,
        risk_level=RiskLevel.LOW,
        reason=""
    )
    errors = validate_action(action)
    assert len(errors) > 0
    assert "Action must have a non-empty reason." in errors[0]

def test_validate_action_valid_delete():
    """Valid DELETE → empty error list"""
    action = Action(
        action_type=ActionType.DELETE,
        source="a.php",
        destination=None,
        risk_level=RiskLevel.LOW,
        reason="test"
    )
    errors = validate_action(action)
    assert len(errors) == 0

def test_validate_action_valid_move():
    """Valid MOVE with destination → empty error list"""
    action = Action(
        action_type=ActionType.MOVE,
        source="a.php",
        destination="b.php",
        risk_level=RiskLevel.LOW,
        reason="test"
    )
    errors = validate_action(action)
    assert len(errors) == 0

def test_risk_level_ordering():
    """LOW < MEDIUM < HIGH evaluates to True"""
    assert RiskLevel.LOW < RiskLevel.MEDIUM
    assert RiskLevel.MEDIUM < RiskLevel.HIGH
    assert RiskLevel.LOW < RiskLevel.HIGH
    assert not (RiskLevel.MEDIUM < RiskLevel.LOW)
    assert RiskLevel.MEDIUM <= RiskLevel.MEDIUM
    assert RiskLevel.HIGH >= RiskLevel.MEDIUM

def test_risk_level_equality():
    """LOW == LOW evaluates to True"""
    assert RiskLevel.LOW == RiskLevel.LOW
    assert RiskLevel.LOW != RiskLevel.HIGH