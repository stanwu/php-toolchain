import logging
from typing import Optional

from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

logger = logging.getLogger(__name__)

THRESHOLDS = {
    "critical": {"max_depth": 15, "total_branches": 100},  # HIGH
    "high":     {"max_depth": 10, "total_branches": 50},   # MEDIUM
    "moderate": {"max_depth": 5,  "total_branches": 20},   # LOW
}


class ComplexityAnalyzer:
    def __init__(
        self,
        records: dict[str, FileRecord],
        summary: dict,
    ) -> None:
        self._records = records
        self._summary = summary

    def analyze(self) -> AnalysisResult:
        actions: list[Action] = []
        scored: list[tuple[int, FileRecord]] = []
        classified_paths: set[str] = set()

        for path, record in self._records.items():
            risk = self._classify(record)
            if risk is None:
                continue
            score = self._score(record)
            scored.append((score, record))
            classified_paths.add(path)

        # Include most_complex entries not already classified
        for entry in self._summary.get("most_complex", []):
            path = entry["file"]
            if path not in classified_paths:
                synthetic = FileRecord(
                    path=path,
                    max_depth=entry.get("max_depth", 0),
                    total_branches=entry.get("total_branches", 0),
                )
                risk = self._classify(synthetic)
                if risk is not None:
                    scored.append((self._score(synthetic), synthetic))
                    classified_paths.add(path)

        # Sort worst-first
        scored.sort(key=lambda t: t[0], reverse=True)

        critical_count = 0
        high_count = 0
        moderate_count = 0

        for score, record in scored:
            risk = self._classify(record)
            if risk == RiskLevel.HIGH:
                critical_count += 1
            elif risk == RiskLevel.MEDIUM:
                high_count += 1
            elif risk == RiskLevel.LOW:
                moderate_count += 1

            reason = (
                f"Complexity score {score} "
                f"(max_depth={record.max_depth}, total_branches={record.total_branches}). "
                f"Refactoring recommended."
            )
            actions.append(
                Action(
                    action_type=ActionType.REPORT_ONLY,
                    source=record.path,
                    destination=None,
                    risk_level=risk,  # type: ignore[arg-type]
                    reason=reason,
                )
            )

        top10 = [
            {
                "file": record.path,
                "score": score,
                "max_depth": record.max_depth,
                "total_branches": record.total_branches,
            }
            for score, record in scored[:10]
        ]

        metadata: dict = {
            "total_analyzed": len(self._records),
            "critical_count": critical_count,
            "high_count": high_count,
            "moderate_count": moderate_count,
            "top10": top10,
        }

        return AnalysisResult(
            analyzer_name="complexity_analyzer",
            actions=actions,
            metadata=metadata,
        )

    def _classify(self, record: FileRecord) -> Optional[RiskLevel]:
        md = record.max_depth
        tb = record.total_branches

        crit = THRESHOLDS["critical"]
        if md >= crit["max_depth"] or tb >= crit["total_branches"]:
            return RiskLevel.HIGH

        high = THRESHOLDS["high"]
        if md >= high["max_depth"] or tb >= high["total_branches"]:
            return RiskLevel.MEDIUM

        mod = THRESHOLDS["moderate"]
        if md >= mod["max_depth"] or tb >= mod["total_branches"]:
            return RiskLevel.LOW

        return None

    def _score(self, record: FileRecord) -> int:
        return record.max_depth * 3 + record.total_branches
