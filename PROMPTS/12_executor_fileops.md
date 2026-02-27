# Prompt 12 — executors/file_ops.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ (01–03), executors/safe_executor.py (11)

---

## Task

Implement `executors/file_ops.py` — the **actual file system operations**
invoked by `safe_executor`. Every operation must be logged and support rollback
via the pre-execution hard-link backup.

---

## Implementation Requirements

```python
from pathlib import Path
from core.models import Action, ActionType
import logging
import shutil
import json

logger = logging.getLogger(__name__)

class FileOps:
    def __init__(
        self,
        project_dir: Path,
        backup_dir: Path
    ) -> None: ...

    def _safe_resolve(self, relative: str) -> Path:
        """
        Resolve a relative path against project_dir and verify it stays
        within project_dir (prevents path traversal).
        Raises ValueError if the resolved path escapes project_dir.
        Example: "../../../etc/passwd" → raises ValueError.
        """
        resolved = (self.project_dir / relative).resolve()
        if not resolved.is_relative_to(self.project_dir.resolve()):
            raise ValueError(
                f"Path traversal detected: '{relative}' resolves outside project_dir"
            )
        return resolved

    def delete(self, action: Action) -> dict:
        """
        1. Call _safe_resolve(action.source) — raises ValueError on traversal attempt
        2. Verify file exists; if not, return {status: "skipped", reason: "not found"}
        3. Hard-link the file to backup_dir / action.source (preserve directory structure)
        4. Delete the original file
        5. If the parent directory is now empty, remove it
        6. Return {status: "ok", backup_path: str}
        """

    def move(self, action: Action) -> dict:
        """
        1. Call _safe_resolve(action.source) for src
        2. Call _safe_resolve(action.destination) for dst
        3. Verify src exists
        4. Hard-link src to backup_dir (before move)
        5. Create dst parent directories if needed
        6. Move src → dst (fail if dst already exists unless dst == src)
        7. Return {status: "ok", backup_path: str}
        """

    def rollback(self, backup_dir: Path, action_log: list[dict]) -> int:
        """
        Restore files from backup using action_log in REVERSE order.
        For each log entry where status == "ok":
          - Copy backup_path back to original location
        Return count of files restored.
        """

    def _backup_path_for(self, source: str) -> Path:
        """
        Return the path where the backup copy should live:
        backup_dir / source  (preserving directory structure)
        """

    def _hard_link_or_copy(self, src: Path, dst: Path) -> None:
        """
        Try hard link first; fall back to shutil.copy2 if cross-device.
        Create parent dirs for dst if needed.
        """
```

### Error handling

- `ValueError` from `_safe_resolve()` → return `{status: "error", reason: "path traversal blocked"}`
- `PermissionError` during delete → return `{status: "error", reason: "permission denied"}`
- `FileExistsError` during move → return `{status: "error", reason: "destination exists"}`
- Any other OS error → return `{status: "error", reason: str(e)}`
- Never raise — always return the status dict

---

## Tests — tests/test_file_ops.py

All tests use `tmp_path` to create real files. No mocking of OS calls.

```python
# Setup helper
def make_file(tmp_path, rel_path, content="<?php echo 1;"):
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p
```

| Test name | What it checks |
|-----------|----------------|
| `test_delete_removes_file` | File gone after delete() |
| `test_delete_creates_backup` | Backup file exists at expected path |
| `test_delete_returns_ok` | Returns `{status: "ok", backup_path: ...}` |
| `test_delete_nonexistent_returns_skipped` | Missing file → `{status: "skipped"}` |
| `test_delete_removes_empty_parent` | Empty dir removed after last file deleted |
| `test_delete_keeps_nonempty_parent` | Dir with other files NOT removed |
| `test_move_moves_file` | File at destination after move() |
| `test_move_src_gone` | Source path gone after move() |
| `test_move_creates_parent_dirs` | Deep destination dirs created |
| `test_move_creates_backup` | Backup of source created before move |
| `test_move_returns_ok` | Returns `{status: "ok"}` |
| `test_move_fails_if_dest_exists` | Returns `{status: "error"}` if dst exists |
| `test_rollback_restores_deleted_file` | Deleted file restored by rollback() |
| `test_rollback_count` | Returns correct count of restored files |
| `test_rollback_skips_non_ok_entries` | Skipped/error entries not rolled back |
| `test_rollback_reverse_order` | Rollback processes log in reverse order |
| `test_delete_traversal_blocked` | `action.source = "../../etc/passwd"` → `{status: "error", reason contains "traversal"}` |
| `test_move_src_traversal_blocked` | `action.source = "../outside.php"` → `{status: "error"}` |
| `test_move_dst_traversal_blocked` | `action.destination = "../outside.php"` → `{status: "error"}` |
| `test_safe_resolve_valid_path` | `_safe_resolve("subdir/file.php")` returns path inside project_dir |
| `test_safe_resolve_raises_on_escape` | `_safe_resolve("../../etc/passwd")` raises `ValueError` |

---

## Deliverables

1. `executors/file_ops.py`
2. `tests/test_file_ops.py`

**Verify:** `pytest tests/test_file_ops.py -v` must pass with 0 failures.
