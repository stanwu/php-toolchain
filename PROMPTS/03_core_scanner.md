# Prompt 03 — core/scanner.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** `core/models.py` (01), `core/loader.py` (02)

---

## Task

Implement `core/scanner.py` — walks the real project directory on disk,
then cross-validates against the JSON records to identify:
- **Ghost files**: in JSON but missing from disk
- **New files**: on disk but missing from JSON
- **Matched files**: present in both

---

## Implementation Requirements

```python
from pathlib import Path
from dataclasses import dataclass
from core.models import FileRecord

@dataclass
class ScanResult:
    matched: dict[str, FileRecord]   # path → FileRecord (exists_on_disk=True)
    ghost: list[str]                 # paths in JSON, not on disk
    new_files: list[str]             # paths on disk, not in JSON

class DirectoryScanner:
    def __init__(self, project_dir: Path) -> None: ...

    def scan(self) -> set[str]:
        """
        Recursively walk project_dir.
        Return a set of relative path strings (forward-slash separated,
        relative to project_dir) for every file found.
        Skips hidden directories (starting with '.') and symlinks.
        """

    def cross_validate(
        self,
        json_records: dict[str, FileRecord]
    ) -> ScanResult:
        """
        Compare disk files (from scan()) against json_records.
        - Sets FileRecord.exists_on_disk = True for matched files.
        - Builds ghost and new_files lists.
        Returns a ScanResult.
        """
```

### Path normalization

- Always use forward slashes in relative paths, even on Windows
- Strip any leading `./` before comparison
- Comparison is case-sensitive (Linux/macOS default)

### Logging

- `INFO`: count of matched / ghost / new files after cross_validate()
- `WARNING`: if ghost list is non-empty (files in JSON missing from disk)

---

## Tests — tests/test_scanner.py

Use `tmp_path` (pytest built-in) to create a temporary directory tree.

**Fixture setup in conftest.py or test file:**

```python
# tests/fixtures/project_tree layout to create in tmp_path:
# index.php
# vendor/autoload.php
# vendor/lib/helper.php
# saas/service.php
# backup_old.php
# utils_copy.php
# .git/config          ← should be skipped (hidden dir)
```

| Test name | What it checks |
|-----------|----------------|
| `test_scan_finds_all_files` | `scan()` returns 6 paths (excludes `.git/config`) |
| `test_scan_no_leading_slash` | No path in result starts with `/` or `./` |
| `test_scan_forward_slash` | Paths use `/` not `\\` |
| `test_scan_skips_hidden_dirs` | `.git/config` not in result |
| `test_scan_skips_symlinks` | Symlink not followed (create one in tmp_path) |
| `test_cross_validate_matched` | All 6 mini_report files matched when disk mirrors JSON |
| `test_cross_validate_ghost` | Remove `backup_old.php` from disk → appears in `ghost` |
| `test_cross_validate_new` | Add `extra.php` to disk → appears in `new_files` |
| `test_cross_validate_exists_on_disk` | Matched FileRecord has `exists_on_disk=True` |
| `test_cross_validate_empty_dir` | Empty project dir → 6 ghosts, 0 matched |
| `test_cross_validate_empty_json` | No JSON records → all disk files in new_files |

---

## Deliverables

1. `core/scanner.py`
2. `tests/test_scanner.py`

**Verify:** `pytest tests/test_scanner.py -v` must pass with 0 failures.
