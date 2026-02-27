from pathlib import Path

import pytest

from analyzers.vendor_analyzer import VendorAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

RECORDS: dict[str, FileRecord] = {
    "index.php": FileRecord("index.php", 1, 2),
    "vendor/autoload.php": FileRecord("vendor/autoload.php", 0, 0),
    "vendor/lib/a.php": FileRecord("vendor/lib/a.php", 1, 2),
    "vendor/lib/b.php": FileRecord("vendor/lib/b.php", 0, 0),
    "node_modules/react/index.js": FileRecord("node_modules/react/index.js", 0, 0),
    "app/service.php": FileRecord("app/service.php", 2, 5),
}

PROJECT_DIR = Path("/fake/project")


@pytest.fixture
def result() -> AnalysisResult:
    return VendorAnalyzer(RECORDS, PROJECT_DIR).analyze()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_returns_analysis_result(result: AnalysisResult) -> None:
    assert isinstance(result, AnalysisResult)


def test_analyzer_name(result: AnalysisResult) -> None:
    assert result.analyzer_name == "vendor_analyzer"


def test_detects_vendor_root(result: AnalysisResult) -> None:
    assert "vendor/" in result.metadata["vendor_roots"]


def test_detects_node_modules(result: AnalysisResult) -> None:
    assert "node_modules/" in result.metadata["vendor_roots"]


def test_vendor_file_count(result: AnalysisResult) -> None:
    assert result.metadata["vendor_roots"]["vendor/"]["file_count"] == 3


def test_non_vendor_not_detected(result: AnalysisResult) -> None:
    assert "app" not in result.metadata["vendor_roots"]
    assert "app/" not in result.metadata["vendor_roots"]


def test_one_action_per_vendor_root(result: AnalysisResult) -> None:
    assert len(result.actions) == 2


def test_action_type_is_gitignore(result: AnalysisResult) -> None:
    for action in result.actions:
        assert action.action_type == ActionType.ADD_GITIGNORE


def test_action_risk_is_low(result: AnalysisResult) -> None:
    for action in result.actions:
        assert action.risk_level == RiskLevel.LOW


def test_action_reason_contains_count(result: AnalysisResult) -> None:
    vendor_action = next(a for a in result.actions if a.source == "vendor")
    assert "3" in vendor_action.reason


def test_no_vendor_no_actions() -> None:
    records = {
        "index.php": FileRecord("index.php", 1, 2),
        "app/service.php": FileRecord("app/service.php", 2, 5),
    }
    result = VendorAnalyzer(records, PROJECT_DIR).analyze()
    assert result.actions == []


def test_nested_vendor() -> None:
    records = {
        "test/vendor/x.php": FileRecord("test/vendor/x.php", 0, 0),
        "index.php": FileRecord("index.php", 1, 2),
    }
    result = VendorAnalyzer(records, PROJECT_DIR).analyze()
    roots = result.metadata["vendor_roots"]
    assert "test/vendor/" in roots
    assert roots["test/vendor/"]["file_count"] == 1
