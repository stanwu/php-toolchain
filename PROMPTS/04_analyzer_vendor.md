# Prompt 04 — analyzers/vendor_analyzer.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ layer complete (Prompts 01–03)

---

## Task

Implement `analyzers/vendor_analyzer.py`.

This analyzer identifies vendor directories, calculates how much of the project
they represent, and produces an `ADD_GITIGNORE` action for each vendor root found.

**Context:** In the real project, `vendor/` contains 83% of all files (12,000+ files
from Composer packages). These should never be committed or manually cleaned —
adding them to `.gitignore` is the safest, highest-value action.

---

## Implementation Requirements

```python
from pathlib import Path
from core.models import FileRecord, AnalysisResult, Action, ActionType, RiskLevel

# Vendor directory patterns to detect
VENDOR_PATTERNS = [
    "vendor/",
    "node_modules/",
    "bower_components/",
]

class VendorAnalyzer:
    def __init__(
        self,
        records: dict[str, FileRecord],
        project_dir: Path
    ) -> None: ...

    def analyze(self) -> AnalysisResult:
        """
        1. Find all unique vendor roots (e.g. "vendor", "test/vendor")
           by checking if any path component matches VENDOR_PATTERNS prefixes.
        2. Count files per vendor root.
        3. Calculate percentage: vendor_files / total_files * 100.
        4. For each vendor root, produce one ADD_GITIGNORE Action (LOW risk).
        5. Return AnalysisResult with:
             analyzer_name = "vendor_analyzer"
             actions = [one ADD_GITIGNORE per vendor root]
             metadata = {
               "vendor_roots": { "vendor/": {"file_count": N, "pct": 83.2} },
               "total_vendor_files": N,
               "total_files": N
             }
        """

    def _find_vendor_roots(self) -> dict[str, list[str]]:
        """Return {vendor_root: [file_paths]} for all detected vendor dirs."""

    def _is_vendor_path(self, path: str) -> tuple[bool, str]:
        """
        Check if path starts with any VENDOR_PATTERNS entry.
        Returns (is_vendor, matched_root).
        e.g. "vendor/lib/x.php" → (True, "vendor")
             "test/vendor/y.php" → (True, "test/vendor")
        """
```

### Action format for vendor roots

```python
Action(
    action_type=ActionType.ADD_GITIGNORE,
    source="vendor",           # the root directory name (no trailing slash)
    destination=None,
    risk_level=RiskLevel.LOW,
    reason="vendor/ contains 12043 files (83.2% of project). Add to .gitignore."
)
```

---

## Tests — tests/test_vendor_analyzer.py

**Fixture records (build inline, no file needed):**

```python
records = {
    "index.php": FileRecord("index.php", 1, 2),
    "vendor/autoload.php": FileRecord("vendor/autoload.php", 0, 0),
    "vendor/lib/a.php": FileRecord("vendor/lib/a.php", 1, 2),
    "vendor/lib/b.php": FileRecord("vendor/lib/b.php", 0, 0),
    "node_modules/react/index.js": FileRecord("node_modules/react/index.js", 0, 0),
    "app/service.php": FileRecord("app/service.php", 2, 5),
}
```

| Test name | What it checks |
|-----------|----------------|
| `test_returns_analysis_result` | `analyze()` returns `AnalysisResult` |
| `test_analyzer_name` | `result.analyzer_name == "vendor_analyzer"` |
| `test_detects_vendor_root` | `"vendor"` appears in `metadata["vendor_roots"]` |
| `test_detects_node_modules` | `"node_modules"` appears in `metadata["vendor_roots"]` |
| `test_vendor_file_count` | `vendor` root has `file_count == 3` |
| `test_non_vendor_not_detected` | `"app"` is NOT in `metadata["vendor_roots"]` |
| `test_one_action_per_vendor_root` | 2 actions generated (vendor + node_modules) |
| `test_action_type_is_gitignore` | All actions have `ActionType.ADD_GITIGNORE` |
| `test_action_risk_is_low` | All actions have `RiskLevel.LOW` |
| `test_action_reason_contains_count` | `reason` contains the file count |
| `test_no_vendor_no_actions` | Records with no vendor paths → 0 actions |
| `test_nested_vendor` | `"test/vendor/x.php"` detected as vendor under `"test/vendor"` |

---

## Deliverables

1. `analyzers/__init__.py` (empty)
2. `analyzers/vendor_analyzer.py`
3. `tests/test_vendor_analyzer.py`

**Verify:** `pytest tests/test_vendor_analyzer.py -v` must pass with 0 failures.
