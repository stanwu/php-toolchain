from __future__ import annotations

from typing import Any, Optional

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

# Thresholds for complexity classification
THRESHOLDS: dict[str, dict[str, int]] = {
    "critical": {"max_depth": 15, "total_branches": 100},  # HIGH
    "high": {"max_depth": 10, "total_branches": 50},  # MEDIUM
    "moderate": {"max_depth": 5, "total_branches": 20},  # LOW
}


class ComplexityAnalyzer:
    def __init__(self, records: dict[str, FileRecord], summary: dict[str, Any]) -> None:
        self._records = records
        self._summary = summary

    def analyze(self) -> AnalysisResult:
        """
        1. Build complexity score for every file in records:
             score = max_depth * 3 + total_branches
        2. Classify each file using THRESHOLDS:
             critical → HIGH risk REPORT_ONLY action
             high     → MEDIUM risk REPORT_ONLY action
             moderate → LOW risk REPORT_ONLY action
             below moderate → no action
        3. Sort actions by score descending (worst first).
        4. Also include any file from summary["most_complex"] that
           isn't already classified (handles vendor files we filtered out).
        5. Return AnalysisResult:
             analyzer_name = "complexity_analyzer"
             actions = [REPORT_ONLY actions, sorted worst-first]
             metadata = {
               "total_analyzed": N,
               "critical_count": N,
               "high_count": N,
               "moderate_count": N,
               "top10": [{"file": ..., "score": ..., "max_depth": ..., "total_branches": ...}]
             }
        """
        actions: list[Action] = []
        action_scores: dict[str, int] = {}
        classified_sources: set[str] = set()

        critical_count = 0
        high_count = 0
        moderate_count = 0

        def add_action(source: str, record: FileRecord, risk_level: RiskLevel) -> None:
            score = self._score(record)
            action_scores[source] = score
            classified_sources.add(source)
            actions.append(
                Action(
                    action_type=ActionType.REPORT_ONLY,
                    source=source,
                    destination=None,
                    risk_level=risk_level,
                    reason=(
                        f"Complexity score {score} (max_depth={record.max_depth}, "
                        f"total_branches={record.total_branches}). Refactoring recommended."
                    ),
                )
            )

        for rel_path, record in self._records.items():
            risk = self._classify(record)
            if risk is None:
                continue

            if risk == RiskLevel.HIGH:
                critical_count += 1
            elif risk == RiskLevel.MEDIUM:
                high_count += 1
            elif risk == RiskLevel.LOW:
                moderate_count += 1

            add_action(rel_path, record, risk)

        most_complex = self._summary.get("most_complex") or []
        for entry in most_complex:
            try:
                rel_path = str(entry["file"])
                record = FileRecord(
                    rel_path,
                    int(entry.get("max_depth", 0)),
                    int(entry.get("total_branches", 0)),
                )
            except Exception:
                continue

            if rel_path in classified_sources:
                continue

            risk = self._classify(record)
            if risk is None:
                continue

            if risk == RiskLevel.HIGH:
                critical_count += 1
            elif risk == RiskLevel.MEDIUM:
                high_count += 1
            elif risk == RiskLevel.LOW:
                moderate_count += 1

            add_action(rel_path, record, risk)

        actions.sort(key=lambda a: (-action_scores.get(a.source, 0), a.source))

        top10: list[dict[str, Any]] = []
        for action in actions[:10]:
            rel_path = action.source
            record = self._records.get(rel_path)
            if record is None:
                record = next(
                    (
                        FileRecord(
                            str(e.get("file", "")),
                            int(e.get("max_depth", 0)),
                            int(e.get("total_branches", 0)),
                        )
                        for e in most_complex
                        if str(e.get("file", "")) == rel_path
                    ),
                    None,
                )
            if record is None:
                record = FileRecord(rel_path, 0, 0)

            top10.append(
                {
                    "file": rel_path,
                    "score": action_scores.get(rel_path, self._score(record)),
                    "max_depth": record.max_depth,
                    "total_branches": record.total_branches,
                }
            )

        return AnalysisResult(
            analyzer_name="complexity_analyzer",
            actions=actions,
            metadata={
                "total_analyzed": len(self._records),
                "critical_count": critical_count,
                "high_count": high_count,
                "moderate_count": moderate_count,
                "top10": top10,
            },
        )

    def _classify(self, record: FileRecord) -> Optional[RiskLevel]:
        """Return RiskLevel or None if below moderate threshold."""
        if record.max_depth >= THRESHOLDS["critical"]["max_depth"] or record.total_branches >= THRESHOLDS["critical"][
            "total_branches"
        ]:
            return RiskLevel.HIGH
        if record.max_depth >= THRESHOLDS["high"]["max_depth"] or record.total_branches >= THRESHOLDS["high"][
            "total_branches"
        ]:
            return RiskLevel.MEDIUM
        if record.max_depth >= THRESHOLDS["moderate"]["max_depth"] or record.total_branches >= THRESHOLDS[
            "moderate"
        ]["total_branches"]:
            return RiskLevel.LOW
        return None

    def _score(self, record: FileRecord) -> int:
        """Return composite complexity score."""
        return (int(record.max_depth) * 3) + int(record.total_branches)

