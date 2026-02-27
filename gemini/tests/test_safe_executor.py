import pytest
from pathlib import Path
import logging
from unittest.mock import MagicMock, call

from core.models import ActionPlan, Action, ActionType, RiskLevel, BackupInfo
from executors.safe_executor import SafeExecutor, BACKUP_ROOT

# Helper functions to create actions
def make_plan(*actions):
    return ActionPlan(actions=list(actions))

def low_delete(src="old.php"):
    return Action(ActionType.DELETE, src, None, RiskLevel.LOW, "test low")

def medium_delete(src="med.php"):
    return Action(ActionType.DELETE, src, None, RiskLevel.MEDIUM, "test medium")

def high_delete(src="hi.php"):
    return Action(ActionType.DELETE, src, None, RiskLevel.HIGH, "test high")

@pytest.fixture(autouse=True)
def isolated_backup_root(monkeypatch, tmp_path):
    """Ensures that all tests use a temporary directory for backups."""
    temp_backup_root = tmp_path / ".php-cleanup-backup"
    # No need to mkdir, the executor should do it.
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", temp_backup_root)
    return temp_backup_root

@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "project"
    d.mkdir()
    (d / "old.php").touch()
    (d / "med.php").touch()
    (d / "hi.php").touch()
    (d / "hi2.php").touch()
    (d / "hi3.php").touch()
    return d

def test_dry_run_returns_backup_info(project_dir):
    plan = make_plan(low_delete())
    executor = SafeExecutor(plan, project_dir, dry_run=True)
    result = executor.execute()
    assert isinstance(result, BackupInfo)

def test_dry_run_empty_action_log(project_dir):
    plan = make_plan(low_delete())
    executor = SafeExecutor(plan, project_dir, dry_run=True)
    backup_info = executor.execute()
    assert backup_info.action_log == []

def test_dry_run_no_file_touched(project_dir):
    file_to_delete = project_dir / "old.php"
    assert file_to_delete.exists()
    
    plan = make_plan(low_delete(src="old.php"))
    executor = SafeExecutor(plan, project_dir, dry_run=True)
    executor.execute()
    
    assert file_to_delete.exists()

def test_dry_run_true_by_default(project_dir):
    plan = make_plan(low_delete())
    executor = SafeExecutor(plan, project_dir) # No dry_run flag
    assert executor.dry_run is True

def test_execute_low_no_confirm_needed(project_dir):
    confirm_mock = MagicMock(return_value=False) # Should not be called
    plan = make_plan(low_delete())
    
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=confirm_mock)
    executor.execute()
    
    confirm_mock.assert_not_called()
    assert len(executor.action_log) == 1
    assert executor.action_log[0]["status"] == "ok"

def test_execute_medium_calls_confirm_once(project_dir):
    confirm_mock = MagicMock(return_value=True)
    plan = make_plan(medium_delete("med1.php"), medium_delete("med2.php"))
    
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=confirm_mock)
    executor.execute()
    
    confirm_mock.assert_called_once_with("Proceed with batch of 2 MEDIUM risk actions? [y/N]")
    assert len(executor.action_log) == 2

def test_execute_medium_skipped_on_deny(project_dir):
    confirm_mock = MagicMock(return_value=False)
    plan = make_plan(medium_delete())
    
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=confirm_mock)
    executor.execute()
    
    confirm_mock.assert_called_once()
    assert len(executor.action_log) == 1
    assert executor.action_log[0]["status"] == "skipped"

def test_execute_high_calls_confirm_per_action(project_dir):
    confirm_mock = MagicMock(return_value=True)
    actions = [high_delete("hi.php"), high_delete("hi2.php"), high_delete("hi3.php")]
    plan = make_plan(*actions)
    
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=confirm_mock)
    executor.execute()
    
    assert confirm_mock.call_count == 3
    expected_calls = [
        call("Execute HIGH risk action: DELETE hi.php? (test high) [y/N]"),
        call("Execute HIGH risk action: DELETE hi2.php? (test high) [y/N]"),
        call("Execute HIGH risk action: DELETE hi3.php? (test high) [y/N]"),
    ]
    confirm_mock.assert_has_calls(expected_calls)
    assert len(executor.action_log) == 3

def test_execute_high_skipped_on_deny(project_dir):
    # Deny the first, approve the second
    confirm_mock = MagicMock(side_effect=[False, True])
    actions = [high_delete("hi.php"), high_delete("hi2.php")]
    plan = make_plan(*actions)
    
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=confirm_mock)
    executor.execute()
    
    assert confirm_mock.call_count == 2
    assert len(executor.action_log) == 2
    assert executor.action_log[0]["status"] == "skipped"
    assert executor.action_log[1]["status"] == "ok"

def test_action_log_has_status(project_dir):
    confirm_mock = MagicMock(side_effect=[False, True]) # Deny medium, approve high
    plan = make_plan(low_delete(), medium_delete(), high_delete())
    
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=confirm_mock)
    result = executor.execute()
    
    assert len(result.action_log) == 3
    assert result.action_log[0]["status"] == "ok" # LOW
    assert result.action_log[1]["status"] == "skipped"  # MEDIUM
    assert result.action_log[2]["status"] == "ok" # HIGH

def test_backup_dir_created(project_dir, isolated_backup_root):
    plan = make_plan(low_delete())
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=lambda p: True)
    result = executor.execute()
    
    assert result.backup_dir is not None
    assert result.backup_dir.exists()
    assert result.backup_dir.is_dir()
    assert isolated_backup_root in result.backup_dir.parents

def test_backup_dir_not_created_in_dry_run(project_dir, isolated_backup_root):
    plan = make_plan(low_delete())
    executor = SafeExecutor(plan, project_dir, dry_run=True)
    result = executor.execute()
    
    assert result.backup_dir is None
    # Check that the temporary backup root is empty
    assert not isolated_backup_root.exists() or not any(isolated_backup_root.iterdir())

def test_backup_dir_permissions(project_dir, isolated_backup_root):
    plan = make_plan(low_delete())
    executor = SafeExecutor(plan, project_dir, dry_run=False, confirm_fn=lambda p: True)
    result = executor.execute()
    
    assert result.backup_dir.stat().st_mode & 0o777 == 0o700
