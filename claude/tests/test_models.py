import pytest
from core.models import (
    Action,
    ActionPlan,
    ActionType,
    BranchRecord,
    DuplicateGroup,
    FileRecord,
    FunctionRecord,
    RiskLevel,
    validate_action,
)


def test_file_record_roundtrip() -> None:
    record = FileRecord(
        path="some/path/file.php",
        max_depth=3,
        total_branches=7,
        exists_on_disk=False,
    )
    restored = FileRecord.from_dict(record.to_dict())
    assert restored.path == record.path
    assert restored.max_depth == record.max_depth
    assert restored.total_branches == record.total_branches
    assert restored.exists_on_disk == record.exists_on_disk


def test_action_roundtrip() -> None:
    action = Action(
        action_type=ActionType.MOVE,
        source="old/path.php",
        destination="new/path.php",
        risk_level=RiskLevel.MEDIUM,
        reason="Reorganizing structure",
        conflict=True,
    )
    restored = Action.from_dict(action.to_dict())
    assert restored.action_type == action.action_type
    assert restored.source == action.source
    assert restored.destination == action.destination
    assert restored.risk_level == action.risk_level
    assert restored.reason == action.reason
    assert restored.conflict == action.conflict


def test_action_plan_roundtrip() -> None:
    plan = ActionPlan(
        actions=[
            Action(
                action_type=ActionType.DELETE,
                source="vendor/old.php",
                destination=None,
                risk_level=RiskLevel.LOW,
                reason="Unused vendor file",
            ),
            Action(
                action_type=ActionType.ADD_GITIGNORE,
                source=".gitignore",
                destination=None,
                risk_level=RiskLevel.LOW,
                reason="Add gitignore entry",
            ),
        ],
        created_at="2026-02-27T00:00:00",
        project_dir="/var/www/project",
    )
    restored = ActionPlan.from_dict(plan.to_dict())
    assert restored.created_at == plan.created_at
    assert restored.project_dir == plan.project_dir
    assert len(restored.actions) == 2
    assert restored.actions[0].action_type == ActionType.DELETE
    assert restored.actions[1].action_type == ActionType.ADD_GITIGNORE


def test_duplicate_group_roundtrip() -> None:
    group = DuplicateGroup(
        sha256="abc123def456",
        files=["a/file.php", "b/file.php", "c/file.php"],
        canonical="a/file.php",
        copies=["b/file.php", "c/file.php"],
    )
    restored = DuplicateGroup.from_dict(group.to_dict())
    assert restored.sha256 == group.sha256
    assert restored.files == group.files
    assert restored.canonical == group.canonical
    assert restored.copies == group.copies


def test_validate_action_move_no_dest() -> None:
    action = Action(
        action_type=ActionType.MOVE,
        source="some/file.php",
        destination=None,
        risk_level=RiskLevel.LOW,
        reason="Moving file",
    )
    errors = validate_action(action)
    assert len(errors) > 0
    assert any("destination" in e for e in errors)


def test_validate_action_delete_with_dest() -> None:
    action = Action(
        action_type=ActionType.DELETE,
        source="some/file.php",
        destination="somewhere/else.php",
        risk_level=RiskLevel.HIGH,
        reason="Removing duplicate",
    )
    errors = validate_action(action)
    assert len(errors) > 0
    assert any("destination" in e for e in errors)


def test_validate_action_empty_reason() -> None:
    action = Action(
        action_type=ActionType.DELETE,
        source="some/file.php",
        destination=None,
        risk_level=RiskLevel.LOW,
        reason="",
    )
    errors = validate_action(action)
    assert len(errors) > 0
    assert any("reason" in e for e in errors)


def test_validate_action_valid_delete() -> None:
    action = Action(
        action_type=ActionType.DELETE,
        source="vendor/unused.php",
        destination=None,
        risk_level=RiskLevel.LOW,
        reason="Unused vendor file",
    )
    errors = validate_action(action)
    assert errors == []


def test_validate_action_valid_move() -> None:
    action = Action(
        action_type=ActionType.MOVE,
        source="old/location.php",
        destination="new/location.php",
        risk_level=RiskLevel.MEDIUM,
        reason="Reorganizing directory structure",
    )
    errors = validate_action(action)
    assert errors == []


def test_risk_level_ordering() -> None:
    assert RiskLevel.LOW < RiskLevel.MEDIUM
    assert RiskLevel.MEDIUM < RiskLevel.HIGH
    assert RiskLevel.LOW < RiskLevel.HIGH
    assert not (RiskLevel.HIGH < RiskLevel.LOW)
    assert not (RiskLevel.MEDIUM < RiskLevel.LOW)


def test_risk_level_equality() -> None:
    assert RiskLevel.LOW == RiskLevel.LOW
    assert RiskLevel.MEDIUM == RiskLevel.MEDIUM
    assert RiskLevel.HIGH == RiskLevel.HIGH
    assert not (RiskLevel.LOW == RiskLevel.MEDIUM)
