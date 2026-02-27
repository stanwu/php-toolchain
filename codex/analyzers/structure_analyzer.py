from __future__ import annotations

from pathlib import Path

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

SIMILARITY_THRESHOLD = 0.7


class StructureAnalyzer:
    def __init__(self, records: dict[str, FileRecord]) -> None:
        self._records = records

    def analyze(self) -> AnalysisResult:
        dir_map = self._build_dir_map()
        dirs = sorted(dir_map)

        actions: list[Action] = []
        similar_pairs: list[dict[str, object]] = []

        for i, dir_a in enumerate(dirs):
            for dir_b in dirs[i + 1 :]:
                similarity = self._jaccard(dir_map[dir_a], dir_map[dir_b])
                if similarity < SIMILARITY_THRESHOLD:
                    continue

                common = sorted(dir_map[dir_a].intersection(dir_map[dir_b]))
                only_in_a = sorted(dir_map[dir_a].difference(dir_map[dir_b]))
                only_in_b = sorted(dir_map[dir_b].difference(dir_map[dir_a]))

                risk_level = RiskLevel.HIGH if similarity >= 0.9 else RiskLevel.MEDIUM
                pct = int(round(similarity * 100.0))

                actions.append(
                    Action(
                        action_type=ActionType.REPORT_ONLY,
                        source=dir_a,
                        destination=dir_b,
                        risk_level=risk_level,
                        reason=(
                            f"Directories share {pct}% of file names (Jaccard={similarity:.2f}). "
                            "Possible duplicate."
                        ),
                    )
                )

                similar_pairs.append(
                    {
                        "dir_a": dir_a,
                        "dir_b": dir_b,
                        "similarity": similarity,
                        "common_files": common,
                        "only_in_a": only_in_a,
                        "only_in_b": only_in_b,
                    }
                )

        return AnalysisResult(
            analyzer_name="structure_analyzer",
            actions=actions,
            metadata={
                "similar_pairs": similar_pairs,
                "total_directories": len(dir_map),
            },
        )

    def _build_dir_map(self) -> dict[str, set[str]]:
        dir_map: dict[str, set[str]] = {}
        for rel_path in self._records:
            normalized = rel_path.replace("\\", "/").lstrip("./")
            p = Path(normalized)
            parent = p.parent.as_posix()
            dir_key = "" if parent in (".", "") else parent
            dir_map.setdefault(dir_key, set()).add(p.name)
        return dir_map

    def _jaccard(self, set_a: set[str], set_b: set[str]) -> float:
        if not set_a and not set_b:
            return 0.0
        union = set_a.union(set_b)
        if not union:
            return 0.0
        return len(set_a.intersection(set_b)) / len(union)

