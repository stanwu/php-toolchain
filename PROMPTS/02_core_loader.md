# Prompt 02 — core/loader.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** `core/models.py` (Prompt 01 complete)

---

## Task

Implement `core/loader.py` — a **streaming JSON parser** for `analysis_report.json`.
The file can be 32 MB. The `iter_files()` method must never hold more than one
`FileRecord` in memory at a time.

---

## Implementation Requirements

```python
import ijson
import logging
from pathlib import Path
from typing import Iterator, Optional
from core.models import FileRecord

logger = logging.getLogger(__name__)

class ReportLoader:
    def __init__(self, json_path: Path) -> None: ...

    def load_summary(self) -> dict:
        """
        Parse only the top-level "summary" block.
        Returns the raw dict (small, safe to load fully).
        """

    def iter_files(self) -> Iterator[tuple[str, FileRecord]]:
        """
        Stream-parse the "files" object using ijson.
        Yields (relative_path: str, FileRecord) one at a time.
        Only reads max_depth and total_branches per entry —
        branch/function details are intentionally skipped here.
        Logs progress every 1000 files at DEBUG level.
        """

    def load_all(self) -> dict[str, FileRecord]:
        """
        Convenience wrapper: collect iter_files() into a dict.
        Use only for small JSONs or tests.
        """

    def get_file(self, path: str) -> Optional[FileRecord]:
        """
        Linear scan via iter_files() to find a single record.
        Returns None if not found. Intended for testing only.
        """
```

### Error handling

- Missing file → raise `FileNotFoundError` with the path in the message
- Malformed JSON (ijson parse error) → catch and re-raise as `ValueError` with context
- Unknown top-level keys in a file entry are silently ignored (forward-compatible)

### Input validation (security)

After parsing each file entry, validate before constructing `FileRecord`:
- `path` (the JSON key) must not contain `..` segments — raise `ValueError` if it does,
  to prevent path traversal payloads in a tampered `analysis_report.json` from reaching
  the executor layer.
- `max_depth` and `total_branches` must be non-negative integers; if missing or invalid,
  use 0 (already required by logging rule) without propagating bad values.

### Logging

- `DEBUG`: every 1000 files loaded, print count
- `INFO`: total files loaded when `load_all()` finishes
- `WARNING`: if a file entry is missing `max_depth` or `total_branches` (use defaults: 0)

---

## Tests — tests/test_loader.py

Uses `tests/fixtures/mini_report.json` (defined in Master Context).

| Test name | What it checks |
|-----------|----------------|
| `test_load_summary_total_files` | `summary["total_files"] == 6` |
| `test_load_summary_most_complex` | `most_complex` list has 1 entry |
| `test_iter_files_count` | `iter_files()` yields exactly 6 tuples |
| `test_iter_files_keys_are_strings` | All yielded keys are `str` |
| `test_iter_files_fields` | `vendor/autoload.php` has `max_depth=0`, `total_branches=0` |
| `test_iter_files_complex_file` | `saas/service.php` has `max_depth=5`, `total_branches=10` |
| `test_load_all_returns_dict` | `load_all()` returns `dict` with 6 keys |
| `test_load_all_contains_vendor` | `"vendor/autoload.php"` is a key |
| `test_get_file_found` | `get_file("index.php")` returns a `FileRecord` |
| `test_get_file_not_found` | `get_file("nonexistent.php")` returns `None` |
| `test_missing_file_raises` | `ReportLoader(Path("no.json")).load_summary()` raises `FileNotFoundError` |
| `test_iter_does_not_load_all` | Call `iter_files()` and `next()` once; assert `load_all` was never called (use monkeypatch) |
| `test_traversal_path_rejected` | JSON with key `"../../etc/passwd"` → `iter_files()` raises `ValueError` |
| `test_dotdot_in_subpath_rejected` | JSON with key `"a/../b/file.php"` → `iter_files()` raises `ValueError` |

---

## Deliverables

1. `core/loader.py`
2. `tests/fixtures/mini_report.json` (copy from Master Context exactly)
3. `tests/test_loader.py`

**Verify:** `pytest tests/test_loader.py -v` must pass with 0 failures.
