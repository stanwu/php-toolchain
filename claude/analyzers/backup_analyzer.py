import re
import logging
from pathlib import Path
from typing import Optional

from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

logger = logging.getLogger(__name__)

# (pattern, risk_level, label)
BACKUP_PATTERNS: list[tuple[str, RiskLevel, str]] = [
    # LOW risk — clearly abandoned (matched against basename)
    (r"_backup\d*\.(php|txt|sql)$",   RiskLevel.LOW,    "explicit backup suffix"),
    (r"_bak\d*\.(php|txt|sql)$",      RiskLevel.LOW,    "bak suffix"),
    (r"_old\d*\.(php|txt|sql)$",      RiskLevel.LOW,    "old suffix"),
    (r"\.bak$",                        RiskLevel.LOW,    ".bak extension"),
    (r"\.orig$",                       RiskLevel.LOW,    ".orig extension"),
    (r"~$",                            RiskLevel.LOW,    "tilde backup"),
    (r"copy_of_",                      RiskLevel.LOW,    "copy_of prefix"),
    # MEDIUM risk — date-stamped or test copies (matched against basename)
    (r"-\d{8}\.(php|txt|sql)$",        RiskLevel.MEDIUM, "date-stamped file"),
    (r"_copy\d*\.(php|txt|sql)$",      RiskLevel.MEDIUM, "copy suffix"),
    (r"_test\d*\.(php|txt|sql)$",      RiskLevel.MEDIUM, "test copy suffix"),
    # MEDIUM risk — x--- prefix matched against full path
    (r"x-{3,}",                        RiskLevel.MEDIUM, "x--- prefix (disabled file)"),
]

# Patterns that match against the full path (not just basename)
_FULL_PATH_LABELS = {"x--- prefix (disabled file)"}


class BackupAnalyzer:
    def __init__(self, records: dict[str, FileRecord]) -> None:
        self._records = records

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
        actions: list[Action] = []
        by_pattern: dict[str, list[str]] = {}
        low_count = 0
        medium_count = 0

        for path in self._records:
            match = self._match_path(path)
            if match is None:
                continue

            risk_level, label = match
            action = Action(
                action_type=ActionType.DELETE,
                source=path,
                destination=None,
                risk_level=risk_level,
                reason=f"Backup file detected: {label}",
            )
            actions.append(action)

            by_pattern.setdefault(label, []).append(path)

            if risk_level == RiskLevel.LOW:
                low_count += 1
            elif risk_level == RiskLevel.MEDIUM:
                medium_count += 1

        return AnalysisResult(
            analyzer_name="backup_analyzer",
            actions=actions,
            metadata={
                "by_pattern": by_pattern,
                "low_risk_count": low_count,
                "medium_risk_count": medium_count,
            },
        )

    def _match_path(self, path: str) -> Optional[tuple[RiskLevel, str]]:
        """
        Test path against BACKUP_PATTERNS.
        Most patterns match the basename only; the x--- pattern matches the full path.
        Return (risk_level, label) for the first match, or None.
        """
        basename = Path(path).name

        for pattern, risk_level, label in BACKUP_PATTERNS:
            target = path if label in _FULL_PATH_LABELS else basename
            if re.search(pattern, target, re.IGNORECASE):
                logger.debug("Path %r matched pattern %r (%s)", path, pattern, label)
                return risk_level, label

        return None
