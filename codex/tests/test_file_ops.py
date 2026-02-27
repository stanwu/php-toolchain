from __future__ import annotations

from pathlib import Path

import pytest

from core.models import Action, ActionType, RiskLevel
from executors.file_ops import FileOps


def make_file(tmp_path: Path, rel_path: str, content: str = "<?php echo 1;") -> Path:
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def delete_action(src: str) -> Action:
    return Action(ActionType.DELETE, src, None, RiskLevel.LOW, "test")


def move_action(src: str, dst: str) -> Action:
    return Action(ActionType.MOVE, src, dst, RiskLevel.LOW, "test")


def test_delete_removes_file(tmp_path: Path) -> None:
    make_file(tmp_path, "old.php")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.delete(delete_action("old.php"))

    assert res["status"] == "ok"
    assert not (tmp_path / "old.php").exists()


def test_delete_creates_backup(tmp_path: Path) -> None:
    make_file(tmp_path, "old.php", content="x")
    backup_dir = tmp_path / "backup"
    ops = FileOps(project_dir=tmp_path, backup_dir=backup_dir)

    res = ops.delete(delete_action("old.php"))

    assert res["status"] == "ok"
    assert (backup_dir / "old.php").exists()
    assert (backup_dir / "old.php").read_text(encoding="utf-8") == "x"


def test_delete_returns_ok(tmp_path: Path) -> None:
    make_file(tmp_path, "old.php")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.delete(delete_action("old.php"))

    assert res["status"] == "ok"
    assert "backup_path" in res
    assert res["backup_path"]


def test_delete_nonexistent_returns_skipped(tmp_path: Path) -> None:
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.delete(delete_action("missing.php"))

    assert res["status"] == "skipped"


def test_delete_removes_empty_parent(tmp_path: Path) -> None:
    make_file(tmp_path, "subdir/old.php")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.delete(delete_action("subdir/old.php"))

    assert res["status"] == "ok"
    assert not (tmp_path / "subdir").exists()


def test_delete_keeps_nonempty_parent(tmp_path: Path) -> None:
    make_file(tmp_path, "subdir/a.php")
    make_file(tmp_path, "subdir/b.php")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.delete(delete_action("subdir/a.php"))

    assert res["status"] == "ok"
    assert (tmp_path / "subdir").exists()
    assert (tmp_path / "subdir/b.php").exists()


