from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.loader import ReportLoader
from core.models import FileRecord


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "mini_report.json"


def test_load_summary_total_files() -> None:
    loader = ReportLoader(_fixture_path())
    summary = loader.load_summary()
    assert summary["total_files"] == 6


def test_load_summary_most_complex() -> None:
    loader = ReportLoader(_fixture_path())
    summary = loader.load_summary()
    assert isinstance(summary["most_complex"], list)
    assert len(summary["most_complex"]) == 1


def test_iter_files_count() -> None:
    loader = ReportLoader(_fixture_path())
    assert sum(1 for _ in loader.iter_files()) == 6


def test_iter_files_keys_are_strings() -> None:
    loader = ReportLoader(_fixture_path())
    for key, _record in loader.iter_files():
        assert isinstance(key, str)


def test_iter_files_fields() -> None:
    loader = ReportLoader(_fixture_path())
    records = dict(loader.iter_files())
    rec = records["vendor/autoload.php"]
    assert rec.max_depth == 0
    assert rec.total_branches == 0


def test_iter_files_complex_file() -> None:
    loader = ReportLoader(_fixture_path())
    records = dict(loader.iter_files())
    rec = records["saas/service.php"]
    assert rec.max_depth == 5
    assert rec.total_branches == 10


def test_load_all_returns_dict() -> None:
    loader = ReportLoader(_fixture_path())
    records = loader.load_all()
    assert isinstance(records, dict)
    assert len(records) == 6


def test_load_all_contains_vendor() -> None:
    loader = ReportLoader(_fixture_path())
    records = loader.load_all()
    assert "vendor/autoload.php" in records


def test_get_file_found() -> None:
    loader = ReportLoader(_fixture_path())
    rec = loader.get_file("index.php")
    assert isinstance(rec, FileRecord)
    assert rec is not None


def test_get_file_not_found() -> None:
    loader = ReportLoader(_fixture_path())
    rec = loader.get_file("nonexistent.php")
    assert rec is None


def test_missing_file_raises() -> None:
    loader = ReportLoader(Path("no.json"))
    with pytest.raises(FileNotFoundError):
        loader.load_summary()


def test_iter_does_not_load_all(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"load_all": False}

    def _spy_load_all(self: ReportLoader) -> dict[str, FileRecord]:
        called["load_all"] = True
        return {}

    monkeypatch.setattr(ReportLoader, "load_all", _spy_load_all, raising=True)

    loader = ReportLoader(_fixture_path())
    it = loader.iter_files()
    _ = next(it)
    assert called["load_all"] is False


def test_traversal_path_rejected(tmp_path: Path) -> None:
    bad = {
        "summary": {"total_files": 1, "total_branches": 0, "most_complex": []},
        "files": {"../../etc/passwd": {"max_depth": 0, "total_branches": 0}},
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    loader = ReportLoader(p)
    with pytest.raises(ValueError):
        next(loader.iter_files())


def test_dotdot_in_subpath_rejected(tmp_path: Path) -> None:
    bad = {
        "summary": {"total_files": 1, "total_branches": 0, "most_complex": []},
        "files": {"a/../b/file.php": {"max_depth": 0, "total_branches": 0}},
    }
    p = tmp_path / "bad2.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    loader = ReportLoader(p)
    with pytest.raises(ValueError):
        next(loader.iter_files())

