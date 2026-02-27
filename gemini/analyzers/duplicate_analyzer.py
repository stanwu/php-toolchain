import hashlib
import logging
import re
from pathlib import Path
from typing import Optional, Dict, List

from core.models import (
    FileRecord, DuplicateGroup, AnalysisResult, Action, ActionType, RiskLevel
)

# Heuristics for scoring a path as the "canonical" (original) copy.
# Lower score = more likely to be the original.
CANONICAL_SCORE_RULES = [
    # (pattern_to_penalize, score_increase)
    (r"_copy", 10),
    (r"_bak", 10),
    (r"_old", 10),
    (r"_backup", 10),
    (r"copy_of", 10),
    (r"\(\d+\)", 10),          # e.g. file(1).php
    (r"-\d{8}", 5),             # e.g. file-20230816.php
    (r"/test/", 5),             # test directories are less likely canonical
    (r"/backup/", 20),
    (r"/bak/", 20),
]

class DuplicateAnalyzer:
    def __init__(
        self,
        records: Dict[str, FileRecord],
        project_dir: Path
    ) -> None:
        self.records = records
        self.project_dir = project_dir
        self.logger = logging.getLogger(__name__)

    def analyze(self) -> AnalysisResult:
        """
        1. Hash all files in records that exist on disk (exists_on_disk=True).
        2. Group files by SHA-256.
        3. For each group with 2+ files:
           a. Score each path with _score_path() to pick the canonical.
           b. Mark the rest as copies.
           c. If all copies score the same, mark as HIGH risk (ambiguous).
           d. Otherwise mark as MEDIUM risk (confident canonical).
        4. Generate DELETE action for each copy:
           - MEDIUM risk when canonical is clear
           - HIGH risk when ambiguous
        5. Return AnalysisResult:
             analyzer_name = "duplicate_analyzer"
             actions = [DELETE for each non-canonical copy]
             metadata = {
               "groups": [DuplicateGroup(...), ...],
               "total_duplicate_files": N,
               "total_wasted_bytes": N
             }
        """
        hashes: Dict[str, List[str]] = {}
        file_sizes: Dict[str, int] = {}

        for path_str, record in self.records.items():
            if not record.exists_on_disk:
                continue

            abs_path = self.project_dir / path_str
            try:
                file_size = abs_path.stat().st_size
                if file_size < 1:
                    continue
            except OSError as e:
                self.logger.warning(f"Could not stat file {abs_path}: {e}")
                continue

            file_hash = self._hash_file(abs_path)
            if file_hash:
                hashes.setdefault(file_hash, []).append(path_str)
                file_sizes[file_hash] = file_size

        duplicate_groups = self._build_groups(hashes)
        actions: List[Action] = []
        total_wasted_bytes = 0

        for group in duplicate_groups:
            file_size = file_sizes.get(group.sha256, 0)
            if len(group.files) > 1:
                total_wasted_bytes += (len(group.files) - 1) * file_size

            scores = {path: self._score_path(path) for path in group.files}
            min_score = min(scores.values())
            
            potential_canonicals = [path for path, score in scores.items() if score == min_score]

            is_ambiguous = len(potential_canonicals) > 1 or len(group.files) >= 5
            
            if not is_ambiguous:
                canonical_path = potential_canonicals[0]
                group.canonical = canonical_path
                group.copies = sorted([p for p in group.files if p != canonical_path])
                risk = RiskLevel.MEDIUM
                
                for copy_path in group.copies:
                    actions.append(Action(
                        action_type=ActionType.DELETE,
                        source=copy_path,
                        destination=None,
                        risk_level=risk,
                        reason=f"Duplicate of '{canonical_path}'"
                    ))
            else:  # Ambiguous
                group.copies = sorted(group.files)
                risk = RiskLevel.HIGH
                reason_file = group.copies[0]
                
                for file_path in group.copies:
                    actions.append(Action(
                        action_type=ActionType.DELETE,
                        source=file_path,
                        destination=None,
                        risk_level=risk,
                        reason=f"Ambiguous duplicate of '{reason_file}' (and others)"
                    ))

        total_duplicate_files_to_delete = len(actions)

        return AnalysisResult(
            analyzer_name="duplicate_analyzer",
            actions=actions,
            metadata={
                "groups": [g.__dict__ for g in duplicate_groups],
                "total_duplicate_files": total_duplicate_files_to_delete,
                "total_wasted_bytes": total_wasted_bytes,
            }
        )

    def _hash_file(self, abs_path: Path) -> Optional[str]:
        """
        Return SHA-256 hex string, or None on IO error. Read in 64KB chunks.
        Use hashlib.sha256() — do NOT use MD5.
        """
        sha256 = hashlib.sha256()
        try:
            with open(abs_path, "rb") as f:
                while chunk := f.read(65536):  # 64KB chunks
                    sha256.update(chunk)
            return sha256.hexdigest()
        except IOError as e:
            self.logger.warning(f"Error hashing file {abs_path}: {e}")
            return None

    def _score_path(self, path: str) -> int:
        """
        Lower score = more likely canonical.
        Apply CANONICAL_SCORE_RULES regex patterns.
        Shorter path gets a small bonus (lower score).
        """
        score = 0
        normalized_path = path.replace("\\", "/")
        
        for pattern, penalty in CANONICAL_SCORE_RULES:
            if re.search(pattern, normalized_path, re.IGNORECASE):
                score += penalty
        
        score += len(Path(path).parts)
        
        return score

    def _build_groups(
        self, hashes: Dict[str, List[str]]
    ) -> List[DuplicateGroup]:
        """Convert hash→paths map into DuplicateGroup list."""
        groups = []
        for sha256, paths in hashes.items():
            if len(paths) > 1:
                groups.append(DuplicateGroup(
                    sha256=sha256,
                    files=sorted(paths),
                    canonical=None,
                    copies=[]
                ))
        return groups