def test_move_moves_file(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php", content="hello")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.move(move_action("a.php", "b.php"))

    assert res["status"] == "ok"
    assert (tmp_path / "b.php").exists()
    assert (tmp_path / "b.php").read_text(encoding="utf-8") == "hello"


def test_move_src_gone(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.move(move_action("a.php", "b.php"))

    assert res["status"] == "ok"
    assert not (tmp_path / "a.php").exists()


def test_move_creates_parent_dirs(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.move(move_action("a.php", "deep/nested/dir/b.php"))

    assert res["status"] == "ok"
    assert (tmp_path / "deep/nested/dir/b.php").exists()


def test_move_creates_backup(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php", content="z")
    backup_dir = tmp_path / "backup"
    ops = FileOps(project_dir=tmp_path, backup_dir=backup_dir)

    res = ops.move(move_action("a.php", "b.php"))

    assert res["status"] == "ok"
    assert (backup_dir / "a.php").exists()
    assert (backup_dir / "a.php").read_text(encoding="utf-8") == "z"


def test_move_returns_ok(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.move(move_action("a.php", "b.php"))

    assert res["status"] == "ok"
    assert "backup_path" in res


def test_move_fails_if_dest_exists(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php", content="src")
    make_file(tmp_path, "b.php", content="dst")
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    res = ops.move(move_action("a.php", "b.php"))

    assert res["status"] == "error"
    assert "exists" in res.get("reason", "")
    assert (tmp_path / "a.php").exists()
    assert (tmp_path / "a.php").read_text(encoding="utf-8") == "src"
    assert (tmp_path / "b.php").read_text(encoding="utf-8") == "dst"


def test_rollback_restores_deleted_file(tmp_path: Path) -> None:
    make_file(tmp_path, "old.php", content="restore-me")
    backup_dir = tmp_path / "backup"
    ops = FileOps(project_dir=tmp_path, backup_dir=backup_dir)

    action = delete_action("old.php")
    res = ops.delete(action)
    assert res["status"] == "ok"
    assert not (tmp_path / "old.php").exists()

    count = ops.rollback(backup_dir, [{"action": action, **res}])

    assert count == 1
    assert (tmp_path / "old.php").exists()
    assert (tmp_path / "old.php").read_text(encoding="utf-8") == "restore-me"


def test_rollback_count(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php")
    make_file(tmp_path, "b.php")
    backup_dir = tmp_path / "backup"
    ops = FileOps(project_dir=tmp_path, backup_dir=backup_dir)

    a = delete_action("a.php")
    b = delete_action("b.php")
    res_a = ops.delete(a)
    res_b = ops.delete(b)

    # add a non-ok entry
    log = [{"action": a, **res_a}, {"action": b, **res_b}, {"action": a, "status": "skipped", "backup_path": None}]
    count = ops.rollback(backup_dir, log)

    assert count == 2


def test_rollback_skips_non_ok_entries(tmp_path: Path) -> None:
    make_file(tmp_path, "a.php", content="x")
    backup_dir = tmp_path / "backup"
    ops = FileOps(project_dir=tmp_path, backup_dir=backup_dir)

    action = delete_action("a.php")
    res = ops.delete(action)
    assert res["status"] == "ok"

    count = ops.rollback(
        backup_dir,
        [
            {"action": action, "status": "skipped", "backup_path": res["backup_path"]},
            {"action": action, "status": "error", "backup_path": res["backup_path"]},
        ],
    )

    assert count == 0
    assert not (tmp_path / "a.php").exists()


def test_rollback_reverse_order(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    ops = FileOps(project_dir=project_dir, backup_dir=backup_dir)

    backup_a = make_file(backup_dir, "a.php", content="first")
    backup_b = make_file(backup_dir, "b.php", content="second")

    action = delete_action("target.php")
    log = [
        {"action": action, "status": "ok", "backup_path": str(backup_a)},
        {"action": action, "status": "ok", "backup_path": str(backup_b)},
    ]

    count = ops.rollback(backup_dir, log)

    assert count == 2
    assert (project_dir / "target.php").read_text(encoding="utf-8") == "first"


def test_delete_traversal_blocked(tmp_path: Path) -> None:
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")
    action = delete_action("../../etc/passwd")

    res = ops.delete(action)

    assert res["status"] == "error"
    assert "traversal" in res.get("reason", "").lower()


def test_move_src_traversal_blocked(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    ops = FileOps(project_dir=project_dir, backup_dir=tmp_path / "backup")
    action = move_action("../outside.php", "inside.php")

    res = ops.move(action)

    assert res["status"] == "error"
    assert "traversal" in res.get("reason", "").lower()


def test_move_dst_traversal_blocked(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    make_file(project_dir, "inside.php")
    ops = FileOps(project_dir=project_dir, backup_dir=tmp_path / "backup")
    action = move_action("inside.php", "../outside.php")

    res = ops.move(action)

    assert res["status"] == "error"
    assert "traversal" in res.get("reason", "").lower()


def test_safe_resolve_valid_path(tmp_path: Path) -> None:
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")
    p = ops._safe_resolve("subdir/file.php")

    assert p.is_relative_to(tmp_path.resolve())


def test_safe_resolve_raises_on_escape(tmp_path: Path) -> None:
    ops = FileOps(project_dir=tmp_path, backup_dir=tmp_path / "backup")

    with pytest.raises(ValueError):
        ops._safe_resolve("../../etc/passwd")

