# Prompt 08 — analyzers/structure_analyzer.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ layer complete (01–03)

---

## Task

Implement `analyzers/structure_analyzer.py`.

This analyzer finds **semantically duplicate directories** — directories whose
file-name sets are highly similar, suggesting one may be a copy or outdated
version of another. It uses **Jaccard similarity** on the set of file basenames
within each directory.

This is `REPORT_ONLY` — no automated deletion, just surfacing for developer review.

---

## Implementation Requirements

```python
from pathlib import Path
from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

SIMILARITY_THRESHOLD = 0.7   # Jaccard similarity ≥ 0.7 → flag as similar

class StructureAnalyzer:
    def __init__(self, records: dict[str, FileRecord]) -> None: ...

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
        5. Return AnalysisResult:
             analyzer_name = "structure_analyzer"
             actions = [REPORT_ONLY per similar pair]
             metadata = {
               "similar_pairs": [
                 {"dir_a": ..., "dir_b": ..., "similarity": 0.85,
                  "common_files": [...], "only_in_a": [...], "only_in_b": [...]}
               ],
               "total_directories": N
             }
        """

    def _build_dir_map(self) -> dict[str, set[str]]:
        """
        Return {directory_path: {basename, ...}} for all directories
        that appear in records.
        Use the parent of each file path as its directory.
        Root-level files go under "" (empty string).
        """

    def _jaccard(self, set_a: set[str], set_b: set[str]) -> float:
        """Jaccard similarity: |A ∩ B| / |A ∪ B|. Return 0.0 if both empty."""
```

### Action format

```python
Action(
    action_type=ActionType.REPORT_ONLY,
    source="services/api",          # dir_a
    destination="services/api_old", # dir_b (reuse destination field)
    risk_level=RiskLevel.HIGH,
    reason="Directories share 92% of file names (Jaccard=0.92). Possible duplicate."
)
```

---

## Tests — tests/test_structure_analyzer.py

```python
records = {
    # dir "a/" — 4 files
    "a/foo.php":   FileRecord("a/foo.php",   0, 0),
    "a/bar.php":   FileRecord("a/bar.php",   0, 0),
    "a/baz.php":   FileRecord("a/baz.php",   0, 0),
    "a/qux.php":   FileRecord("a/qux.php",   0, 0),
    # dir "b/" — 3 of the same basenames + 1 different
    "b/foo.php":   FileRecord("b/foo.php",   0, 0),
    "b/bar.php":   FileRecord("b/bar.php",   0, 0),
    "b/baz.php":   FileRecord("b/baz.php",   0, 0),
    "b/zzz.php":   FileRecord("b/zzz.php",   0, 0),
    # dir "c/" — completely different
    "c/alpha.php": FileRecord("c/alpha.php", 0, 0),
    "c/beta.php":  FileRecord("c/beta.php",  0, 0),
}
# Jaccard(a, b) = |{foo,bar,baz}| / |{foo,bar,baz,qux,zzz}| = 3/5 = 0.6  → below threshold
# To trigger detection, use a higher-overlap fixture in specific tests.
```

| Test name | What it checks |
|-----------|----------------|
| `test_returns_analysis_result` | Returns `AnalysisResult` |
| `test_analyzer_name` | `"structure_analyzer"` |
| `test_jaccard_identical` | `_jaccard({"a","b"}, {"a","b"}) == 1.0` |
| `test_jaccard_disjoint` | `_jaccard({"a"}, {"b"}) == 0.0` |
| `test_jaccard_partial` | `_jaccard({"a","b","c"}, {"a","b","d"}) == pytest.approx(0.5)` |
| `test_jaccard_empty` | `_jaccard(set(), set()) == 0.0` |
| `test_no_similar_pairs_below_threshold` | Default fixture (0.6) → 0 actions |
| `test_detects_similar_pair` | 90%+ overlap fixture → 1 action |
| `test_no_duplicate_pairs` | (A,B) and (B,A) not both reported |
| `test_high_risk_above_90` | ≥0.9 similarity → HIGH risk |
| `test_medium_risk_above_70` | 0.7–0.89 similarity → MEDIUM risk |
| `test_metadata_similar_pairs` | `metadata["similar_pairs"]` has correct fields |
| `test_metadata_total_directories` | `total_directories` count is correct |

---

## Deliverables

1. `analyzers/structure_analyzer.py`
2. `tests/test_structure_analyzer.py`

**Verify:** `pytest tests/test_structure_analyzer.py -v` must pass with 0 failures.
