import pytest
import json
from pathlib import Path
from unittest.mock import patch
import sys

# Add project root to Python path to allow imports from core
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loader import ReportLoader
from core.models import FileRecord

@pytest.fixture
def fixture_path() -> Path:
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def mini_report_path(fixture_path: Path) -> Path:
    return fixture_path / "mini_report.json"

@pytest.fixture
def loader(mini_report_path: Path) -> ReportLoader:
    return ReportLoader(mini_report_path)

def test_load_summary_total_files(loader: ReportLoader):
    summary = loader.load_summary()
    assert summary["total_files"] == 6

def test_load_summary_most_complex(loader: ReportLoader):
    summary = loader.load_summary()
    assert len(summary["most_complex"]) == 1
    assert summary["most_complex"][0]["file"] == "saas/service.php"

def test_iter_files_count(loader: ReportLoader):
    files = list(loader.iter_files())
    assert len(files) == 6

def test_iter_files_keys_are_strings(loader: ReportLoader):
    for path, record in loader.iter_files():
        assert isinstance(path, str)
        assert isinstance(record, FileRecord)

def test_iter_files_fields(loader: ReportLoader):
    files = dict(loader.iter_files())
    record = files.get("vendor/autoload.php")
    assert record is not None
    assert record.max_depth == 0
    assert record.total_branches == 0

def test_iter_files_complex_file(loader: ReportLoader):
    files = dict(loader.iter_files())
    record = files.get("saas/service.php")
    assert record is not None
    assert record.max_depth == 5
    assert record.total_branches == 10

def test_load_all_returns_dict(loader: ReportLoader):
    all_files = loader.load_all()
    assert isinstance(all_files, dict)
    assert len(all_files) == 6

def test_load_all_contains_vendor(loader: ReportLoader):
    all_files = loader.load_all()
    assert "vendor/autoload.php" in all_files

def test_get_file_found(loader: ReportLoader):
    record = loader.get_file("index.php")
    assert isinstance(record, FileRecord)
    assert record.path == "index.php"

def test_get_file_not_found(loader: ReportLoader):
    record = loader.get_file("nonexistent.php")
    assert record is None

def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ReportLoader(Path("nonexistent.json"))

def test_iter_does_not_load_all(loader: ReportLoader):
    with patch.object(ReportLoader, 'load_all', wraps=loader.load_all) as spy_load_all:
        file_iterator = loader.iter_files()
        first_item = next(file_iterator)
        assert first_item is not None
        spy_load_all.assert_not_called()

def create_malicious_json(tmp_path: Path, key: str) -> Path:
    malicious_file = tmp_path / "malicious.json"
    data = {
        "summary": {},
        "files": {
            key: {"max_depth": 0, "total_branches": 0}
        }
    }
    with open(malicious_file, 'w') as f:
        json.dump(data, f)
    return malicious_file

def test_traversal_path_rejected(tmp_path: Path):
    malicious_path = create_malicious_json(tmp_path, "../../etc/passwd")
    loader = ReportLoader(malicious_path)
    with pytest.raises(ValueError, match="Path traversal attempt detected"):
        list(loader.iter_files())

def test_dotdot_in_subpath_rejected(tmp_path: Path):
    malicious_path = create_malicious_json(tmp_path, "a/b/../../c.php")
    loader = ReportLoader(malicious_path)
    with pytest.raises(ValueError, match="Path traversal attempt detected"):
        list(loader.iter_files())

def test_missing_fields_defaults_and_logs(tmp_path: Path, caplog):
    data = {
        "summary": {},
        "files": {
            "file1.php": {"total_branches": 1},
            "file2.php": {"max_depth": 2},
            "file3.php": {"max_depth": "invalid", "total_branches": -5}
        }
    }
    test_file = tmp_path / "test.json"
    with open(test_file, 'w') as f:
        json.dump(data, f)
    
    loader = ReportLoader(test_file)
    with caplog.at_level('WARNING'):
        files = dict(loader.iter_files())

    assert len(files) == 3
    assert files["file1.php"].max_depth == 0
    assert files["file1.php"].total_branches == 1
    assert files["file2.php"].max_depth == 2
    assert files["file2.php"].total_branches == 0
    assert files["file3.php"].max_depth == 0
    assert files["file3.php"].total_branches == 0

    assert "Invalid or missing 'max_depth' for file1.php" in caplog.text
    assert "Invalid or missing 'total_branches' for file2.php" in caplog.text
    assert "Invalid or missing 'max_depth' for file3.php" in caplog.text
    assert "Invalid or missing 'total_branches' for file3.php" in caplog.text

def test_malformed_json_raises_value_error(tmp_path: Path):
    bad_json_path = tmp_path / "bad.json"
    bad_json_path.write_text('{"files": {"a.php": { "max_depth": 1, } } }') # trailing comma
    loader = ReportLoader(bad_json_path)
    with pytest.raises(ValueError, match="Malformed JSON"):
        list(loader.iter_files())
