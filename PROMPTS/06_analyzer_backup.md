# Prompt 06 — analyzers/backup_analyzer.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ layer complete (01–03)

---

## Task

Implement `analyzers/backup_analyzer.py`.

This analyzer uses **regex pattern matching** on file paths to identify
abandoned backup files. It classifies each match into two buckets:
- **Safe to delete (LOW risk):** strong unambiguous backup markers
- **Needs review (MEDIUM risk):** patterns that might be intentional

---

## Implementation Requirements

```python
import re
from pathlib import Path
from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

# (pattern, risk_level, label)
BACKUP_PATTERNS: list[tuple[str, RiskLevel, str]] = [
    # LOW risk — clearly abandoned
    (r"_backup\d*\.(php|txt|sql)$",   RiskLevel.LOW,    "explicit backup suffix"),
    (r"_bak\d*\.(php|txt|sql)$",      RiskLevel.LOW,    "bak suffix"),
    (r"_old\d*\.(php|txt|sql)$",      RiskLevel.LOW,    "old suffix"),
    (r"\.bak$",                        RiskLevel.LOW,    ".bak extension"),
    (r"\.orig$",                       RiskLevel.LOW,    ".orig extension"),
    (r"~$",                            RiskLevel.LOW,    "tilde backup"),
    (r"copy_of_",                      RiskLevel.LOW,    "copy_of prefix"),
    # MEDIUM risk — date-stamped or test copies (might be intentional)
    (r"-\d{8}\.(php|txt|sql)$",        RiskLevel.MEDIUM, "date-stamped file"),
    (r"_copy\d*\.(php|txt|sql)$",      RiskLevel.MEDIUM, "copy suffix"),
    (r"_test\d*\.(php|txt|sql)$",      RiskLevel.MEDIUM, "test copy suffix"),
    (r"x-{3,}",                        RiskLevel.MEDIUM, "x--- prefix (disabled file)"),
]

class BackupAnalyzer:
    def __init__(self, records: dict[str, FileRecord]) -> None: ...

    def analyze(self) -> AnalysisResult:
        """
        Scan all paths in records against BACKUP_PATTERNS.
        For each match:
        - Create a DELETE Action at the matched risk level.
        - A path matches the FIRST pattern that applies (no double-counting).
        Return AnalysisResult:
          analyzer_name = "backup_analyzer"
          actions = [DELETE actions]
          metadata = {
            "by_pattern": {"explicit backup suffix": [...paths], ...},
            "low_risk_count": N,
            "medium_risk_count": N
          }
        """

    def _match_path(self, path: str) -> Optional[tuple[RiskLevel, str]]:
        """
        Test path (basename only, not full path) against BACKUP_PATTERNS.
        Return (risk_level, label) for the first match, or None.
        """
```

### Notes

- Match against the **basename** of the path (last component), not the full path
  — this prevents `vendor/phpoffice/backup_tool/` from falsely triggering
- Exception: `x---` pattern matches against the **full path** (including directory names)
- Case-insensitive matching (`re.IGNORECASE`)
- `exists_on_disk` is ignored here — we trust the JSON record for planning

---

## Tests — tests/test_backup_analyzer.py

Build records inline (no disk access needed).

**Fixture paths:**

```python
paths = [
    "index.php",                           # no match
    "saas/service.php",                    # no match
    "backup_old.php",                      # matches _old → LOW
    "services/api/fetch_orders-20230816.php",  # matches date → MEDIUM
    "utils_backup2.php",                   # matches _backup → LOW
    "config.bak",                          # matches .bak → LOW
    "upload.php~",                         # matches ~ → LOW
    "x-----services1.php",                 # matches x--- → MEDIUM
    "report_copy.php",                     # matches _copy → MEDIUM
    "vendor/lib/autoload.php",             # no match (vendor — not a backup pattern)
]
records = {p: FileRecord(p, 0, 0) for p in paths}
```

| Test name | What it checks |
|-----------|----------------|
| `test_returns_analysis_result` | Returns `AnalysisResult` |
| `test_analyzer_name` | `"backup_analyzer"` |
| `test_no_match_for_clean_files` | `index.php`, `saas/service.php` not in any action |
| `test_old_suffix_low_risk` | `backup_old.php` → DELETE, LOW |
| `test_date_stamp_medium_risk` | `fetch_orders-20230816.php` → DELETE, MEDIUM |
| `test_bak_extension_low_risk` | `config.bak` → DELETE, LOW |
| `test_tilde_low_risk` | `upload.php~` → DELETE, LOW |
| `test_x_prefix_medium_risk` | `x-----services1.php` → DELETE, MEDIUM |
| `test_copy_medium_risk` | `report_copy.php` → DELETE, MEDIUM |
| `test_vendor_not_matched` | `vendor/lib/autoload.php` → no action |
| `test_no_double_count` | Each path appears in at most one action |
| `test_metadata_by_pattern` | `metadata["by_pattern"]` groups paths correctly |
| `test_metadata_counts` | `low_risk_count` + `medium_risk_count` == total actions |

---

## Deliverables

1. `analyzers/backup_analyzer.py`
2. `tests/test_backup_analyzer.py`

**Verify:** `pytest tests/test_backup_analyzer.py -v` must pass with 0 failures.
