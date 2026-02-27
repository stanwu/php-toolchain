import pytest
from pathlib import Path
from core.scanner import DirectoryScanner
from core.models import FileRecord
from core.loader import ReportLoader

# Expected files from the mini_report.json fixture
MINI_REPORT_FILES = {
    "index.php",
    "vendor/autoload.php",
    "vendor/lib/helper.php",
    "saas/service.php",
    "backup_old.php",
    "utils_copy.php",
}


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Creates a temporary project directory structure for testing."""
    # Create standard files from the report
    for rel_path in MINI_REPORT_FILES:
        file_path = tmp_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"content of {rel_path}")

    # Create a hidden directory and file to be ignored
    hidden_dir = tmp_path / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "config").write_text("git config")

    # Create a symlink to be ignored
    symlink_target = tmp_path / "index.php"
    symlink_path = tmp_path / "link_to_index.php"
    symlink_path.symlink_to(symlink_target)

    return tmp_path


@pytest.fixture
def json_records() -> dict[str, FileRecord]:
    """Loads file records from the mini_report.json fixture."""
    fixture_path = Path("/Users/stan/PHP_toolchain/gemini/tests/fixtures/mini_report.json")
    loader = ReportLoader(fixture_path)
    records = {}
    for path, record in loader.iter_files():
        record.exists_on_disk = False  # Ensure default state for tests
        records[path] = record
    return records


def test_scan_finds_all_files(project_root: Path):
    scanner = DirectoryScanner(project_root)
    found_files = scanner.scan()
    assert found_files == MINI_REPORT_FILES
    assert len(found_files) == 6


def test_scan_no_leading_slash(project_root: Path):
    scanner = DirectoryScanner(project_root)
    found_files = scanner.scan()
    assert all(not path.startswith("/") and not path.startswith("./") for path in found_files)


def test_scan_forward_slash(project_root: Path):
    scanner = DirectoryScanner(project_root)
    found_files = scanner.scan()
    assert all("\\" not in path for path in found_files)


def test_scan_skips_hidden_dirs(project_root: Path):
    scanner = DirectoryScanner(project_root)
    found_files = scanner.scan()
    assert ".git/config" not in found_files


def test_scan_skips_symlinks(project_root: Path):
    scanner = DirectoryScanner(project_root)
    found_files = scanner.scan()
    assert "link_to_index.php" not in found_files


def test_cross_validate_matched(project_root: Path, json_records: dict[str, FileRecord]):
    scanner = DirectoryScanner(project_root)
    result = scanner.cross_validate(json_records)

    assert len(result.matched) == 6
    assert len(result.ghost) == 0
    assert len(result.new_files) == 0
    assert set(result.matched.keys()) == MINI_REPORT_FILES


def test_cross_validate_ghost(project_root: Path, json_records: dict[str, FileRecord]):
    # Remove a file from disk to make it a "ghost"
    (project_root / "backup_old.php").unlink()

    scanner = DirectoryScanner(project_root)
    result = scanner.cross_validate(json_records)

    assert len(result.matched) == 5
    assert result.ghost == ["backup_old.php"]
    assert len(result.new_files) == 0


def test_cross_validate_new(project_root: Path, json_records: dict[str, FileRecord]):
    # Add a new file to disk
    (project_root / "extra.php").touch()

    scanner = DirectoryScanner(project_root)
    result = scanner.cross_validate(json_records)

    assert len(result.matched) == 6
    assert len(result.ghost) == 0
    assert result.new_files == ["extra.php"]


def test_cross_validate_exists_on_disk(project_root: Path, json_records: dict[str, FileRecord]):
    # Initial state from fixture is False
    assert json_records["index.php"].exists_on_disk is False

    scanner = DirectoryScanner(project_root)
    # Run validation, record should be marked as True
    result = scanner.cross_validate(json_records)
    assert result.matched["index.php"].exists_on_disk is True
    assert json_records["index.php"].exists_on_disk is True # Original dict is mutated

    # Now, test the ghost file scenario.
    # Reset the state of one record for a clean test.
    json_records["backup_old.php"].exists_on_disk = False
    assert json_records["backup_old.php"].exists_on_disk is False # Confirm reset

    # Delete the file to make it a ghost
    (project_root / "backup_old.php").unlink()

    # Run validation again
    result_with_ghost = scanner.cross_validate(json_records)

    # The record for the ghost file should not be in 'matched'
    assert "backup_old.php" not in result_with_ghost.matched
    assert "backup_old.php" in result_with_ghost.ghost

    # Its state in the original dictionary should remain False,
    # because it was not matched in this run.
    assert json_records["backup_old.php"].exists_on_disk is False


def test_cross_validate_empty_dir(tmp_path: Path, json_records: dict[str, FileRecord]):
    # Use a new, empty directory for the scan
    empty_dir = tmp_path / "empty_project"
    empty_dir.mkdir()

    scanner = DirectoryScanner(empty_dir)
    result = scanner.cross_validate(json_records)

    assert len(result.matched) == 0
    assert len(result.new_files) == 0
    assert len(result.ghost) == 6
    assert set(result.ghost) == MINI_REPORT_FILES


def test_cross_validate_empty_json(project_root: Path):
    scanner = DirectoryScanner(project_root)
    # Cross-validate against an empty set of JSON records
    result = scanner.cross_validate({})

    assert len(result.matched) == 0
    assert len(result.ghost) == 0
    assert len(result.new_files) == 6
    assert set(result.new_files) == MINI_REPORT_FILES
