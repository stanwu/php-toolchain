"""Tests for core/scanner.py."""
import pytest
from pathlib import Path

from core.models import FileRecord
from core.scanner import DirectoryScanner, ScanResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINI_REPORT_PATHS = [
    "index.php",
    "vendor/autoload.php",
    "vendor/lib/helper.php",
    "saas/service.php",
    "backup_old.php",
    "utils_copy.php",
]


def make_file_records() -> dict[str, FileRecord]:
    return {
        p: FileRecord(path=p, max_depth=1, total_branches=1)
        for p in MINI_REPORT_PATHS
    }


def build_project_tree(base: Path) -> None:
    """Create the standard mini project tree under base."""
    for rel in MINI_REPORT_PATHS:
        full = base / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("<?php // placeholder")

    # Hidden directory that must be skipped
    git_dir = base / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "config").write_text("[core]")


# ---------------------------------------------------------------------------
# scan() tests
# ---------------------------------------------------------------------------

def test_scan_finds_all_files(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    found = scanner.scan()
    assert len(found) == 6


def test_scan_no_leading_slash(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    for path in scanner.scan():
        assert not path.startswith("/"), f"Path has leading /: {path!r}"
        assert not path.startswith("./"), f"Path has leading ./: {path!r}"


def test_scan_forward_slash(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    for path in scanner.scan():
        assert "\\" not in path, f"Path contains backslash: {path!r}"


def test_scan_skips_hidden_dirs(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    found = scanner.scan()
    assert ".git/config" not in found
    assert not any(p.startswith(".git") for p in found)


def test_scan_skips_symlinks(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    # Create a symlink to one of the real files
    target = tmp_path / "index.php"
    link = tmp_path / "index_link.php"
    link.symlink_to(target)

    scanner = DirectoryScanner(tmp_path)
    found = scanner.scan()
    # Symlink should not appear in results
    assert "index_link.php" not in found
    # Original is still found
    assert "index.php" in found


# ---------------------------------------------------------------------------
# cross_validate() tests
# ---------------------------------------------------------------------------

def test_cross_validate_matched(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(make_file_records())

    assert len(result.matched) == 6
    assert result.ghost == []
    assert result.new_files == []


def test_cross_validate_ghost(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    # Remove backup_old.php from disk
    (tmp_path / "backup_old.php").unlink()

    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(make_file_records())

    assert "backup_old.php" in result.ghost
    assert len(result.matched) == 5


def test_cross_validate_new(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    # Add an extra file not in JSON
    (tmp_path / "extra.php").write_text("<?php")

    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(make_file_records())

    assert "extra.php" in result.new_files
    assert len(result.matched) == 6


def test_cross_validate_exists_on_disk(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    records = make_file_records()
    # Set exists_on_disk=False initially to confirm scanner flips it
    for rec in records.values():
        rec.exists_on_disk = False

    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(records)

    for rec in result.matched.values():
        assert rec.exists_on_disk is True


def test_cross_validate_empty_dir(tmp_path: Path) -> None:
    # Empty directory: all JSON records become ghosts
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(make_file_records())

    assert len(result.ghost) == 6
    assert result.matched == {}
    assert result.new_files == []


def test_cross_validate_empty_json(tmp_path: Path) -> None:
    build_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate({})

    assert result.matched == {}
    assert result.ghost == []
    assert len(result.new_files) == 6
