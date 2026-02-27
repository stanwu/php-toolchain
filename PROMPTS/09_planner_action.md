# Prompt 09 — planners/action_planner.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ (01–03) + all analyzers (04–08) complete

---

## Task

Implement `planners/action_planner.py`.

This module **aggregates** the `AnalysisResult` from all five analyzers into a
single, ordered `ActionPlan`. It applies global deduplication and risk-aware
sorting so the executor can process actions safely.

---

## Implementation Requirements

```python
from datetime import datetime, timezone
from core.models import AnalysisResult, ActionPlan, Action, RiskLevel, ActionType

RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}

class ActionPlanner:
    def __init__(
        self,
        results: list[AnalysisResult],
        project_dir: str
    ) -> None: ...

    def build_plan(self) -> ActionPlan:
        """
        1. Collect all actions from all AnalysisResults.
        2. Deduplicate: if two actions have the same (action_type, source),
           keep the one with the LOWER risk level (more conservative).
        3. Sort: PRIMARY by risk level ascending (LOW first),
                 SECONDARY by action_type (ADD_GITIGNORE → DELETE → MOVE → REPORT_ONLY),
                 TERTIARY by source path alphabetically.
        4. Set ActionPlan.created_at = ISO 8601 UTC timestamp.
        5. Set ActionPlan.project_dir = project_dir.
        6. Return the ActionPlan.
        """

    def _deduplicate(self, actions: list[Action]) -> list[Action]:
        """Remove duplicate (action_type, source) pairs, keeping lowest risk."""

    def _sort_key(self, action: Action) -> tuple:
        """Return a tuple used for sorting."""

    def summary(self, plan: ActionPlan) -> dict:
        """
        Return a summary dict:
        {
          "total": N,
          "by_risk": {"LOW": N, "MEDIUM": N, "HIGH": N},
          "by_type": {"DELETE": N, "ADD_GITIGNORE": N, ...}
        }
        """
```

### Action type sort order

```
ADD_GITIGNORE = 0   (safest, do first)
DELETE        = 1
MOVE          = 2
REPORT_ONLY   = 3   (no-op, do last)
```

---

## Tests — tests/test_action_planner.py

```python
from core.models import AnalysisResult, Action, ActionType, RiskLevel

def make_action(atype, source, risk, dest=None):
    return Action(atype, source, dest, risk, f"reason for {source}")

# Simulate outputs from multiple analyzers
vendor_result = AnalysisResult("vendor_analyzer", [
    make_action(ActionType.ADD_GITIGNORE, "vendor", RiskLevel.LOW),
], {})

backup_result = AnalysisResult("backup_analyzer", [
    make_action(ActionType.DELETE, "backup_old.php", RiskLevel.LOW),
    make_action(ActionType.DELETE, "config-20230816.php", RiskLevel.MEDIUM),
], {})

duplicate_result = AnalysisResult("duplicate_analyzer", [
    make_action(ActionType.DELETE, "utils_copy.php", RiskLevel.MEDIUM),
    # Duplicate of backup_old.php — should be deduplicated (keep LOW)
    make_action(ActionType.DELETE, "backup_old.php", RiskLevel.HIGH),
], {})

complexity_result = AnalysisResult("complexity_analyzer", [
    make_action(ActionType.REPORT_ONLY, "saas/service.php", RiskLevel.HIGH),
], {})
```

| Test name | What it checks |
|-----------|----------------|
| `test_returns_action_plan` | `build_plan()` returns `ActionPlan` |
| `test_plan_has_project_dir` | `plan.project_dir` set correctly |
| `test_plan_has_created_at` | `plan.created_at` is a non-empty ISO string |
| `test_dedup_keeps_lower_risk` | `backup_old.php` appears once with LOW risk |
| `test_dedup_unique_sources_kept` | All other unique sources present |
| `test_sort_gitignore_first` | ADD_GITIGNORE action is first in plan |
| `test_sort_report_only_last` | REPORT_ONLY action is last |
| `test_sort_low_before_medium` | LOW risk DELETE before MEDIUM risk DELETE |
| `test_summary_total` | `summary()["total"]` == correct count |
| `test_summary_by_risk` | `by_risk` counts are correct |
| `test_summary_by_type` | `by_type` counts are correct |
| `test_empty_results` | No analyzer results → empty plan (0 actions) |

---

## Deliverables

1. `planners/__init__.py` (empty)
2. `planners/action_planner.py`
3. `tests/test_action_planner.py`

**Verify:** `pytest tests/test_action_planner.py -v` must pass with 0 failures.
