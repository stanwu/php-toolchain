"""
Tests for the ComplexityAnalyzer module.
"""
import pytest

from analyzers.complexity_analyzer import ComplexityAnalyzer
from core.models import (ActionType, AnalysisResult, FileRecord, RiskLevel)

# Test data mimicking records from the loader and summary from the report
RECORDS = {
    "critical.php": FileRecord(path="critical.php", max_depth=16, total_branches=200),
    "high.php": FileRecord(path="high.php", max_depth=11, total_branches=60),
    "moderate.php": FileRecord(path="moderate.php", max_depth=6, total_branches=25),
    "low.php": FileRecord(path="low.php", max_depth=1, total_branches=2),
    "zero.php": FileRecord(path="zero.php", max_depth=0, total_branches=0),
}

SUMMARY = {
    "total_files": 5,
    "total_branches": 287,
    "most_complex": [
        {"file": "critical.php", "max_depth": 16, "total_branches": 200},
        # This one is not in RECORDS to test the summary-fallback logic
        {"file": "vendor/complex.php", "max_depth": 20, "total_branches": 150},
    ]
}

@pytest.fixture
def analyzer() -> ComplexityAnalyzer:
    """Provides a ComplexityAnalyzer instance with standard test data."""
    return ComplexityAnalyzer(RECORDS, SUMMARY)

@pytest.fixture
def no_complex_analyzer() -> ComplexityAnalyzer:
    """Provides an analyzer with no complex files."""
    records = {
        "low.php": FileRecord(path="low.php", max_depth=1, total_branches=2),
        "zero.php": FileRecord(path="zero.php", max_depth=0, total_branches=0),
    }
    summary = {"most_complex": []}
    return ComplexityAnalyzer(records, summary)

def test_returns_analysis_result(analyzer: ComplexityAnalyzer):
    """Checks if the analyze method returns an AnalysisResult instance."""
    result = analyzer.analyze()
    assert isinstance(result, AnalysisResult)

def test_analyzer_name(analyzer: ComplexityAnalyzer):
    """Ensures the analyzer name is set correctly."""
    result = analyzer.analyze()
    assert result.analyzer_name == "complexity_analyzer"

def test_critical_is_high_risk(analyzer: ComplexityAnalyzer):
    """Verifies that a 'critical' complexity file generates a HIGH risk action."""
    result = analyzer.analyze()
    action = next((a for a in result.actions if a.source == "critical.php"), None)
    assert action is not None
    assert action.risk_level == RiskLevel.HIGH

def test_high_is_medium_risk(analyzer: ComplexityAnalyzer):
    """Verifies that a 'high' complexity file generates a MEDIUM risk action."""
    result = analyzer.analyze()
    action = next((a for a in result.actions if a.source == "high.php"), None)
    assert action is not None
    assert action.risk_level == RiskLevel.MEDIUM

def test_moderate_is_low_risk(analyzer: ComplexityAnalyzer):
    """Verifies that a 'moderate' complexity file generates a LOW risk action."""
    result = analyzer.analyze()
    action = next((a for a in result.actions if a.source == "moderate.php"), None)
    assert action is not None
    assert action.risk_level == RiskLevel.LOW

def test_below_threshold_no_action(analyzer: ComplexityAnalyzer):
    """Ensures files below the 'moderate' threshold do not generate actions."""
    result = analyzer.analyze()
    action_files = {a.source for a in result.actions}
    assert "low.php" not in action_files
    assert "zero.php" not in action_files

def test_all_actions_are_report_only(analyzer: ComplexityAnalyzer):
    """Checks that all generated actions are of type REPORT_ONLY."""
    result = analyzer.analyze()
    assert all(a.action_type == ActionType.REPORT_ONLY for a in result.actions)

def test_sorted_worst_first(analyzer: ComplexityAnalyzer):
    """
    Tests that actions are sorted by complexity score in descending order.
    'vendor/complex.php' should be first, then 'critical.php', etc.
    """
    result = analyzer.analyze()
    action_sources = [a.source for a in result.actions]
    expected_order = ["critical.php", "vendor/complex.php", "high.php", "moderate.php"]
    assert action_sources == expected_order

def test_metadata_counts(analyzer: ComplexityAnalyzer):
    """Checks if the metadata counts for each risk level are correct."""
    result = analyzer.analyze()
    assert result.metadata["critical_count"] == 2  # critical.php + vendor/complex.php
    assert result.metadata["high_count"] == 1
    assert result.metadata["moderate_count"] == 1
    assert result.metadata["total_analyzed"] == len(RECORDS)

def test_top10_in_metadata(analyzer: ComplexityAnalyzer):
    """
    Validates the 'top10' list in the metadata, ensuring it's sorted correctly
    and contains the right file information.
    """
    result = analyzer.analyze()
    top10 = result.metadata["top10"]
    
    # Check that it contains items and is sorted by score
    assert len(top10) > 0
    assert top10[0]["file"] == "critical.php"
    assert top10[0]["score"] == (16 * 3) + 200
    
    scores = [item["score"] for item in top10]
    assert scores == sorted(scores, reverse=True)

def test_no_complex_files(no_complex_analyzer: ComplexityAnalyzer):
    """
    Tests the analyzer's behavior when no files meet the complexity thresholds.
    It should produce no actions and have zero counts in metadata.
    """
    result = no_complex_analyzer.analyze()
    assert len(result.actions) == 0
    assert result.metadata["critical_count"] == 0
    assert result.metadata["high_count"] == 0
    assert result.metadata["moderate_count"] == 0
    assert len(result.metadata["top10"]) > 0 # Still shows scored files

def test_summary_fallback_logic(analyzer: ComplexityAnalyzer):
    """
    Ensures that a complex file listed in the summary but not present in the
    main records is still processed and included in the actions.
    """
    result = analyzer.analyze()
    action = next((a for a in result.actions if a.source == "vendor/complex.php"), None)
    assert action is not None
    assert action.risk_level == RiskLevel.HIGH
    assert "From summary" in action.reason
