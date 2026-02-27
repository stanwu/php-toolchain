from __future__ import annotations

from pathlib import Path

from analyzers.vendor_analyzer import VendorAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel


def _fixture_records() -> dict[str, FileRecord]:
    return {
        "index.php": FileRecord("index.php", 1, 2),
        "vendor/autoload.php": FileRecord("vendor/autoload.php", 0, 0),
        "vendor/lib/a.php": FileRecord("vendor/lib/a.php", 1, 2),
        "vendor/lib/b.php": FileRecord("vendor/lib/b.php", 0, 0),
        "node_modules/react/index.js": FileRecord("node_modules/react/index.js", 0, 0),
        "app/service.php": FileRecord("app/service.php", 2, 5),
    }


def test_returns_analysis_result(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert isinstance(result, AnalysisResult)


def test_analyzer_name(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert result.analyzer_name == "vendor_analyzer"


def test_detects_vendor_root(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert "vendor" in result.metadata["vendor_roots"]


def test_detects_node_modules(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert "node_modules" in result.metadata["vendor_roots"]


def test_vendor_file_count(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert result.metadata["vendor_roots"]["vendor"]["file_count"] == 3


def test_non_vendor_not_detected(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert "app" not in result.metadata["vendor_roots"]


def test_one_action_per_vendor_root(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert len(result.actions) == 2


def test_action_type_is_gitignore(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert all(a.action_type == ActionType.ADD_GITIGNORE for a in result.actions)


def test_action_risk_is_low(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    assert all(a.risk_level == RiskLevel.LOW for a in result.actions)


def test_action_reason_contains_count(tmp_path: Path) -> None:
    result = VendorAnalyzer(_fixture_records(), tmp_path).analyze()
    vendor_action = next(a for a in result.actions if a.source == "vendor")
    assert "3" in vendor_action.reason


def test_no_vendor_no_actions(tmp_path: Path) -> None:
    records = {"index.php": FileRecord("index.php", 1, 2), "app/service.php": FileRecord("app/service.php", 2, 5)}
    result = VendorAnalyzer(records, tmp_path).analyze()
    assert result.actions == []
    assert result.metadata["vendor_roots"] == {}


def test_nested_vendor(tmp_path: Path) -> None:
    records = {
        "test/vendor/x.php": FileRecord("test/vendor/x.php", 0, 0),
        "test/app/y.php": FileRecord("test/app/y.php", 0, 0),
    }
    result = VendorAnalyzer(records, tmp_path).analyze()
    assert "test/vendor" in result.metadata["vendor_roots"]
