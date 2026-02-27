import pytest
from pathlib import Path
import os
import shutil

from core.models import Action, ActionType, RiskLevel
from executors.file_ops import FileOps

# Setup helper
def make_file(tmp_path: Path, rel_path: str, content: str = "<?php echo 1;"):
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p

@pytest.fixture
def file_ops(tmp_path: Path):
    project_dir = tmp_path / "project"
    backup_dir = tmp_path / "backup"
    project_dir.mkdir()
    backup_dir.mkdir()
    return FileOps(project_dir, backup_dir)

@pytest.fixture
def project_dir(file_ops: FileOps) -> Path:
    return file_ops.project_dir

@pytest.fixture
def backup_dir(file_ops: FileOps) -> Path:
    return file_ops.backup_dir

# Test _safe_resolve
def test_safe_resolve_valid_path(file_ops: FileOps, project_dir: Path):
    path = file_ops._safe_resolve("subdir/file.php")
    assert path == project_dir / "subdir" / "file.php"

def test_safe_resolve_raises_on_escape(file_ops: FileOps):
    with pytest.raises(ValueError, match="traversal"):
        file_ops._safe_resolve("../../etc/passwd")

# Test delete
def test_delete_removes_file(file_ops: FileOps, project_dir: Path):
    file_path = make_file(project_dir, "test.php")
    action = Action(ActionType.DELETE, "test.php", None, RiskLevel.LOW, "test")
    
    result = file_ops.delete(action)
    
    assert result["status"] == "ok"
    assert not file_path.exists()

def test_delete_creates_backup(file_ops: FileOps, project_dir: Path, backup_dir: Path):
    make_file(project_dir, "test.php", "content")
    action = Action(ActionType.DELETE, "test.php", None, RiskLevel.LOW, "test")
    
    file_ops.delete(action)
    
    backup_file = backup_dir / "test.php"
    assert backup_file.exists()
    assert backup_file.read_text() == "content"

def test_delete_returns_ok(file_ops: FileOps, project_dir: Path, backup_dir: Path):
    make_file(project_dir, "test.php")
    action = Action(ActionType.DELETE, "test.php", None, RiskLevel.LOW, "test")
    
    result = file_ops.delete(action)
    
    assert result["status"] == "ok"
    assert result["backup_path"] == str(backup_dir / "test.php")

def test_delete_nonexistent_returns_skipped(file_ops: FileOps):
    action = Action(ActionType.DELETE, "nonexistent.php", None, RiskLevel.LOW, "test")
    result = file_ops.delete(action)
    assert result["status"] == "skipped"
    assert "not found" in result["reason"]

def test_delete_removes_empty_parent(file_ops: FileOps, project_dir: Path):
    file_path = make_file(project_dir, "subdir/test.php")
    parent_dir = file_path.parent
    action = Action(ActionType.DELETE, "subdir/test.php", None, RiskLevel.LOW, "test")
    
    assert parent_dir.exists()
    file_ops.delete(action)
    assert not parent_dir.exists()

def test_delete_keeps_nonempty_parent(file_ops: FileOps, project_dir: Path):
    make_file(project_dir, "subdir/test1.php")
    file_to_delete = make_file(project_dir, "subdir/test2.php")
    parent_dir = file_to_delete.parent
    action = Action(ActionType.DELETE, "subdir/test2.php", None, RiskLevel.LOW, "test")
    
    file_ops.delete(action)
    
    assert parent_dir.exists()
    assert (project_dir / "subdir/test1.php").exists()

def test_delete_traversal_blocked(file_ops: FileOps):
    action = Action(ActionType.DELETE, "../../../etc/passwd", None, RiskLevel.HIGH, "malicious")
    result = file_ops.delete(action)
    assert result["status"] == "error"
    assert "traversal" in result["reason"]

# Test move
def test_move_moves_file(file_ops: FileOps, project_dir: Path):
    src_rel = "src/file.php"
    dst_rel = "dst/new_file.php"
    make_file(project_dir, src_rel)
    action = Action(ActionType.MOVE, src_rel, dst_rel, RiskLevel.LOW, "test")
    
    result = file_ops.move(action)
    
    assert result["status"] == "ok"
    assert (project_dir / dst_rel).exists()

def test_move_src_gone(file_ops: FileOps, project_dir: Path):
    src_rel = "src/file.php"
    dst_rel = "dst/new_file.php"
    src_path = make_file(project_dir, src_rel)
    action = Action(ActionType.MOVE, src_rel, dst_rel, RiskLevel.LOW, "test")
    
    file_ops.move(action)
    
    assert not src_path.exists()

def test_move_creates_parent_dirs(file_ops: FileOps, project_dir: Path):
    src_rel = "file.php"
    dst_rel = "a/b/c/new_file.php"
    make_file(project_dir, src_rel)
    action = Action(ActionType.MOVE, src_rel, dst_rel, RiskLevel.LOW, "test")
    
    file_ops.move(action)
    
    assert (project_dir / dst_rel).exists()

