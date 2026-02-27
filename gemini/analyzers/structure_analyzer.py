"""
Analyzes directory structures to find semantically duplicate directories.

This analyzer identifies directories that have a similar set of file names,
suggesting one might be a copy or an outdated version of another. It uses
the Jaccard similarity index on the sets of file basenames within each
directory.

The analysis is report-only and does not suggest any automated actions like
deletion. It's intended to surface potential structural duplication for
manual review.
"""
from pathlib import Path
from itertools import combinations
from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

SIMILARITY_THRESHOLD = 0.7   # Jaccard similarity ≥ 0.7 → flag as similar
HIGH_RISK_THRESHOLD = 0.9    # Jaccard similarity ≥ 0.9 → high risk

class StructureAnalyzer:
    """
    Finds pairs of directories with highly similar file name compositions.
    """
    def __init__(self, records: dict[str, FileRecord]) -> None:
        """
        Initializes the analyzer with file records from the scanner.

        Args:
            records: A dictionary mapping relative file paths to FileRecord objects.
        """
        self._records = records

    def _jaccard(self, set_a: set[str], set_b: set[str]) -> float:
        """
        Calculates the Jaccard similarity between two sets.

        Jaccard similarity = |A ∩ B| / |A ∪ B|.

        Returns:
            A float between 0.0 and 1.0. Returns 0.0 if both sets are empty.
        """
        if not set_a and not set_b:
            return 0.0

        intersection_len = len(set_a.intersection(set_b))
        union_len = len(set_a.union(set_b))

        if union_len == 0:
            return 1.0 if intersection_len > 0 else 0.0

        return intersection_len / union_len

    def _build_dir_map(self) -> dict[str, set[str]]:
        """
        Builds a map from directory paths to a set of file basenames in it.

        Returns:
            A dictionary where keys are directory paths (as strings) and
            values are sets of basenames of files within that directory.
            Root-level files are grouped under the key "".
        """
        dir_map: dict[str, set[str]] = {}
        for path_str in self._records:
            p = Path(path_str)
            # Use "" for root directory, otherwise the parent path as a string
            directory = str(p.parent) if str(p.parent) != '.' else ""
            basename = p.name
            if directory not in dir_map:
                dir_map[directory] = set()
            dir_map[directory].add(basename)
        return dir_map

    def analyze(self) -> AnalysisResult:
        """
        Performs the structure analysis to find similar directories.

        1. Builds a directory-to-filenames map.
        2. Computes Jaccard similarity for each pair of directories.
        3. Flags pairs exceeding the similarity threshold.
        4. Generates REPORT_ONLY actions for flagged pairs.

        Returns:
            An AnalysisResult containing the findings.
        """
        dir_map = self._build_dir_map()
        actions: list[Action] = []
        similar_pairs_metadata: list[dict] = []

        # Use combinations to avoid duplicate pairs (A,B) and (B,A) and self-comparison (A,A)
        dir_names = sorted(list(dir_map.keys()))

        for dir_a, dir_b in combinations(dir_names, 2):
            set_a = dir_map[dir_a]
            set_b = dir_map[dir_b]

            similarity = self._jaccard(set_a, set_b)

            if similarity >= SIMILARITY_THRESHOLD:
                if similarity >= HIGH_RISK_THRESHOLD:
                    risk = RiskLevel.HIGH
                else:
                    risk = RiskLevel.MEDIUM

                reason = (
                    f"Directories share {similarity:.0%} of file names "
                    f"(Jaccard={similarity:.2f}). Possible duplicate."
                )

                actions.append(Action(
                    action_type=ActionType.REPORT_ONLY,
                    source=dir_a,
                    destination=dir_b,
                    risk_level=risk,
                    reason=reason
                ))

                similar_pairs_metadata.append({
                    "dir_a": dir_a,
                    "dir_b": dir_b,
                    "similarity": similarity,
                    "common_files": sorted(list(set_a.intersection(set_b))),
                    "only_in_a": sorted(list(set_a.difference(set_b))),
                    "only_in_b": sorted(list(set_b.difference(set_a))),
                })

        return AnalysisResult(
            analyzer_name="structure_analyzer",
            actions=actions,
            metadata={
                "similar_pairs": similar_pairs_metadata,
                "total_directories": len(dir_map)
            }
        )
