from __future__ import annotations

from pathlib import Path

import executors.safe_executor as safe_executor_mod
from core.models import Action, ActionPlan, ActionType, BackupInfo, RiskLevel
from executors.safe_executor import SafeExecutor


def make_plan(*actions: Action) -> ActionPlan:
    return ActionPlan(actions=list(actions))


def low_delete(src: str = "old.php") -> Action:
    return Action(ActionType.DELETE, src, None, RiskLevel.LOW, "test")


def medium_delete(src: str = "med.php") -> Action:
    return Action(ActionType.DELETE, src, None, RiskLevel.MEDIUM, "test")


def high_delete(src: str = "hi.php") -> Action:
    return Action(ActionType.DELETE, src, None, RiskLevel.HIGH, "test")


def test_dry_run_returns_backup_info(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    plan = make_plan(low_delete("old.php"))
    info = SafeExecutor(plan, tmp_path).execute()
    assert isinstance(info, BackupInfo)


def test_dry_run_empty_action_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    plan = make_plan(low_delete("old.php"))
    info = SafeExecutor(plan, tmp_path).execute()
    assert info.action_log == []


def test_dry_run_no_file_touched(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    target = tmp_path / "old.php"
    target.write_text("x", encoding="utf-8")

    plan = make_plan(low_delete("old.php"))
    SafeExecutor(plan, tmp_path).execute()

    assert target.exists()


def test_dry_run_true_by_default(tmp_path: Path) -> None:
    plan = make_plan(low_delete("old.php"))
    ex = SafeExecutor(plan, tmp_path)
    assert ex.dry_run is True


def test_execute_low_no_confirm_needed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    target = tmp_path / "old.php"
    target.write_text("x", encoding="utf-8")

    def confirm_fn(_prompt: str) -> bool:
        raise AssertionError("confirm_fn should not be called for LOW actions")

    plan = make_plan(low_delete("old.php"))
    SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=confirm_fn).execute()

    assert not target.exists()


def test_execute_medium_calls_confirm_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    (tmp_path / "a.php").write_text("a", encoding="utf-8")
    (tmp_path / "b.php").write_text("b", encoding="utf-8")

    calls: list[str] = []

    def confirm_fn(prompt: str) -> bool:
        calls.append(prompt)
        return True

    plan = make_plan(medium_delete("a.php"), medium_delete("b.php"))
    SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=confirm_fn).execute()

    assert len(calls) == 1
    assert not (tmp_path / "a.php").exists()
    assert not (tmp_path / "b.php").exists()


def test_execute_medium_skipped_on_deny(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    target = tmp_path / "med.php"
    target.write_text("x", encoding="utf-8")

    def confirm_fn(_prompt: str) -> bool:
        return False

    plan = make_plan(medium_delete("med.php"))
    info = SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=confirm_fn).execute()

    assert target.exists()
    assert info.action_log[0]["status"] == "skipped"


def test_execute_high_calls_confirm_per_action(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    for name in ["1.php", "2.php", "3.php"]:
        (tmp_path / name).write_text("x", encoding="utf-8")

    calls: list[str] = []

    def confirm_fn(prompt: str) -> bool:
        calls.append(prompt)
        return True

    plan = make_plan(high_delete("1.php"), high_delete("2.php"), high_delete("3.php"))
    SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=confirm_fn).execute()

    assert len(calls) == 3
    assert not (tmp_path / "1.php").exists()
    assert not (tmp_path / "2.php").exists()
    assert not (tmp_path / "3.php").exists()


def test_execute_high_skipped_on_deny(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    for name in ["1.php", "2.php", "3.php"]:
        (tmp_path / name).write_text("x", encoding="utf-8")

    calls: list[str] = []

    def confirm_fn(prompt: str) -> bool:
        calls.append(prompt)
        return len(calls) != 2  # deny second

    plan = make_plan(high_delete("1.php"), high_delete("2.php"), high_delete("3.php"))
    SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=confirm_fn).execute()

    assert len(calls) == 3
    assert not (tmp_path / "1.php").exists()
    assert (tmp_path / "2.php").exists()
    assert not (tmp_path / "3.php").exists()


def test_action_log_has_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    (tmp_path / "old.php").write_text("x", encoding="utf-8")

    plan = make_plan(low_delete("old.php"))
    info = SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=lambda _p: True).execute()

    assert info.action_log
    for entry in info.action_log:
        assert "status" in entry


def test_backup_dir_created(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    (tmp_path / "old.php").write_text("x", encoding="utf-8")

    plan = make_plan(low_delete("old.php"))
    info = SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=lambda _p: True).execute()

    assert info.backup_dir.exists()
    assert info.backup_dir.is_dir()


def test_backup_dir_not_created_in_dry_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    (tmp_path / "old.php").write_text("x", encoding="utf-8")

    plan = make_plan(low_delete("old.php"))
    info = SafeExecutor(plan, tmp_path, dry_run=True, confirm_fn=lambda _p: True).execute()

    assert not info.backup_dir.exists()


def test_backup_dir_permissions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", tmp_path / "backup-root")
    (tmp_path / "old.php").write_text("x", encoding="utf-8")

    plan = make_plan(low_delete("old.php"))
    info = SafeExecutor(plan, tmp_path, dry_run=False, confirm_fn=lambda _p: True).execute()

    mode = info.backup_dir.stat().st_mode & 0o777
    assert mode == 0o700

