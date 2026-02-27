import json
import pytest
from pathlib import Path

from core.loader import ReportLoader
from core.models import FileRecord

FIXTURES = Path(__file__).parent / "fixtures"
MINI_REPORT = FIXTURES / "mini_report.json"


# ---------------------------------------------------------------------------
# Summary tests
# ---------------------------------------------------------------------------

def test_load_summary_total_files() -> None:
    loader = ReportLoader(MINI_REPORT)
    summary = loader.load_summary()
    assert summary["total_files"] == 6


def test_load_summary_most_complex() -> None:
    loader = ReportLoader(MINI_REPORT)
    summary = loader.load_summary()
    assert len(summary["most_complex"]) == 1


# ---------------------------------------------------------------------------
# iter_files tests
# ---------------------------------------------------------------------------

def test_iter_files_count() -> None:
    loader = ReportLoader(MINI_REPORT)
    pairs = list(loader.iter_files())
    assert len(pairs) == 6


def test_iter_files_keys_are_strings() -> None:
    loader = ReportLoader(MINI_REPORT)
    for key, _ in loader.iter_files():
        assert isinstance(key, str)


def test_iter_files_fields() -> None:
    loader = ReportLoader(MINI_REPORT)
    records = dict(loader.iter_files())
    rec = records["vendor/autoload.php"]
    assert rec.max_depth == 0
    assert rec.total_branches == 0


def test_iter_files_complex_file() -> None:
    loader = ReportLoader(MINI_REPORT)
    records = dict(loader.iter_files())
    rec = records["saas/service.php"]
    assert rec.max_depth == 5
    assert rec.total_branches == 10


# ---------------------------------------------------------------------------
# load_all tests
# ---------------------------------------------------------------------------

def test_load_all_returns_dict() -> None:
    loader = ReportLoader(MINI_REPORT)
    result = loader.load_all()
    assert isinstance(result, dict)
    assert len(result) == 6


def test_load_all_contains_vendor() -> None:
    loader = ReportLoader(MINI_REPORT)
    result = loader.load_all()
    assert "vendor/autoload.php" in result


# ---------------------------------------------------------------------------
# get_file tests
# ---------------------------------------------------------------------------

def test_get_file_found() -> None:
    loader = ReportLoader(MINI_REPORT)
    rec = loader.get_file("index.php")
    assert rec is not None
    assert isinstance(rec, FileRecord)


def test_get_file_not_found() -> None:
    loader = ReportLoader(MINI_REPORT)
    rec = loader.get_file("nonexistent.php")
    assert rec is None


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        ReportLoader(Path("no.json")).load_summary()


def test_iter_does_not_load_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling iter_files() and pulling one item must not trigger load_all()."""
    loader = ReportLoader(MINI_REPORT)
    called = []

    original_load_all = loader.load_all

    def spy_load_all() -> dict:
        called.append(True)
        return original_load_all()

    monkeypatch.setattr(loader, "load_all", spy_load_all)

    gen = loader.iter_files()
    next(gen)  # pull exactly one record

    assert called == [], "load_all() must not be called during iter_files()"


# ---------------------------------------------------------------------------
# Security / path traversal tests
# ---------------------------------------------------------------------------

def test_traversal_path_rejected(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text(
        json.dumps(
            {
                "summary": {"total_files": 1, "total_branches": 0, "most_complex": []},
                "files": {
                    "../../etc/passwd": {"max_depth": 0, "total_branches": 0, "branches": [], "functions": []}
                },
            }
        )
    )
    loader = ReportLoader(bad_json)
    with pytest.raises(ValueError, match="traversal"):
        list(loader.iter_files())


def test_dotdot_in_subpath_rejected(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad2.json"
    bad_json.write_text(
        json.dumps(
            {
                "summary": {"total_files": 1, "total_branches": 0, "most_complex": []},
                "files": {
                    "a/../b/file.php": {"max_depth": 0, "total_branches": 0, "branches": [], "functions": []}
                },
            }
        )
    )
    loader = ReportLoader(bad_json)
    with pytest.raises(ValueError, match="traversal"):
        list(loader.iter_files())