def test_move_creates_backup(file_ops: FileOps, project_dir: Path, backup_dir: Path):
    src_rel = "file.php"
    dst_rel = "new_file.php"
    make_file(project_dir, src_rel, "move content")
    action = Action(ActionType.MOVE, src_rel, dst_rel, RiskLevel.LOW, "test")
    
    file_ops.move(action)
    
    backup_file = backup_dir / src_rel
    assert backup_file.exists()
    assert backup_file.read_text() == "move content"

def test_move_returns_ok(file_ops: FileOps, project_dir: Path):
    src_rel = "file.php"
    dst_rel = "new_file.php"
    make_file(project_dir, src_rel)
    action = Action(ActionType.MOVE, src_rel, dst_rel, RiskLevel.LOW, "test")
    
    result = file_ops.move(action)
    
    assert result["status"] == "ok"
    assert "backup_path" in result

def test_move_fails_if_dest_exists(file_ops: FileOps, project_dir: Path):
    src_rel = "file.php"
    dst_rel = "existing.php"
    make_file(project_dir, src_rel)
    make_file(project_dir, dst_rel)
    action = Action(ActionType.MOVE, src_rel, dst_rel, RiskLevel.LOW, "test")
    
    result = file_ops.move(action)
    
    assert result["status"] == "error"
    assert "destination exists" in result["reason"]

def test_move_src_traversal_blocked(file_ops: FileOps):
    action = Action(ActionType.MOVE, "../src.php", "dst.php", RiskLevel.HIGH, "malicious")
    result = file_ops.move(action)
    assert result["status"] == "error"
    assert "traversal" in result["reason"]

def test_move_dst_traversal_blocked(file_ops: FileOps, project_dir: Path):
    make_file(project_dir, "src.php")
    action = Action(ActionType.MOVE, "src.php", "../dst.php", RiskLevel.HIGH, "malicious")
    result = file_ops.move(action)
    assert result["status"] == "error"
    assert "traversal" in result["reason"]

# Test rollback
def test_rollback_restores_deleted_file(file_ops: FileOps, project_dir: Path):
    file_path = make_file(project_dir, "delete_me.php", "deleted content")
    action = Action(ActionType.DELETE, "delete_me.php", None, RiskLevel.LOW, "test")
    
    log_entry = file_ops.delete(action)
    assert not file_path.exists()
    
    count = file_ops.rollback([log_entry])
    
    assert count == 1
    assert file_path.exists()
    assert file_path.read_text() == "deleted content"

def test_rollback_restores_moved_file(file_ops: FileOps, project_dir: Path):
    src_rel = "move_me.php"
    dst_rel = "moved.php"
    src_path = make_file(project_dir, src_rel, "moved content")
    dst_path = project_dir / dst_rel
    action = Action(ActionType.MOVE, src_rel, dst_rel, RiskLevel.LOW, "test")

    log_entry = file_ops.move(action)
    assert not src_path.exists()
    assert dst_path.exists()

    count = file_ops.rollback([log_entry])

    assert count == 1
    assert src_path.exists()
    assert src_path.read_text() == "moved content"
    assert not dst_path.exists()

def test_rollback_count(file_ops: FileOps, project_dir: Path):
    make_file(project_dir, "f1.php")
    make_file(project_dir, "f2.php")
    log = [
        file_ops.delete(Action(ActionType.DELETE, "f1.php", None, RiskLevel.LOW, "")),
        file_ops.delete(Action(ActionType.DELETE, "f2.php", None, RiskLevel.LOW, "")),
    ]
    
    count = file_ops.rollback(log)
    assert count == 2
    assert (project_dir / "f1.php").exists()
    assert (project_dir / "f2.php").exists()

def test_rollback_skips_non_ok_entries(file_ops: FileOps, project_dir: Path):
    make_file(project_dir, "f1.php")
    log = [
        file_ops.delete(Action(ActionType.DELETE, "f1.php", None, RiskLevel.LOW, "")),
        {"status": "skipped", "reason": "not found"},
        {"status": "error", "reason": "permission denied"},
    ]
    
    count = file_ops.rollback(log)
    assert count == 1
    assert (project_dir / "f1.php").exists()

def test_rollback_reverse_order(file_ops: FileOps, project_dir: Path):
    src_rel = "original.php"
    moved_rel = "moved/new.php"
    src_path = make_file(project_dir, src_rel, "content")

    action1 = Action(ActionType.MOVE, src_rel, moved_rel, RiskLevel.LOW, "move")
    log_entry1 = file_ops.move(action1)
    
    action2 = Action(ActionType.DELETE, moved_rel, None, RiskLevel.LOW, "delete")
    log_entry2 = file_ops.delete(action2)

    count = file_ops.rollback([log_entry1, log_entry2])

    assert count == 1
    assert src_path.exists()
    assert src_path.read_text() == "content"
    assert not (project_dir / moved_rel).exists()
