from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

# (pattern, risk_level, label)
BACKUP_PATTERNS: list[tuple[str, RiskLevel, str]] = [
    # LOW risk — clearly abandoned
    (r"_backup\d*\.(php|txt|sql)$", RiskLevel.LOW, "explicit backup suffix"),
    (r"_bak\d*\.(php|txt|sql)$", RiskLevel.LOW, "bak suffix"),
    (r"_old\d*\.(php|txt|sql)$", RiskLevel.LOW, "old suffix"),
    (r"\.bak$", RiskLevel.LOW, ".bak extension"),
    (r"\.orig$", RiskLevel.LOW, ".orig extension"),
    (r"~$", RiskLevel.LOW, "tilde backup"),
    (r"copy_of_", RiskLevel.LOW, "copy_of prefix"),
    # MEDIUM risk — date-stamped or test copies (might be intentional)
    (r"-\d{8}\.(php|txt|sql)$", RiskLevel.MEDIUM, "date-stamped file"),
    (r"_copy\d*\.(php|txt|sql)$", RiskLevel.MEDIUM, "copy suffix"),
    (r"_test\d*\.(php|txt|sql)$", RiskLevel.MEDIUM, "test copy suffix"),
    (r"x-{3,}", RiskLevel.MEDIUM, "x--- prefix (disabled file)"),
]


class BackupAnalyzer:
    def __init__(self, records: dict[str, FileRecord]) -> None:
        self._records = records
        self._compiled: list[tuple[re.Pattern[str], RiskLevel, str, bool]] = []
        for pattern, risk, label in BACKUP_PATTERNS:
            full_path = pattern == r"x-{3,}"
            self._compiled.append((re.compile(pattern, re.IGNORECASE), risk, label, full_path))

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
        low_risk_count = 0
        medium_risk_count = 0

        for rel_path in sorted(self._records):
            matched = self._match_path(rel_path)
            if matched is None:
                continue
            risk_level, label = matched

            if risk_level == RiskLevel.LOW:
                low_risk_count += 1
            elif risk_level == RiskLevel.MEDIUM:
                medium_risk_count += 1

            by_pattern.setdefault(label, []).append(rel_path)
            actions.append(
                Action(
                    action_type=ActionType.DELETE,
                    source=rel_path,
                    destination=None,
                    risk_level=risk_level,
                    reason=f"Backup-like file detected ({label}).",
                )
            )

        return AnalysisResult(
            analyzer_name="backup_analyzer",
            actions=actions,
            metadata={
                "by_pattern": by_pattern,
                "low_risk_count": low_risk_count,
                "medium_risk_count": medium_risk_count,
            },
        )

    def _match_path(self, path: str) -> Optional[tuple[RiskLevel, str]]:
        """
        Test path (basename only, not full path) against BACKUP_PATTERNS.
        Return (risk_level, label) for the first match, or None.
        """
        normalized = path.replace("\\", "/").lstrip("./")
        basename = Path(normalized).name

        for pattern, risk_level, label, full_path in self._compiled:
            target = normalized if full_path else basename
            if pattern.search(target):
                return risk_level, label

        return None
