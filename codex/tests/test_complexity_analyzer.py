from __future__ import annotations

from analyzers.complexity_analyzer import ComplexityAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel


def _fixture_records() -> dict[str, FileRecord]:
    return {
        "critical.php": FileRecord("critical.php", 16, 200),
        "high.php": FileRecord("high.php", 11, 60),
        "moderate.php": FileRecord("moderate.php", 6, 25),
        "low.php": FileRecord("low.php", 1, 2),
        "zero.php": FileRecord("zero.php", 0, 0),
    }


def _fixture_summary() -> dict:
    return {
        "total_files": 5,
        "total_branches": 287,
        "most_complex": [{"file": "critical.php", "max_depth": 16, "total_branches": 200}],
    }


def test_returns_analysis_result() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    assert isinstance(result, AnalysisResult)


def test_analyzer_name() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    assert result.analyzer_name == "complexity_analyzer"


def test_critical_is_high_risk() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    action = next(a for a in result.actions if a.source == "critical.php")
    assert action.risk_level == RiskLevel.HIGH


def test_high_is_medium_risk() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    action = next(a for a in result.actions if a.source == "high.php")
    assert action.risk_level == RiskLevel.MEDIUM


def test_moderate_is_low_risk() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    action = next(a for a in result.actions if a.source == "moderate.php")
    assert action.risk_level == RiskLevel.LOW


def test_below_threshold_no_action() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    sources = {a.source for a in result.actions}
    assert "low.php" not in sources
    assert "zero.php" not in sources


def test_all_actions_are_report_only() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    assert all(a.action_type == ActionType.REPORT_ONLY for a in result.actions)


def test_sorted_worst_first() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    sources = [a.source for a in result.actions]
    assert sources.index("critical.php") < sources.index("high.php")


def test_metadata_counts() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    assert result.metadata["critical_count"] == 1
    assert result.metadata["high_count"] == 1
    assert result.metadata["moderate_count"] == 1


def test_top10_in_metadata() -> None:
    result = ComplexityAnalyzer(_fixture_records(), _fixture_summary()).analyze()
    top10_files = {entry["file"] for entry in result.metadata["top10"]}
    assert "critical.php" in top10_files


def test_no_complex_files() -> None:
    records = {
        "a.php": FileRecord("a.php", 0, 0),
        "b.php": FileRecord("b.php", 0, 0),
    }
    summary = {"total_files": 2, "total_branches": 0, "most_complex": []}
    result = ComplexityAnalyzer(records, summary).analyze()
    assert result.actions == []

