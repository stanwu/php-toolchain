from __future__ import annotations

from pathlib import Path

import pytest

from core.loader import ReportLoader
from core.scanner import DirectoryScanner


def _fixture_report_path() -> Path:
    return Path(__file__).parent / "fixtures" / "mini_report.json"


def _create_project_tree(root: Path) -> None:
    (root / "vendor" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "saas").mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir(parents=True, exist_ok=True)

    (root / "index.php").write_text("<?php echo 'hi';", encoding="utf-8")
    (root / "vendor" / "autoload.php").write_text("<?php", encoding="utf-8")
    (root / "vendor" / "lib" / "helper.php").write_text("<?php", encoding="utf-8")
    (root / "saas" / "service.php").write_text("<?php", encoding="utf-8")
    (root / "backup_old.php").write_text("<?php", encoding="utf-8")
    (root / "utils_copy.php").write_text("<?php", encoding="utf-8")

    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")


def test_scan_finds_all_files(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    paths = scanner.scan()
    assert len(paths) == 6


def test_scan_no_leading_slash(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    paths = scanner.scan()
    assert all(not p.startswith("/") and not p.startswith("./") for p in paths)


def test_scan_forward_slash(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    paths = scanner.scan()
    assert all("\\" not in p for p in paths)


def test_scan_skips_hidden_dirs(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    paths = scanner.scan()
    assert ".git/config" not in paths


def test_scan_skips_symlinks(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    target = tmp_path / "index.php"
    link = tmp_path / "link.php"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported in this environment")

    scanner = DirectoryScanner(tmp_path)
    paths = scanner.scan()
    assert "link.php" not in paths


def test_cross_validate_matched(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    records = ReportLoader(_fixture_report_path()).load_all()
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(records)
    assert len(result.matched) == 6
    assert result.ghost == []
    assert result.new_files == []


def test_cross_validate_ghost(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    (tmp_path / "backup_old.php").unlink()
    records = ReportLoader(_fixture_report_path()).load_all()
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(records)
    assert "backup_old.php" in result.ghost
    assert len(result.matched) == 5


def test_cross_validate_new(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    (tmp_path / "extra.php").write_text("<?php", encoding="utf-8")
    records = ReportLoader(_fixture_report_path()).load_all()
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(records)
    assert "extra.php" in result.new_files


def test_cross_validate_exists_on_disk(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    records = ReportLoader(_fixture_report_path()).load_all()
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(records)
    assert result.matched["index.php"].exists_on_disk is True


def test_cross_validate_empty_dir(tmp_path: Path) -> None:
    records = ReportLoader(_fixture_report_path()).load_all()
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate(records)
    assert result.matched == {}
    assert len(result.ghost) == 6
    assert result.new_files == []


def test_cross_validate_empty_json(tmp_path: Path) -> None:
    _create_project_tree(tmp_path)
    scanner = DirectoryScanner(tmp_path)
    result = scanner.cross_validate({})
    assert result.matched == {}
    assert result.ghost == []
    assert len(result.new_files) == 6

