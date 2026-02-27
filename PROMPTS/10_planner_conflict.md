# Prompt 10 — planners/conflict_resolver.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ (01–03), planners/action_planner.py (09)

---

## Task

Implement `planners/conflict_resolver.py`.

Before handing the plan to the executor, this module checks for **dependency
conflicts** between actions — cases where two actions target the same file
in incompatible ways — and resolves or escalates them.

---

## Conflict Types

| Conflict | Example | Resolution |
|----------|---------|------------|
| **DELETE + MOVE same source** | Action A deletes `utils.php`, Action B moves `utils.php` | Remove DELETE, keep MOVE; mark MOVE as `conflict=True`, upgrade to HIGH risk |
| **Two MOVEs same source** | Both want to move `foo.php` to different destinations | Keep first (lower risk), remove second; log WARNING |
| **DELETE after ADD_GITIGNORE on same dir** | Delete a vendor file AND add it to .gitignore | Remove DELETE (redundant); .gitignore is sufficient |
| **MOVE target = another file's source** | Move A→B, and B is also being moved B→C | Reorder: process B→C first, then A→B |

---

## Implementation Requirements

```python
from core.models import ActionPlan, Action, ActionType, RiskLevel
import logging

logger = logging.getLogger(__name__)

class ConflictResolver:
    def __init__(self, plan: ActionPlan) -> None: ...

    def resolve(self) -> ActionPlan:
        """
        Run all conflict checks in order and return a clean ActionPlan.
        Sets action.conflict = True on any action that was involved in a conflict.
        Logs each resolved conflict at WARNING level.
        """

    def _find_delete_move_conflicts(
        self, actions: list[Action]
    ) -> list[Action]:
        """Resolve DELETE+MOVE conflicts on the same source."""

    def _find_duplicate_move_conflicts(
        self, actions: list[Action]
    ) -> list[Action]:
        """Resolve two MOVEs on the same source."""

    def _find_redundant_deletes_in_gitignore_dirs(
        self, actions: list[Action]
    ) -> list[Action]:
        """
        If ADD_GITIGNORE action exists for dir X,
        remove any DELETE actions for files under X/.
        """

    def _reorder_move_chain(
        self, actions: list[Action]
    ) -> list[Action]:
        """Topological sort so move dependencies execute in correct order."""

    def conflict_report(self) -> list[dict]:
        """
        Return list of {type, source, resolution, actions_involved}
        for every conflict that was detected (even if auto-resolved).
        """
```

---

## Tests — tests/test_conflict_resolver.py

```python
from core.models import ActionPlan, Action, ActionType, RiskLevel

def make_action(atype, source, risk=RiskLevel.LOW, dest=None, reason="r"):
    return Action(atype, source, dest, risk, reason)

# Helper
def make_plan(*actions):
    return ActionPlan(actions=list(actions))
```

| Test name | What it checks |
|-----------|----------------|
| `test_no_conflicts_unchanged` | Clean plan returned as-is (same action count) |
| `test_delete_move_conflict_removes_delete` | DELETE removed, MOVE kept |
| `test_delete_move_conflict_marks_move` | Kept MOVE has `conflict=True` |
| `test_delete_move_conflict_upgrades_risk` | MOVE risk upgraded to HIGH |
| `test_duplicate_move_keeps_first` | First MOVE kept, second removed |
| `test_redundant_delete_under_gitignore_removed` | DELETE `vendor/x.php` removed when `vendor` is gitignored |
| `test_delete_outside_gitignore_dir_kept` | DELETE for `app/x.php` not removed when `vendor` is gitignored |
| `test_move_chain_reordered` | B→C before A→B in final plan |
| `test_conflict_report_populated` | `conflict_report()` returns one entry per conflict |
| `test_conflict_report_empty_if_clean` | `conflict_report()` returns [] for clean plan |
| `test_returns_action_plan` | Returns `ActionPlan` instance |

---

## Deliverables

1. `planners/conflict_resolver.py`
2. `tests/test_conflict_resolver.py`

**Verify:** `pytest tests/test_conflict_resolver.py -v` must pass with 0 failures.
