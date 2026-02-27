# Prompt 11 — executors/safe_executor.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ (01–03), planners/ (09–10)

---

## Task

Implement `executors/safe_executor.py` — the **safety gateway** for all
file system operations.

This is the most critical module. It enforces:
- Dry-run mode (default ON — never touches files unless `--execute` is passed)
- Risk-level gating (LOW auto, MEDIUM batch-confirm, HIGH one-by-one confirm)
- Pre-execution backup via hard links
- Structured execution log

---

## Implementation Requirements

```python
from pathlib import Path
from datetime import datetime, timezone
from core.models import ActionPlan, Action, RiskLevel, BackupInfo
import logging

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path.home() / ".php-cleanup-backup"

class SafeExecutor:
    def __init__(
        self,
        plan: ActionPlan,
        project_dir: Path,
        dry_run: bool = True,               # default: simulate only
        confirm_fn: Optional[Callable] = None  # injected for testing
    ) -> None: ...

    def execute(self) -> BackupInfo:
        """
        Main entry point.
        1. If dry_run: log every action as "[DRY-RUN]" and return a BackupInfo
           with empty action_log. Never call file_ops.
        2. If not dry_run:
           a. Create backup directory: BACKUP_ROOT / {timestamp}/
           b. For each action, gate by risk level:
              - LOW:    execute immediately
              - MEDIUM: ask confirm_fn("Proceed with batch of N MEDIUM actions? [y/N]")
              - HIGH:   ask confirm_fn per action ("Delete X? [y/N]")
           c. On confirm=False: skip action, log as SKIPPED
           d. On confirm=True:  call _dispatch(action), log result
        3. Return BackupInfo with complete action_log.
        """

    def _dispatch(self, action: Action, backup_dir: Path) -> dict:
        """
        Route action to correct executor method.
        Returns log entry: {action, status, backup_path, error}
        """

    def _create_backup_dir(self) -> Path:
        """
        Create ~/.php-cleanup-backup/{timestamp}/ and return the path.
        SECURITY: use mode=0o700 so only the current user can read the backup
        (backed-up PHP files may contain database passwords, API keys, etc.).
        """

    def _gate_medium(self, actions: list[Action]) -> bool:
        """Call confirm_fn with a batch prompt. Return True to proceed."""

    def _gate_high(self, action: Action) -> bool:
        """Call confirm_fn with a per-action prompt. Return True to proceed."""
```

### confirm_fn contract

```python
# Signature: confirm_fn(prompt: str) -> bool
# In production: prompts the user via rich.prompt.Confirm
# In tests: injected as a lambda / mock
```

### Dry-run output format (via logging.INFO)

```
[DRY-RUN] DELETE  backup_old.php           (LOW)    — explicit backup suffix
[DRY-RUN] ADD_GITIGNORE  vendor            (LOW)    — vendor/ contains 12043 files
[DRY-RUN] REPORT_ONLY  saas/service.php   (HIGH)   — Complexity score 115
```

---

## Tests — tests/test_safe_executor.py

Use `tmp_path` and monkeypatch `confirm_fn`.

```python
from core.models import ActionPlan, Action, ActionType, RiskLevel

def make_plan(*actions):
    return ActionPlan(actions=list(actions))

def low_delete(src="old.php"):
    return Action(ActionType.DELETE, src, None, RiskLevel.LOW, "test")

def medium_delete(src="med.php"):
    return Action(ActionType.DELETE, src, None, RiskLevel.MEDIUM, "test")

def high_delete(src="hi.php"):
    return Action(ActionType.DELETE, src, None, RiskLevel.HIGH, "test")
```

| Test name | What it checks |
|-----------|----------------|
| `test_dry_run_returns_backup_info` | Returns `BackupInfo` |
| `test_dry_run_empty_action_log` | `backup_info.action_log` is empty |
| `test_dry_run_no_file_touched` | File exists before and after dry-run |
| `test_dry_run_true_by_default` | `SafeExecutor(plan, dir)` → dry_run=True |
| `test_execute_low_no_confirm_needed` | LOW action executes without calling confirm_fn |
| `test_execute_medium_calls_confirm_once` | confirm_fn called once for all MEDIUM actions |
| `test_execute_medium_skipped_on_deny` | confirm_fn returns False → action skipped |
| `test_execute_high_calls_confirm_per_action` | 3 HIGH actions → confirm_fn called 3 times |
| `test_execute_high_skipped_on_deny` | Per-action denial → that action skipped |
| `test_action_log_has_status` | Each log entry has "status" key (executed/skipped/dry-run) |
| `test_backup_dir_created` | `~/.php-cleanup-backup/{ts}/` created on real execute |
| `test_backup_dir_not_created_in_dry_run` | No backup dir in dry-run mode |
| `test_backup_dir_permissions` | Backup dir has mode `0o700` (owner-only access) |

---

## Deliverables

1. `executors/__init__.py` (empty)
2. `executors/safe_executor.py`
3. `tests/test_safe_executor.py`

**Verify:** `pytest tests/test_safe_executor.py -v` must pass with 0 failures.
