from __future__ import annotations

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


# Heuristics for scoring a path as the "canonical" (original) copy.
# Lower score = more likely to be the original.
CANONICAL_SCORE_RULES: list[tuple[str, int]] = [
    # (pattern_to_penalize, score_increase)
    (r"_copy", 10),
    (r"_bak", 10),
    (r"_old", 10),
    (r"_backup", 10),
    (r"copy_of", 10),
    (r"\(\d+\)", 10),  # e.g. file(1).php
    (r"-\d{8}", 5),  # e.g. file-20230816.php
    (r"/test/", 5),  # test directories are less likely canonical
    (r"/backup/", 20),
    (r"/bak/", 20),
]


class DuplicateAnalyzer:
    def __init__(self, records: dict[str, FileRecord], project_dir: Path) -> None:
        self._records = records
        self._project_dir = project_dir
        self._compiled_rules: list[tuple[re.Pattern[str], int]] = [
            (re.compile(pattern, re.IGNORECASE), score) for pattern, score in CANONICAL_SCORE_RULES
        ]
        self._max_components = 0
        for rel in records:
            normalized = rel.replace("\\", "/").lstrip("./")
            components = len([p for p in normalized.split("/") if p])
            self._max_components = max(self._max_components, components)

    def analyze(self) -> AnalysisResult:
        """
        1. Hash all files in records that exist on disk (exists_on_disk=True).
        2. Group files by SHA-256.
        3. For each group with 2+ files:
           a. Score each path with _score_path() to pick the canonical.
           b. Mark the rest as copies.
           c. If canonical is ambiguous (equal best score) or group is large (5+),
              mark as HIGH risk.
           d. Otherwise mark as MEDIUM risk (confident canonical).
        4. Generate DELETE action for each copy.
        5. Return AnalysisResult with DuplicateGroup metadata and byte totals.
        """
        hashes: dict[str, list[str]] = {}
        sizes: dict[str, int] = {}

        for rel_path, record in self._records.items():
            if not record.exists_on_disk:
                continue

            normalized = rel_path.replace("\\", "/").lstrip("./")
            abs_path = (self._project_dir / normalized).resolve()

            try:
                size = abs_path.stat().st_size
            except OSError as exc:
                logger.warning("Failed to stat %s: %s", abs_path, exc)
                continue

            if size < 1:
                continue

            digest = self._hash_file(abs_path)
            if digest is None:
                continue

            hashes.setdefault(digest, []).append(normalized)
            sizes[normalized] = size

        groups = self._build_groups(hashes)

        actions: list[Action] = []
        total_duplicate_files = 0
        total_wasted_bytes = 0

        for group in groups:
            if group.canonical is None:
                continue

            path_scores = {p: self._score_path(p) for p in group.files}
            min_score = min(path_scores.values())
            best = sorted([p for p, s in path_scores.items() if s == min_score])

            ambiguous = len(best) > 1
            large_group = len(group.files) >= 5
            risk = RiskLevel.HIGH if ambiguous or large_group else RiskLevel.MEDIUM

            for copy_path in group.copies:
                total_duplicate_files += 1
                total_wasted_bytes += sizes.get(copy_path, 0)
                actions.append(
                    Action(
                        action_type=ActionType.DELETE,
                        source=copy_path,
                        destination=None,
                        risk_level=risk,
                        reason=(
                            f"Duplicate content (sha256={group.sha256}). "
                            f"Canonical inferred as {group.canonical}; delete duplicate {copy_path}."
                        ),
                    )
                )

        return AnalysisResult(
            analyzer_name="duplicate_analyzer",
            actions=actions,
            metadata={
                "groups": [g.to_dict() for g in groups],
                "total_duplicate_files": total_duplicate_files,
                "total_wasted_bytes": total_wasted_bytes,
            },
        )

    def _hash_file(self, abs_path: Path) -> Optional[str]:
        """
        Return SHA-256 hex string, or None on IO error. Read in 64KB chunks.
        """
        h = hashlib.sha256()
        try:
            with abs_path.open("rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
        except OSError as exc:
            logger.warning("Failed to hash %s: %s", abs_path, exc)
            return None
        return h.hexdigest()

    def _score_path(self, path: str) -> int:
        """
        Lower score = more likely canonical.
        Apply CANONICAL_SCORE_RULES regex patterns.
        Shorter path gets a small bonus (−1 per fewer path components vs. max).
        """
        normalized = path.replace("\\", "/").lstrip("./")
        score = 0
        for pattern, inc in self._compiled_rules:
            if pattern.search(normalized):
                score += inc

        components = len([p for p in normalized.split("/") if p])
        bonus = self._max_components - components
        score -= max(0, bonus)
        return score

    def _build_groups(self, hashes: dict[str, list[str]]) -> list[DuplicateGroup]:
        """Convert hash→paths map into DuplicateGroup list."""
        groups: list[DuplicateGroup] = []

        for sha, paths in hashes.items():
            unique_paths = sorted(set(paths))
            if len(unique_paths) < 2:
                continue

            scores = {p: self._score_path(p) for p in unique_paths}
            min_score = min(scores.values())
            canonical_candidates = sorted([p for p, s in scores.items() if s == min_score])
            canonical = canonical_candidates[0] if canonical_candidates else None
            copies = [p for p in unique_paths if p != canonical]

            groups.append(
                DuplicateGroup(
                    sha256=sha,
                    files=unique_paths,
                    canonical=canonical,
                    copies=copies,
                )
            )

        groups.sort(key=lambda g: (g.sha256, g.canonical or ""))
        return groups
