import pytest

from core.models import Action, ActionPlan, ActionType, BackupInfo, RiskLevel
from executors.safe_executor import SafeExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_plan(*actions: Action) -> ActionPlan:
    return ActionPlan(actions=list(actions))


def low_delete(src: str = "old.php") -> Action:
    return Action(ActionType.DELETE, src, None, RiskLevel.LOW, "test")


def medium_delete(src: str = "med.php") -> Action:
    return Action(ActionType.DELETE, src, None, RiskLevel.MEDIUM, "test")


def high_delete(src: str = "hi.php") -> Action:
    return Action(ActionType.DELETE, src, None, RiskLevel.HIGH, "test")


def _project_with_files(tmp_path, *filenames):
    """Create project dir with stub PHP files and return the dir path."""
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    for name in filenames:
        (project / name).write_text("<?php // stub ?>")
    return project


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------

def test_dry_run_returns_backup_info(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)
    executor = SafeExecutor(make_plan(low_delete()), project)
    result = executor.execute()
    assert isinstance(result, BackupInfo)


def test_dry_run_empty_action_log(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)
    executor = SafeExecutor(make_plan(low_delete(), medium_delete()), project)
    result = executor.execute()
    assert result.action_log == []


def test_dry_run_no_file_touched(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path, "old.php")
    target = project / "old.php"
    assert target.exists()

    executor = SafeExecutor(make_plan(low_delete("old.php")), project)
    executor.execute()

    assert target.exists()


def test_dry_run_true_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)
    executor = SafeExecutor(make_plan(), project)
    assert executor._dry_run is True


# ---------------------------------------------------------------------------
# Live-execution: LOW risk
# ---------------------------------------------------------------------------

def test_execute_low_no_confirm_needed(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path, "old.php")

    calls: list[str] = []
    executor = SafeExecutor(
        make_plan(low_delete("old.php")),
        project,
        dry_run=False,
        confirm_fn=lambda p: calls.append(p) or True,
    )
    executor.execute()

    assert calls == []


# ---------------------------------------------------------------------------
# Live-execution: MEDIUM risk
# ---------------------------------------------------------------------------

def test_execute_medium_calls_confirm_once(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)

    calls: list[str] = []
    plan = make_plan(
        medium_delete("med1.php"),
        medium_delete("med2.php"),
        medium_delete("med3.php"),
    )
    executor = SafeExecutor(
        plan,
        project,
        dry_run=False,
        confirm_fn=lambda p: calls.append(p) or True,
    )
    executor.execute()

    assert len(calls) == 1


def test_execute_medium_skipped_on_deny(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path, "med.php")

    executor = SafeExecutor(
        make_plan(medium_delete("med.php")),
        project,
        dry_run=False,
        confirm_fn=lambda p: False,
    )
    result = executor.execute()

    skipped = [e for e in result.action_log if e["status"] == "skipped"]
    assert len(skipped) == 1
    # File must still exist — action was not executed
    assert (project / "med.php").exists()


# ---------------------------------------------------------------------------
# Live-execution: HIGH risk
# ---------------------------------------------------------------------------

def test_execute_high_calls_confirm_per_action(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)

    calls: list[str] = []
    plan = make_plan(
        high_delete("hi1.php"),
        high_delete("hi2.php"),
        high_delete("hi3.php"),
    )
    executor = SafeExecutor(
        plan,
        project,
        dry_run=False,
        confirm_fn=lambda p: calls.append(p) or True,
    )
    executor.execute()

    assert len(calls) == 3


def test_execute_high_skipped_on_deny(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path, "hi.php")

    executor = SafeExecutor(
        make_plan(high_delete("hi.php")),
        project,
        dry_run=False,
        confirm_fn=lambda p: False,
    )
    result = executor.execute()

    skipped = [e for e in result.action_log if e["status"] == "skipped"]
    assert len(skipped) == 1
    assert (project / "hi.php").exists()


# ---------------------------------------------------------------------------
# Action log structure
# ---------------------------------------------------------------------------

def test_action_log_has_status(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)

    plan = make_plan(
        low_delete("low.php"),
        medium_delete("med.php"),
    )
    # deny MEDIUM batch → low executed, medium skipped
    executor = SafeExecutor(plan, project, dry_run=False, confirm_fn=lambda p: False)
    result = executor.execute()

    assert len(result.action_log) == 2
    valid_statuses = {"executed", "skipped", "error", "dry-run"}
    for entry in result.action_log:
        assert "status" in entry
        assert entry["status"] in valid_statuses


# ---------------------------------------------------------------------------
# Backup directory
# ---------------------------------------------------------------------------

def test_backup_dir_created(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)

    executor = SafeExecutor(
        make_plan(low_delete()),
        project,
        dry_run=False,
        confirm_fn=lambda p: True,
    )
    result = executor.execute()

    assert result.backup_dir.exists()


def test_backup_dir_not_created_in_dry_run(tmp_path, monkeypatch):
    backup_root = tmp_path / "backup"
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", backup_root)
    project = _project_with_files(tmp_path)

    executor = SafeExecutor(make_plan(low_delete()), project)  # dry_run=True
    executor.execute()

    assert not backup_root.exists()


def test_backup_dir_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", tmp_path / "backup")
    project = _project_with_files(tmp_path)

    executor = SafeExecutor(
        make_plan(low_delete()),
        project,
        dry_run=False,
        confirm_fn=lambda p: True,
    )
    result = executor.execute()

    mode = result.backup_dir.stat().st_mode & 0o777
    assert mode == 0o700
