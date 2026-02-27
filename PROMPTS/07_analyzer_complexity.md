# Prompt 07 — analyzers/complexity_analyzer.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ layer complete (01–03)

---

## Task

Implement `analyzers/complexity_analyzer.py`.

This analyzer reads the `summary.most_complex` list and the per-file `total_branches`
from the JSON records to produce a **refactoring priority report**.
It does NOT generate DELETE/MOVE actions — it generates `REPORT_ONLY` actions
that surface complexity hotspots for the developer.

---

## Implementation Requirements

```python
from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

# Thresholds for complexity classification
THRESHOLDS = {
    "critical":  {"max_depth": 15, "total_branches": 100},  # HIGH
    "high":      {"max_depth": 10, "total_branches": 50},   # MEDIUM
    "moderate":  {"max_depth": 5,  "total_branches": 20},   # LOW
}

class ComplexityAnalyzer:
    def __init__(
        self,
        records: dict[str, FileRecord],
        summary: dict                      # from loader.load_summary()
    ) -> None: ...

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

    def _classify(self, record: FileRecord) -> Optional[RiskLevel]:
        """Return RiskLevel or None if below moderate threshold."""

    def _score(self, record: FileRecord) -> int:
        """Return composite complexity score."""
```

### Action format

```python
Action(
    action_type=ActionType.REPORT_ONLY,
    source="saas/service.php",
    destination=None,
    risk_level=RiskLevel.HIGH,
    reason="Complexity score 115 (max_depth=5, total_branches=100). Refactoring recommended."
)
```

---

## Tests — tests/test_complexity_analyzer.py

```python
records = {
    "critical.php":  FileRecord("critical.php",  16, 200),   # critical
    "high.php":      FileRecord("high.php",       11, 60),    # high
    "moderate.php":  FileRecord("moderate.php",   6,  25),    # moderate
    "low.php":       FileRecord("low.php",        1,  2),     # below threshold
    "zero.php":      FileRecord("zero.php",       0,  0),     # below threshold
}
summary = {
    "total_files": 5,
    "total_branches": 287,
    "most_complex": [
        {"file": "critical.php", "max_depth": 16, "total_branches": 200}
    ]
}
```

| Test name | What it checks |
|-----------|----------------|
| `test_returns_analysis_result` | Returns `AnalysisResult` |
| `test_analyzer_name` | `"complexity_analyzer"` |
| `test_critical_is_high_risk` | `critical.php` → HIGH risk action |
| `test_high_is_medium_risk` | `high.php` → MEDIUM risk action |
| `test_moderate_is_low_risk` | `moderate.php` → LOW risk action |
| `test_below_threshold_no_action` | `low.php` and `zero.php` → no actions |
| `test_all_actions_are_report_only` | All `action_type == REPORT_ONLY` |
| `test_sorted_worst_first` | `critical.php` appears before `high.php` in actions |
| `test_metadata_counts` | `critical_count=1, high_count=1, moderate_count=1` |
| `test_top10_in_metadata` | `metadata["top10"]` contains `critical.php` |
| `test_no_complex_files` | Records with all zero complexity → 0 actions |

---

## Deliverables

1. `analyzers/complexity_analyzer.py`
2. `tests/test_complexity_analyzer.py`

**Verify:** `pytest tests/test_complexity_analyzer.py -v` must pass with 0 failures.
