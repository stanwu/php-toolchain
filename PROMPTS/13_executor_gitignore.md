# Prompt 13 — executors/gitignore_gen.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ (01–03)

---

## Task

Implement `executors/gitignore_gen.py` — reads the existing `.gitignore`
(if any), merges in new entries from `ADD_GITIGNORE` actions, and outputs
a **unified diff** for review before writing.

---

## Implementation Requirements

```python
from pathlib import Path
from core.models import Action, ActionType
import difflib
import logging

logger = logging.getLogger(__name__)

class GitignoreGen:
    def __init__(self, project_dir: Path) -> None:
        self.gitignore_path = project_dir / ".gitignore"

    def read_existing(self) -> list[str]:
        """
        Read existing .gitignore lines.
        Return [] if file does not exist.
        Preserve exact content (including blank lines and comments).
        """

    def generate_new_entries(self, actions: list[Action]) -> list[str]:
        """
        From actions of type ADD_GITIGNORE, extract source paths.
        Return a list of new .gitignore lines to add:
        - Each entry is: /{source}/\n  (rooted, trailing slash for dirs)
        - Skip entries that already exist in the current .gitignore
        - Sort entries alphabetically
        """

    def build_updated_content(self, new_entries: list[str]) -> str:
        """
        Append new entries to existing content.
        If existing file is non-empty and doesn't end with newline, add one.
        Prepend a comment block before the new entries:
          # Added by php-cleanup-toolkit {timestamp}
        Return the full updated file content as a string.
        """

    def diff(self, new_content: str) -> str:
        """
        Generate unified diff between existing and new content.
        Use difflib.unified_diff with:
          fromfile=".gitignore (current)"
          tofile=".gitignore (proposed)"
        Return the diff as a string (empty string if no changes).
        """

    def write(self, new_content: str) -> None:
        """Write new_content to .gitignore. Log path at INFO level."""

    def apply(self, actions: list[Action], dry_run: bool = True) -> str:
        """
        High-level method:
        1. Filter actions to ADD_GITIGNORE only.
        2. Generate new entries.
        3. Build updated content.
        4. If dry_run: return diff string, do not write.
        5. If not dry_run: write and return diff string.
        """
```

### Entry format examples

```
# Before (existing .gitignore):
.env
*.log

# New entries added:
# Added by php-cleanup-toolkit 2026-02-26T10:00:00Z
/vendor/
/node_modules/
```

---

## Tests — tests/test_gitignore_gen.py

Use `tmp_path` for all file operations.

```python
from core.models import Action, ActionType, RiskLevel

def make_gitignore_action(source):
    return Action(ActionType.ADD_GITIGNORE, source, None, RiskLevel.LOW, "test")
```

| Test name | What it checks |
|-----------|----------------|
| `test_read_existing_returns_lines` | Reads existing file correctly |
| `test_read_existing_no_file_returns_empty` | Returns `[]` when no `.gitignore` |
| `test_generate_new_entries_format` | `"/vendor/\n"` in new entries for source `"vendor"` |
| `test_generate_skips_existing_entries` | Entry already in `.gitignore` not duplicated |
| `test_generate_sorted` | New entries sorted alphabetically |
| `test_generate_only_gitignore_actions` | Non-ADD_GITIGNORE actions ignored |
| `test_build_adds_comment` | `"# Added by php-cleanup-toolkit"` in updated content |
| `test_build_preserves_existing` | Existing lines still present in output |
| `test_build_newline_before_additions` | Blank line separates old and new content |
| `test_diff_shows_added_lines` | `+/vendor/` in diff output |
| `test_diff_empty_if_no_changes` | Empty string when nothing to add |
| `test_apply_dry_run_no_write` | `dry_run=True` → file not modified |
| `test_apply_writes_file` | `dry_run=False` → file updated on disk |
| `test_apply_returns_diff_string` | `apply()` always returns a string |

---

## Deliverables

1. `executors/gitignore_gen.py`
2. `tests/test_gitignore_gen.py`

**Verify:** `pytest tests/test_gitignore_gen.py -v` must pass with 0 failures.
