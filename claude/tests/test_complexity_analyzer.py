import pytest
from core.models import FileRecord, AnalysisResult, ActionType, RiskLevel
from analyzers.complexity_analyzer import ComplexityAnalyzer

RECORDS: dict[str, FileRecord] = {
    "critical.php": FileRecord("critical.php", 16, 200),
    "high.php":     FileRecord("high.php",     11,  60),
    "moderate.php": FileRecord("moderate.php",  6,  25),
    "low.php":      FileRecord("low.php",       1,   2),
    "zero.php":     FileRecord("zero.php",      0,   0),
}

SUMMARY = {
    "total_files": 5,
    "total_branches": 287,
    "most_complex": [
        {"file": "critical.php", "max_depth": 16, "total_branches": 200}
    ],
}


@pytest.fixture
def result() -> AnalysisResult:
    return ComplexityAnalyzer(RECORDS, SUMMARY).analyze()


def test_returns_analysis_result(result: AnalysisResult) -> None:
    assert isinstance(result, AnalysisResult)


def test_analyzer_name(result: AnalysisResult) -> None:
    assert result.analyzer_name == "complexity_analyzer"


def test_critical_is_high_risk(result: AnalysisResult) -> None:
    action = next(a for a in result.actions if a.source == "critical.php")
    assert action.risk_level == RiskLevel.HIGH


def test_high_is_medium_risk(result: AnalysisResult) -> None:
    action = next(a for a in result.actions if a.source == "high.php")
    assert action.risk_level == RiskLevel.MEDIUM


def test_moderate_is_low_risk(result: AnalysisResult) -> None:
    action = next(a for a in result.actions if a.source == "moderate.php")
    assert action.risk_level == RiskLevel.LOW


def test_below_threshold_no_action(result: AnalysisResult) -> None:
    sources = {a.source for a in result.actions}
    assert "low.php" not in sources
    assert "zero.php" not in sources


def test_all_actions_are_report_only(result: AnalysisResult) -> None:
    assert all(a.action_type == ActionType.REPORT_ONLY for a in result.actions)


def test_sorted_worst_first(result: AnalysisResult) -> None:
    sources = [a.source for a in result.actions]
    assert sources.index("critical.php") < sources.index("high.php")


def test_metadata_counts(result: AnalysisResult) -> None:
    assert result.metadata["critical_count"] == 1
    assert result.metadata["high_count"] == 1
    assert result.metadata["moderate_count"] == 1


def test_top10_in_metadata(result: AnalysisResult) -> None:
    files_in_top10 = [entry["file"] for entry in result.metadata["top10"]]
    assert "critical.php" in files_in_top10


def test_no_complex_files() -> None:
    flat_records = {
        "a.php": FileRecord("a.php", 0, 0),
        "b.php": FileRecord("b.php", 1, 1),
    }
    flat_summary: dict = {"total_files": 2, "total_branches": 1, "most_complex": []}
    result = ComplexityAnalyzer(flat_records, flat_summary).analyze()
    assert len(result.actions) == 0
