import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from core.models import (
    Action,
    ActionType,
    AnalysisResult,
    DuplicateGroup,
    FileRecord,
    RiskLevel,
)

logger = logging.getLogger(__name__)

CANONICAL_SCORE_RULES: list[tuple[str, int]] = [
    (r"_copy", 10),
    (r"_bak", 10),
    (r"_old", 10),
    (r"_backup", 10),
    (r"copy_of", 10),
    (r"\(\d+\)", 10),
    (r"-\d{8}", 5),
    (r"/test/", 5),
    (r"/backup/", 20),
    (r"/bak/", 20),
]


class DuplicateAnalyzer:
    def __init__(
        self,
        records: dict[str, FileRecord],
        project_dir: Path,
    ) -> None:
        self._records = records
        self._project_dir = project_dir

    def analyze(self) -> AnalysisResult:
        hashes: dict[str, list[str]] = {}

        for rel_path, record in self._records.items():
            if not record.exists_on_disk:
                continue
            abs_path = self._project_dir / rel_path
            try:
                if abs_path.stat().st_size < 1:
                    continue
            except OSError:
                continue
            digest = self._hash_file(abs_path)
            if digest is None:
                continue
            hashes.setdefault(digest, []).append(rel_path)

        dup_hashes = {h: paths for h, paths in hashes.items() if len(paths) >= 2}
        groups = self._build_groups(dup_hashes)

        actions: list[Action] = []
        total_wasted_bytes = 0

        for group in groups:
            # Determine risk: ambiguous when all copies share the same score
            scores = {p: self._score_path(p) for p in group.files}
            score_values = list(scores.values())
            min_score = min(score_values)
            min_count = score_values.count(min_score)
            ambiguous = min_count > 1 or len(group.files) >= 5

            risk = RiskLevel.HIGH if ambiguous else RiskLevel.MEDIUM

            for copy_path in group.copies:
                abs_copy = self._project_dir / copy_path
                try:
                    wasted = abs_copy.stat().st_size
                except OSError:
                    wasted = 0
                total_wasted_bytes += wasted

                canonical_label = group.canonical or "unknown"
                actions.append(
                    Action(
                        action_type=ActionType.DELETE,
                        source=copy_path,
                        destination=None,
                        risk_level=risk,
                        reason=(
                            f"Duplicate of {canonical_label} "
                            f"(SHA-256: {group.sha256[:12]}…)"
                        ),
                    )
                )

        metadata = {
            "groups": [g.to_dict() for g in groups],
            "total_duplicate_files": sum(len(g.files) for g in groups),
            "total_wasted_bytes": total_wasted_bytes,
        }

        return AnalysisResult(
            analyzer_name="duplicate_analyzer",
            actions=actions,
            metadata=metadata,
        )

    def _hash_file(self, abs_path: Path) -> Optional[str]:
        h = hashlib.sha256()
        try:
            with abs_path.open("rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
        except OSError as exc:
            logger.warning("Could not hash %s: %s", abs_path, exc)
            return None
        return h.hexdigest()

    def _score_path(self, path: str) -> int:
        score = 0
        for pattern, penalty in CANONICAL_SCORE_RULES:
            if re.search(pattern, path, re.IGNORECASE):
                score += penalty
        # Shorter path (fewer components) is more likely canonical
        # Bonus: subtract 1 for each component fewer than the max in group
        # The caller adjusts relative scores; here we just count components
        score -= len(Path(path).parts)
        return score

    def _build_groups(
        self, hashes: dict[str, list[str]]
    ) -> list[DuplicateGroup]:
        groups: list[DuplicateGroup] = []
        for digest, paths in hashes.items():
            scores = {p: self._score_path(p) for p in paths}
            sorted_paths = sorted(paths, key=lambda p: (scores[p], p))
            min_score = scores[sorted_paths[0]]
            tied_for_first = [p for p in sorted_paths if scores[p] == min_score]

            if len(tied_for_first) == 1:
                canonical: Optional[str] = sorted_paths[0]
                copies = sorted_paths[1:]
            else:
                # Ambiguous — no confident canonical
                canonical = None
                copies = list(sorted_paths)

            groups.append(
                DuplicateGroup(
                    sha256=digest,
                    files=list(paths),
                    canonical=canonical,
                    copies=copies,
                )
            )
        return groups
