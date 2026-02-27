import re
from pathlib import Path
from typing import Optional, Dict

from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

# (pattern, risk_level, label)
BACKUP_PATTERNS: list[tuple[str, RiskLevel, str]] = [
    # LOW risk — clearly abandoned
    (r"_backup\d*\.(php|txt|sql)$",   RiskLevel.LOW,    "explicit backup suffix"),
    (r"_bak\d*\.(php|txt|sql)$",      RiskLevel.LOW,    "bak suffix"),
    (r"_old\d*\.(php|txt|sql)$",      RiskLevel.LOW,    "old suffix"),
    (r"\.bak$",                        RiskLevel.LOW,    ".bak extension"),
    (r"\.orig$",                       RiskLevel.LOW,    ".orig extension"),
    (r"~$",                            RiskLevel.LOW,    "tilde backup"),
    (r"copy_of_",                      RiskLevel.LOW,    "copy_of prefix"),
    # MEDIUM risk — date-stamped or test copies (might be intentional)
    (r"-\d{8}\.(php|txt|sql)$",        RiskLevel.MEDIUM, "date-stamped file"),
    (r"_copy\d*\.(php|txt|sql)$",      RiskLevel.MEDIUM, "copy suffix"),
    (r"_test\d*\.(php|txt|sql)$",      RiskLevel.MEDIUM, "test copy suffix"),
    (r"x-{3,}",                        RiskLevel.MEDIUM, "x--- prefix (disabled file)"),
]

class BackupAnalyzer:
    def __init__(self, records: Dict[str, FileRecord]) -> None:
        self.records = records

    def analyze(self) -> AnalysisResult:
        """
        Scan all paths in records against BACKUP_PATTERNS.
        For each match:
        - Create a DELETE Action at the matched risk level.
        - A path matches the FIRST pattern that applies (no double-counting).
        Return AnalysisResult:
          analyzer_name = "backup_analyzer"
          actions = [DELETE actions]
          metadata = {
            "by_pattern": {"explicit backup suffix": [...paths], ...},
            "low_risk_count": N,
            "medium_risk_count": N
          }
        """
        actions = []
        metadata = {
            "by_pattern": {label: [] for _, _, label in BACKUP_PATTERNS},
            "low_risk_count": 0,
            "medium_risk_count": 0
        }

        for path_str in self.records:
            match = self._match_path(path_str)
            if match:
                risk_level, label = match
                action = Action(
                    action_type=ActionType.DELETE,
                    source=path_str,
                    destination=None,
                    risk_level=risk_level,
                    reason=f"File matches backup pattern: {label}"
                )
                actions.append(action)
                metadata["by_pattern"][label].append(path_str)
                if risk_level == RiskLevel.LOW:
                    metadata["low_risk_count"] += 1
                elif risk_level == RiskLevel.MEDIUM:
                    metadata["medium_risk_count"] += 1

        return AnalysisResult(
            analyzer_name="backup_analyzer",
            actions=actions,
            metadata=metadata
        )

    def _match_path(self, path: str) -> Optional[tuple[RiskLevel, str]]:
        """
        Test path (basename only, not full path) against BACKUP_PATTERNS.
        Return (risk_level, label) for the first match, or None.
        """
        basename = Path(path).name
        for pattern, risk_level, label in BACKUP_PATTERNS:
            # Special case for x--- prefix, which matches the full path
            if label == "x--- prefix (disabled file)":
                if re.search(pattern, path, re.IGNORECASE):
                    return risk_level, label
            else:
                if re.search(pattern, basename, re.IGNORECASE):
                    return risk_level, label
        return None
