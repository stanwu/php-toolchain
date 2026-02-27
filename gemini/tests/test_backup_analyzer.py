import pytest
from analyzers.backup_analyzer import BackupAnalyzer
from core.models import FileRecord, AnalysisResult, ActionType, RiskLevel

# Fixture paths from the prompt
paths = [
    "index.php",                           # no match
    "saas/service.php",                    # no match
    "backup_old.php",                      # matches _old → LOW
    "services/api/fetch_orders-20230816.php",  # matches date → MEDIUM
    "utils_backup2.php",                   # matches _backup → LOW
    "config.bak",                          # matches .bak → LOW
    "upload.php~",                         # matches ~ → LOW
    "x-----services1.php",                 # matches x--- → MEDIUM
    "report_copy.php",                     # matches _copy → MEDIUM
    "vendor/lib/autoload.php",             # no match (vendor — not a backup pattern)
]
records = {p: FileRecord(p, 0, 0) for p in paths}

@pytest.fixture
def analysis_result() -> AnalysisResult:
    analyzer = BackupAnalyzer(records)
    return analyzer.analyze()

def test_returns_analysis_result(analysis_result: AnalysisResult):
    assert isinstance(analysis_result, AnalysisResult)

def test_analyzer_name(analysis_result: AnalysisResult):
    assert analysis_result.analyzer_name == "backup_analyzer"

def test_no_match_for_clean_files(analysis_result: AnalysisResult):
    matched_files = {action.source for action in analysis_result.actions}
    assert "index.php" not in matched_files
    assert "saas/service.php" not in matched_files

def find_action_for_path(result: AnalysisResult, path: str):
    for action in result.actions:
        if action.source == path:
            return action
    return None

def test_old_suffix_low_risk(analysis_result: AnalysisResult):
    action = find_action_for_path(analysis_result, "backup_old.php")
    assert action is not None
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW
    assert "old suffix" in action.reason

def test_date_stamp_medium_risk(analysis_result: AnalysisResult):
    path = "services/api/fetch_orders-20230816.php"
    action = find_action_for_path(analysis_result, path)
    assert action is not None
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM
    assert "date-stamped file" in action.reason

def test_bak_extension_low_risk(analysis_result: AnalysisResult):
    action = find_action_for_path(analysis_result, "config.bak")
    assert action is not None
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW
    assert ".bak extension" in action.reason

def test_tilde_low_risk(analysis_result: AnalysisResult):
    action = find_action_for_path(analysis_result, "upload.php~")
    assert action is not None
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.LOW
    assert "tilde backup" in action.reason

def test_x_prefix_medium_risk(analysis_result: AnalysisResult):
    action = find_action_for_path(analysis_result, "x-----services1.php")
    assert action is not None
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM
    assert "x--- prefix" in action.reason

def test_copy_medium_risk(analysis_result: AnalysisResult):
    action = find_action_for_path(analysis_result, "report_copy.php")
    assert action is not None
    assert action.action_type == ActionType.DELETE
    assert action.risk_level == RiskLevel.MEDIUM
    assert "copy suffix" in action.reason

def test_vendor_not_matched(analysis_result: AnalysisResult):
    action = find_action_for_path(analysis_result, "vendor/lib/autoload.php")
    assert action is None

def test_no_double_count(analysis_result: AnalysisResult):
    sources = [action.source for action in analysis_result.actions]
    assert len(sources) == len(set(sources))
    # Total matches should be 7 based on the list
    assert len(sources) == 7

def test_metadata_by_pattern(analysis_result: AnalysisResult):
    metadata = analysis_result.metadata
    assert "backup_old.php" in metadata["by_pattern"]["old suffix"]
    assert "services/api/fetch_orders-20230816.php" in metadata["by_pattern"]["date-stamped file"]
    assert "utils_backup2.php" in metadata["by_pattern"]["explicit backup suffix"]
    assert "config.bak" in metadata["by_pattern"][".bak extension"]
    assert "upload.php~" in metadata["by_pattern"]["tilde backup"]
    assert "x-----services1.php" in metadata["by_pattern"]["x--- prefix (disabled file)"]
    assert "report_copy.php" in metadata["by_pattern"]["copy suffix"]

def test_metadata_counts(analysis_result: AnalysisResult):
    metadata = analysis_result.metadata
    # LOW: _old, _backup, .bak, ~ (4)
    # MEDIUM: date, x---, _copy (3)
    assert metadata["low_risk_count"] == 4
    assert metadata["medium_risk_count"] == 3
    assert metadata["low_risk_count"] + metadata["medium_risk_count"] == len(analysis_result.actions)
