# Prompt 05 — analyzers/duplicate_analyzer.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ layer complete (01–03)

---

## Task

Implement `analyzers/duplicate_analyzer.py`.

This analyzer finds files with identical content (same MD5) on disk,
then uses **path semantics** to infer which copy is the canonical original
and which are copies to be removed.

---

## Implementation Requirements

```python
from pathlib import Path
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
        records: dict[str, FileRecord],
        project_dir: Path
    ) -> None: ...

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
               "groups": [DuplicateGroup.to_dict(), ...],
               "total_duplicate_files": N,
               "total_wasted_bytes": N
             }
        """

    def _hash_file(self, abs_path: Path) -> Optional[str]:
        """
        Return SHA-256 hex string, or None on IO error. Read in 64KB chunks.
        Use hashlib.sha256() — do NOT use MD5 (vulnerable to hash collisions
        that could cause two different files to be treated as duplicates,
        leading to incorrect deletion of valid files).
        """

    def _score_path(self, path: str) -> int:
        """
        Lower score = more likely canonical.
        Apply CANONICAL_SCORE_RULES regex patterns.
        Shorter path gets a small bonus (−1 per fewer path components vs. max).
        """

    def _build_groups(
        self, hashes: dict[str, list[str]]
    ) -> list[DuplicateGroup]:
        """Convert hash→paths map into DuplicateGroup list."""
```

### Edge cases

- Files that **do not exist on disk** (`exists_on_disk=False`) are skipped entirely
- Files < 1 byte are skipped (empty files are not meaningful duplicates)
- Hash collisions across very large groups (5+ files) are kept as HIGH risk
- IO errors during hashing are logged as WARNING and the file is skipped

---

## Tests — tests/test_duplicate_analyzer.py

Use `tmp_path` to create real files with known content.

**Fixture setup:**

```python
# In tmp_path:
# utils.php         → content "<?php function helper(){}"
# utils_copy.php    → SAME content as utils.php
# service.php       → content "<?php class Service{}"
# service_old.php   → SAME content as service.php
# unique.php        → content "<?php echo 1;"
```

Records must have `exists_on_disk=True` for all files.

| Test name | What it checks |
|-----------|----------------|
| `test_returns_analysis_result` | Returns `AnalysisResult` |
| `test_analyzer_name` | `result.analyzer_name == "duplicate_analyzer"` |
| `test_finds_two_groups` | 2 duplicate groups detected |
| `test_unique_file_not_in_groups` | `unique.php` not in any group |
| `test_canonical_inference_copy_suffix` | `utils.php` chosen as canonical over `utils_copy.php` |
| `test_canonical_inference_old_suffix` | `service.php` chosen over `service_old.php` |
| `test_delete_action_for_copy` | DELETE action generated for each non-canonical |
| `test_medium_risk_clear_canonical` | Clear canonical → MEDIUM risk |
| `test_high_risk_ambiguous` | Two files with equal scores → HIGH risk |
| `test_skips_nonexistent_files` | `exists_on_disk=False` files not hashed |
| `test_hash_uses_sha256` | `_hash_file()` returns a 64-character hex string (SHA-256 length, not 32-char MD5) |
| `test_metadata_total_wasted_bytes` | `total_wasted_bytes` > 0 |
| `test_no_duplicates_no_actions` | All unique files → 0 actions |

---

## Deliverables

1. `analyzers/duplicate_analyzer.py`
2. `tests/test_duplicate_analyzer.py`

**Verify:** `pytest tests/test_duplicate_analyzer.py -v` must pass with 0 failures.
