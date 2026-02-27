from __future__ import annotations

from analyzers.backup_analyzer import BackupAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel


def _fixture_records() -> dict[str, FileRecord]:
    paths = [
        "index.php",  # no match
        "saas/service.php",  # no match
        "backup_old.php",  # matches _old → LOW
        "services/api/fetch_orders-20230816.php",  # matches date → MEDIUM
        "utils_backup2.php",  # matches _backup → LOW
        "config.bak",  # matches .bak → LOW
        "upload.php~",  # matches ~ → LOW
        "x-----services1.php",  # matches x--- → MEDIUM
        "report_copy.php",  # matches _copy → MEDIUM
        "vendor/lib/autoload.php",  # no match (vendor — not a backup pattern)
    ]
    return {p: FileRecord(p, 0, 0) for p in paths}


def _actions_by_source(result: AnalysisResult) -> dict[str, list]:
    actions: dict[str, list] = {}
    for action in result.actions:
        actions.setdefault(action.source, []).append(action)
    return actions


def test_returns_analysis_result() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    assert isinstance(result, AnalysisResult)


def test_analyzer_name() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    assert result.analyzer_name == "backup_analyzer"


def test_no_match_for_clean_files() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    sources = {a.source for a in result.actions}
    assert "index.php" not in sources
    assert "saas/service.php" not in sources


def test_old_suffix_low_risk() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    action = next(a for a in result.actions if a.source == "backup_old.php")
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW


def test_date_stamp_medium_risk() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    action = next(a for a in result.actions if a.source == "services/api/fetch_orders-20230816.php")
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM


def test_bak_extension_low_risk() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    action = next(a for a in result.actions if a.source == "config.bak")
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW


def test_tilde_low_risk() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    action = next(a for a in result.actions if a.source == "upload.php~")
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW


def test_x_prefix_medium_risk() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    action = next(a for a in result.actions if a.source == "x-----services1.php")
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM


def test_copy_medium_risk() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    action = next(a for a in result.actions if a.source == "report_copy.php")
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM


def test_vendor_not_matched() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    sources = {a.source for a in result.actions}
    assert "vendor/lib/autoload.php" not in sources


def test_no_double_count() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    by_source = _actions_by_source(result)
    assert all(len(actions) == 1 for actions in by_source.values())


def test_metadata_by_pattern() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    by_pattern = result.metadata["by_pattern"]

    assert "old suffix" in by_pattern
    assert "backup_old.php" in by_pattern["old suffix"]

    assert "date-stamped file" in by_pattern
    assert "services/api/fetch_orders-20230816.php" in by_pattern["date-stamped file"]

    assert ".bak extension" in by_pattern
    assert "config.bak" in by_pattern[".bak extension"]

    assert "tilde backup" in by_pattern
    assert "upload.php~" in by_pattern["tilde backup"]

    assert "x--- prefix (disabled file)" in by_pattern
    assert "x-----services1.php" in by_pattern["x--- prefix (disabled file)"]

    assert "copy suffix" in by_pattern
    assert "report_copy.php" in by_pattern["copy suffix"]


def test_metadata_counts() -> None:
    result = BackupAnalyzer(_fixture_records()).analyze()
    assert result.metadata["low_risk_count"] + result.metadata["medium_risk_count"] == len(result.actions)
