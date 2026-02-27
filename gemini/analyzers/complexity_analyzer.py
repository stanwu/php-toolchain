"""
Analyzes files for code complexity based on branch count and nesting depth.

This analyzer reads file records and the project summary to identify files that
are overly complex and may be candidates for refactoring. It generates
`REPORT_ONLY` actions, flagging files with different risk levels based on
pre-defined thresholds.

The complexity score is a simple heuristic:
    score = (max_depth * 3) + total_branches
"""

from typing import Optional

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

# Thresholds for complexity classification.
# A file's complexity is checked against these values. If it exceeds any
# value in a category, it's classified at that level.
THRESHOLDS = {
    "critical": {"max_depth": 15, "total_branches": 100},  # HIGH risk
    "high": {"max_depth": 10, "total_branches": 50},      # MEDIUM risk
    "moderate": {"max_depth": 5, "total_branches": 20},   # LOW risk
}


class ComplexityAnalyzer:
    """
    Identifies complex files that should be prioritized for refactoring.
    """

    def __init__(
        self,
        records: dict[str, FileRecord],
        summary: dict  # from loader.load_summary()
    ) -> None:
        """
        Initializes the analyzer with file records and the analysis summary.

        Args:
            records: A dictionary mapping file paths to FileRecord objects.
            summary: A dictionary containing summary data from the analysis report,
                     including the "most_complex" list.
        """
        self._records = records
        self._summary = summary

    def _score(self, record: FileRecord) -> int:
        """
        Calculates a composite complexity score for a file.

        The score is weighted to prioritize reducing nesting depth (max_depth)
        over simply reducing the number of branches.

        Args:
            record: The FileRecord to score.

        Returns:
            The calculated complexity score.
        """
        return (record.max_depth * 3) + record.total_branches

    def _classify(self, record: FileRecord) -> Optional[RiskLevel]:
        """
        Classifies a file's complexity into a RiskLevel based on THRESHOLDS.

        Args:
            record: The FileRecord to classify.

        Returns:
            The corresponding RiskLevel (HIGH, MEDIUM, LOW) or None if the
            complexity is below all defined thresholds.
        """
        if (record.max_depth >= THRESHOLDS["critical"]["max_depth"] or
                record.total_branches >= THRESHOLDS["critical"]["total_branches"]):
            return RiskLevel.HIGH
        if (record.max_depth >= THRESHOLDS["high"]["max_depth"] or
                record.total_branches >= THRESHOLDS["high"]["total_branches"]):
            return RiskLevel.MEDIUM
        if (record.max_depth >= THRESHOLDS["moderate"]["max_depth"] or
                record.total_branches >= THRESHOLDS["moderate"]["total_branches"]):
            return RiskLevel.LOW
        return None

    def analyze(self) -> AnalysisResult:
        """
        Analyzes all file records to find complexity hotspots.

        The process involves:
        1. Scoring and classifying each file based on its max_depth and total_branches.
        2. Creating `REPORT_ONLY` actions for files exceeding moderate complexity.
        3. Incorporating files from the summary's "most_complex" list, which might
           have been filtered out of the main records (e.g., vendor files).
        4. Sorting the resulting actions from most to least complex.
        5. Compiling metadata, including counts and a top-10 list of the most
           complex files.

        Returns:
            An AnalysisResult containing the sorted list of actions and metadata.
        """
        actions = []
        scored_files = []
        processed_files = set()

        # 1. Build complexity score for every file in records
        for record in self._records.values():
            risk_level = self._classify(record)
            score = self._score(record)
            
            if score > 0:
                scored_files.append({
                    "file": record.path,
                    "score": score,
                    "max_depth": record.max_depth,
                    "total_branches": record.total_branches,
                })

            # 2. Classify each file and create actions
            if risk_level:
                reason = (
                    f"Complexity score {score} (max_depth={record.max_depth}, "
                    f"total_branches={record.total_branches}). Refactoring recommended."
                )
                action = Action(
                    action_type=ActionType.REPORT_ONLY,
                    source=record.path,
                    destination=None,
                    risk_level=risk_level,
                    reason=reason,
                )
                actions.append((score, action))
                processed_files.add(record.path)

        # 4. Also include any file from summary["most_complex"] that isn't already classified
        for complex_file_info in self._summary.get("most_complex", []):
            file_path = complex_file_info["file"]
            if file_path not in processed_files and file_path not in self._records:
                # This handles cases like vendor files that are complex but excluded from records
                temp_record = FileRecord(
                    path=file_path,
                    max_depth=complex_file_info["max_depth"],
                    total_branches=complex_file_info["total_branches"]
                )
                risk_level = self._classify(temp_record)
                score = self._score(temp_record)

                if risk_level:
                    reason = (
                        f"Complexity score {score} (max_depth={temp_record.max_depth}, "
                        f"total_branches={temp_record.total_branches}). From summary; refactoring recommended."
                    )
                    action = Action(
                        action_type=ActionType.REPORT_ONLY,
                        source=temp_record.path,
                        destination=None,
                        risk_level=risk_level,
                        reason=reason,
                    )
                    actions.append((score, action))
                    processed_files.add(file_path)


        # 3. Sort actions by score descending (worst first)
        actions.sort(key=lambda item: item[0], reverse=True)
        final_actions = [action for score, action in actions]

        # 5. Prepare metadata
        scored_files.sort(key=lambda x: x["score"], reverse=True)
        
        metadata = {
            "total_analyzed": len(self._records),
            "critical_count": sum(1 for _, action in actions if action.risk_level == RiskLevel.HIGH),
            "high_count": sum(1 for _, action in actions if action.risk_level == RiskLevel.MEDIUM),
            "moderate_count": sum(1 for _, action in actions if action.risk_level == RiskLevel.LOW),
            "top10": scored_files[:10],
        }

        return AnalysisResult(
            analyzer_name="complexity_analyzer",
            actions=final_actions,
            metadata=metadata,
        )
