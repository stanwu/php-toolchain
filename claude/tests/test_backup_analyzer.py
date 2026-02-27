import pytest
from core.models import FileRecord, AnalysisResult, ActionType, RiskLevel
from analyzers.backup_analyzer import BackupAnalyzer

PATHS = [
    "index.php",                                      # no match
    "saas/service.php",                               # no match
    "backup_old.php",                                 # matches _old → LOW
    "services/api/fetch_orders-20230816.php",       # matches date → MEDIUM
    "utils_backup2.php",                              # matches _backup → LOW
    "config.bak",                                     # matches .bak → LOW
    "upload.php~",                                    # matches ~ → LOW
    "x-----services1.php",                            # matches x--- → MEDIUM
    "report_copy.php",                                # matches _copy → MEDIUM
    "vendor/lib/autoload.php",                        # no match
]

RECORDS: dict[str, FileRecord] = {p: FileRecord(p, 0, 0) for p in PATHS}


@pytest.fixture
def result() -> AnalysisResult:
    return BackupAnalyzer(RECORDS).analyze()


@pytest.fixture
def action_map(result: AnalysisResult) -> dict[str, object]:
    return {a.source: a for a in result.actions}


# --- basic shape ---

def test_returns_analysis_result(result: AnalysisResult) -> None:
    assert isinstance(result, AnalysisResult)


def test_analyzer_name(result: AnalysisResult) -> None:
    assert result.analyzer_name == "backup_analyzer"


# --- no-match paths ---

def test_no_match_for_clean_files(action_map: dict) -> None:
    assert "index.php" not in action_map
    assert "saas/service.php" not in action_map


# --- individual pattern checks ---

def test_old_suffix_low_risk(action_map: dict) -> None:
    action = action_map["backup_old.php"]
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW


def test_date_stamp_medium_risk(action_map: dict) -> None:
    action = action_map["services/api/fetch_orders-20230816.php"]
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM


def test_bak_extension_low_risk(action_map: dict) -> None:
    action = action_map["config.bak"]
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW


def test_tilde_low_risk(action_map: dict) -> None:
    action = action_map["upload.php~"]
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW


def test_x_prefix_medium_risk(action_map: dict) -> None:
    action = action_map["x-----services1.php"]
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM


def test_copy_medium_risk(action_map: dict) -> None:
    action = action_map["report_copy.php"]
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM


def test_vendor_not_matched(action_map: dict) -> None:
    assert "vendor/lib/autoload.php" not in action_map


# --- integrity checks ---

def test_no_double_count(result: AnalysisResult) -> None:
    sources = [a.source for a in result.actions]
    assert len(sources) == len(set(sources)), "Each path must appear at most once"


def test_metadata_by_pattern(result: AnalysisResult) -> None:
    by_pattern = result.metadata["by_pattern"]
    # _old group must contain backup_old.php
    assert "backup_old.php" in by_pattern["old suffix"]
    # date-stamped group must contain the date-stamped file
    assert "services/api/fetch_orders-20230816.php" in by_pattern["date-stamped file"]
    # Each path appears in exactly one group
    all_paths: list[str] = []
    for paths in by_pattern.values():
        all_paths.extend(paths)
    assert len(all_paths) == len(set(all_paths)), "A path must not appear in multiple groups"


def test_metadata_counts(result: AnalysisResult) -> None:
    low = result.metadata["low_risk_count"]
    medium = result.metadata["medium_risk_count"]
    assert low + medium == len(result.actions)
    assert low > 0
    assert medium > 0
