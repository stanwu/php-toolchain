from core.models import (
    Action,
    ActionPlan,
    ActionType,
    DuplicateGroup,
    FileRecord,
    RiskLevel,
    validate_action,
)


def test_file_record_roundtrip() -> None:
    record = FileRecord(path="src/index.php", max_depth=3, total_branches=7, exists_on_disk=False)
    rebuilt = FileRecord.from_dict(record.to_dict())
    assert rebuilt == record


def test_action_roundtrip() -> None:
    action = Action(
        action_type=ActionType.MOVE,
        source="a.php",
        destination="b.php",
        risk_level=RiskLevel.MEDIUM,
        reason="Consolidate duplicates",
        conflict=True,
    )
    rebuilt = Action.from_dict(action.to_dict())
    assert rebuilt == action
    assert rebuilt.action_type is ActionType.MOVE
    assert rebuilt.risk_level is RiskLevel.MEDIUM


def test_action_plan_roundtrip() -> None:
    plan = ActionPlan(
        actions=[
            Action(
                action_type=ActionType.DELETE,
                source="backup_old.php",
                destination=None,
                risk_level=RiskLevel.LOW,
                reason="Old backup",
            ),
            Action(
                action_type=ActionType.ADD_GITIGNORE,
                source=".gitignore",
                destination=None,
                risk_level=RiskLevel.LOW,
                reason="Prevent future bloat",
            ),
        ],
        created_at="2026-02-27T00:00:00Z",
        project_dir="/tmp/project",
    )
    rebuilt = ActionPlan.from_dict(plan.to_dict())
    assert rebuilt == plan
    assert len(rebuilt.actions) == 2


def test_duplicate_group_roundtrip() -> None:
    group = DuplicateGroup(
        sha256="abc123",
        files=["a.php", "b.php"],
        canonical="a.php",
        copies=["b.php"],
    )
    rebuilt = DuplicateGroup.from_dict(group.to_dict())
    assert rebuilt == group


def test_validate_action_move_no_dest() -> None:
    errors = validate_action(
        Action(
            action_type=ActionType.MOVE,
            source="a.php",
            destination=None,
            risk_level=RiskLevel.MEDIUM,
            reason="Need move",
        )
    )
    assert any("destination" in e for e in errors)


def test_validate_action_delete_with_dest() -> None:
    errors = validate_action(
        Action(
            action_type=ActionType.DELETE,
            source="a.php",
            destination="b.php",
            risk_level=RiskLevel.LOW,
            reason="Should delete only",
        )
    )
    assert any("DELETE must NOT have a destination" in e for e in errors)


def test_validate_action_empty_reason() -> None:
    errors = validate_action(
        Action(
            action_type=ActionType.DELETE,
            source="a.php",
            destination=None,
            risk_level=RiskLevel.LOW,
            reason="",
        )
    )
    assert any("reason" in e for e in errors)


def test_validate_action_valid_delete() -> None:
    errors = validate_action(
        Action(
            action_type=ActionType.DELETE,
            source="a.php",
            destination=None,
            risk_level=RiskLevel.LOW,
            reason="Remove obsolete file",
        )
    )
    assert errors == []


def test_validate_action_valid_move() -> None:
    errors = validate_action(
        Action(
            action_type=ActionType.MOVE,
            source="a.php",
            destination="b.php",
            risk_level=RiskLevel.MEDIUM,
            reason="Relocate file",
        )
    )
    assert errors == []


def test_risk_level_ordering() -> None:
    assert RiskLevel.LOW < RiskLevel.MEDIUM < RiskLevel.HIGH


def test_risk_level_equality() -> None:
    assert RiskLevel.LOW == RiskLevel.LOW

