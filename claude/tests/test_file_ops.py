import shutil
from pathlib import Path

import pytest

from core.models import Action, ActionType, RiskLevel
from executors.file_ops import FileOps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_file(base: Path, rel_path: str, content: str = "<?php echo 1;") -> Path:
    p = base / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def make_action(
    action_type: ActionType,
    source: str,
    destination: str | None = None,
    risk: RiskLevel = RiskLevel.LOW,
) -> Action:
    return Action(
        action_type=action_type,
        source=source,
        destination=destination,
        risk_level=risk,
        reason="test",
    )


@pytest.fixture
def setup(tmp_path):
    project_dir = tmp_path / "project"
    backup_dir = tmp_path / "backup"
    project_dir.mkdir()
    backup_dir.mkdir()
    ops = FileOps(project_dir, backup_dir)
    return ops, project_dir, backup_dir


# ---------------------------------------------------------------------------
# delete() tests
# ---------------------------------------------------------------------------

def test_delete_removes_file(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "file.php")
    action = make_action(ActionType.DELETE, "file.php")
    ops.delete(action)
    assert not (project_dir / "file.php").exists()


def test_delete_creates_backup(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "file.php")
    action = make_action(ActionType.DELETE, "file.php")
    result = ops.delete(action)
    assert Path(result["backup_path"]).exists()


def test_delete_returns_ok(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "file.php")
    action = make_action(ActionType.DELETE, "file.php")
    result = ops.delete(action)
    assert result["status"] == "ok"
    assert "backup_path" in result


def test_delete_nonexistent_returns_skipped(setup):
    ops, project_dir, backup_dir = setup
    action = make_action(ActionType.DELETE, "nonexistent.php")
    result = ops.delete(action)
    assert result["status"] == "skipped"


def test_delete_removes_empty_parent(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "subdir/file.php")
    action = make_action(ActionType.DELETE, "subdir/file.php")
    ops.delete(action)
    assert not (project_dir / "subdir").exists()


def test_delete_keeps_nonempty_parent(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "subdir/file1.php")
    make_file(project_dir, "subdir/file2.php")
    action = make_action(ActionType.DELETE, "subdir/file1.php")
    ops.delete(action)
    assert (project_dir / "subdir").exists()
    assert (project_dir / "subdir" / "file2.php").exists()


# ---------------------------------------------------------------------------
# move() tests
# ---------------------------------------------------------------------------

def test_move_moves_file(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "src.php")
    action = make_action(ActionType.MOVE, "src.php", "dst.php")
    ops.move(action)
    assert (project_dir / "dst.php").exists()


def test_move_src_gone(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "src.php")
    action = make_action(ActionType.MOVE, "src.php", "dst.php")
    ops.move(action)
    assert not (project_dir / "src.php").exists()


def test_move_creates_parent_dirs(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "src.php")
    action = make_action(ActionType.MOVE, "src.php", "deep/nested/dst.php")
    ops.move(action)
    assert (project_dir / "deep" / "nested" / "dst.php").exists()


def test_move_creates_backup(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "src.php")
    action = make_action(ActionType.MOVE, "src.php", "dst.php")
    result = ops.move(action)
    assert Path(result["backup_path"]).exists()


def test_move_returns_ok(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "src.php")
    action = make_action(ActionType.MOVE, "src.php", "dst.php")
    result = ops.move(action)
    assert result["status"] == "ok"


def test_move_fails_if_dest_exists(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "src.php")
    make_file(project_dir, "dst.php")
    action = make_action(ActionType.MOVE, "src.php", "dst.php")
    result = ops.move(action)
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# rollback() tests
# ---------------------------------------------------------------------------

def test_rollback_restores_deleted_file(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "file.php", content="<?php // original")
    action = make_action(ActionType.DELETE, "file.php")
    result = ops.delete(action)
    assert not (project_dir / "file.php").exists()
    log = [{"status": result["status"], "backup_path": result["backup_path"]}]
    ops.rollback(backup_dir, log)
    assert (project_dir / "file.php").exists()


def test_rollback_count(setup):
    ops, project_dir, backup_dir = setup
    log = []
    for name in ["a.php", "b.php", "c.php"]:
        make_file(project_dir, name)
        action = make_action(ActionType.DELETE, name)
        result = ops.delete(action)
        log.append(result)
    count = ops.rollback(backup_dir, log)
    assert count == 3


def test_rollback_skips_non_ok_entries(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "real.php")
    action = make_action(ActionType.DELETE, "real.php")
    result = ops.delete(action)
    log = [
        {"status": "skipped", "backup_path": result["backup_path"]},
        {"status": "error", "backup_path": result["backup_path"]},
        {"status": "ok", "backup_path": result["backup_path"]},
    ]
    count = ops.rollback(backup_dir, log)
    assert count == 1


def test_rollback_reverse_order(tmp_path, monkeypatch):
    """Rollback processes log entries in reverse order (last action undone first)."""
    project_dir = tmp_path / "project"
    backup_dir = tmp_path / "backup"
    project_dir.mkdir()
    backup_dir.mkdir()
    ops = FileOps(project_dir, backup_dir)

    # Create 3 backup files with distinct names
    entries = []
    for i in range(3):
        bp = backup_dir / f"file_{i}.php"
        bp.write_text(f"content_{i}")
        entries.append({"status": "ok", "backup_path": str(bp)})

    # Track restoration order by intercepting shutil.copy2 (real copy still executes)
    restored_names: list[str] = []
    _original_copy2 = shutil.copy2

    def tracking_copy2(src, dst, **kwargs):
        restored_names.append(Path(src).name)
        return _original_copy2(src, dst)

    monkeypatch.setattr(shutil, "copy2", tracking_copy2)

    count = ops.rollback(backup_dir, entries)

    assert count == 3
    # Entries [file_0, file_1, file_2] reversed → [file_2, file_1, file_0]
    assert restored_names == ["file_2.php", "file_1.php", "file_0.php"]


# ---------------------------------------------------------------------------
# path traversal tests
# ---------------------------------------------------------------------------

def test_delete_traversal_blocked(setup):
    ops, project_dir, backup_dir = setup
    action = make_action(ActionType.DELETE, "../../etc/passwd")
    result = ops.delete(action)
    assert result["status"] == "error"
    assert "traversal" in result["reason"].lower()


def test_move_src_traversal_blocked(setup):
    ops, project_dir, backup_dir = setup
    action = make_action(ActionType.MOVE, "../outside.php", "dst.php")
    result = ops.move(action)
    assert result["status"] == "error"


def test_move_dst_traversal_blocked(setup):
    ops, project_dir, backup_dir = setup
    make_file(project_dir, "src.php")
    action = make_action(ActionType.MOVE, "src.php", "../outside.php")
    result = ops.move(action)
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# _safe_resolve() tests
# ---------------------------------------------------------------------------

def test_safe_resolve_valid_path(setup):
    ops, project_dir, backup_dir = setup
    result = ops._safe_resolve("subdir/file.php")
    assert result == (project_dir / "subdir" / "file.php").resolve()
    assert str(result).startswith(str(project_dir.resolve()))


def test_safe_resolve_raises_on_escape(setup):
    ops, project_dir, backup_dir = setup
    with pytest.raises(ValueError):
        ops._safe_resolve("../../etc/passwd")
