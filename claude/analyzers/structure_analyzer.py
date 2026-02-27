import itertools
import logging
from pathlib import Path

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.7


class StructureAnalyzer:
    def __init__(self, records: dict[str, FileRecord]) -> None:
        self._records = records

    def analyze(self) -> AnalysisResult:
        """
        1. Build a directory → set[basename] map from all paths.
        2. For each pair of directories (A, B):
             similarity = jaccard(basenames_A, basenames_B)
             if similarity >= SIMILARITY_THRESHOLD and A != B:
               flag the pair.
        3. Avoid reporting both (A,B) and (B,A) — use sorted tuple as key.
        4. Generate one REPORT_ONLY action per flagged pair.
           Risk level: HIGH if similarity >= 0.9, MEDIUM otherwise.
        5. Return AnalysisResult with similar_pairs metadata.
        """
        dir_map = self._build_dir_map()
        dirs = list(dir_map.keys())

        seen_pairs: set[tuple[str, str]] = set()
        similar_pairs: list[dict] = []
        actions: list[Action] = []

        for dir_a, dir_b in itertools.combinations(dirs, 2):
            pair_key = (min(dir_a, dir_b), max(dir_a, dir_b))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            basenames_a = dir_map[dir_a]
            basenames_b = dir_map[dir_b]

            similarity = self._jaccard(basenames_a, basenames_b)
            if similarity < SIMILARITY_THRESHOLD:
                continue

            common = sorted(basenames_a & basenames_b)
            # source/dest use sorted order for deterministic output
            source, dest = pair_key
            only_in_source = sorted(dir_map[source] - dir_map[dest])
            only_in_dest = sorted(dir_map[dest] - dir_map[source])

            risk = RiskLevel.HIGH if similarity >= 0.9 else RiskLevel.MEDIUM
            sim_pct = round(similarity * 100)
            reason = (
                f"Directories share {sim_pct}% of file names "
                f"(Jaccard={similarity:.2f}). Possible duplicate."
            )

            actions.append(Action(
                action_type=ActionType.REPORT_ONLY,
                source=source,
                destination=dest,
                risk_level=risk,
                reason=reason,
            ))

            similar_pairs.append({
                "dir_a": source,
                "dir_b": dest,
                "similarity": round(similarity, 4),
                "common_files": common,
                "only_in_a": only_in_source,
                "only_in_b": only_in_dest,
            })

        logger.info(
            "structure_analyzer: %d directories checked, %d similar pairs found",
            len(dirs),
            len(similar_pairs),
        )

        return AnalysisResult(
            analyzer_name="structure_analyzer",
            actions=actions,
            metadata={
                "similar_pairs": similar_pairs,
                "total_directories": len(dirs),
            },
        )

    def _build_dir_map(self) -> dict[str, set[str]]:
        """
        Return {directory_path: {basename, ...}} for all directories
        that appear in records.
        Root-level files go under "" (empty string).
        """
        dir_map: dict[str, set[str]] = {}
        for path_str in self._records:
            p = Path(path_str)
            parent = "" if p.parent == Path(".") else str(p.parent)
            basename = p.name
            if parent not in dir_map:
                dir_map[parent] = set()
            dir_map[parent].add(basename)
        return dir_map

    def _jaccard(self, set_a: set[str], set_b: set[str]) -> float:
        """Jaccard similarity: |A ∩ B| / |A ∪ B|. Return 0.0 if both empty."""
        if not set_a and not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)
