# Prompt 01 — core/models.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **No prior modules required.**

---

## Task

Implement `core/models.py` — the **data foundation** for the entire toolkit.
Every other module imports from here; nothing in this file imports from other internal modules.

---

## Implementation Requirements

### 1. All dataclasses from Master Context, plus:

```python
@dataclass
class BranchRecord:
    type: str         # "if", "for", "foreach", etc.
    line: int
    depth: int
    condition: str

@dataclass
class FunctionRecord:
    name: str
    start_line: int
    end_line: int
    total_branches: int
    max_depth: int
    branches: list[BranchRecord]

@dataclass
class BackupInfo:
    """Created by safe_executor before any real action."""
    timestamp: str
    backup_dir: Path
    action_log: list[dict]   # [{"action": Action, "backup_path": str}, ...]
```

### 2. Serialization — every dataclass must implement:

```python
def to_dict(self) -> dict:
    """Return a JSON-serializable dict (Path → str, Enum → .value)."""

@classmethod
def from_dict(cls, d: dict) -> "Self":
    """Reconstruct from dict produced by to_dict()."""
```

### 3. Validation helper:

```python
def validate_action(action: Action) -> list[str]:
    """
    Return a list of error strings.
    Empty list means the action is valid.
    Rules:
    - MOVE must have a non-empty destination
    - DELETE must NOT have a destination
    - reason must be non-empty
    - source must be non-empty
    """
```

### 4. RiskLevel ordering:

`RiskLevel` must support `<` / `<=` comparison (LOW < MEDIUM < HIGH).
Implement `__lt__` or use `@functools.total_ordering`.

---

## Tests — tests/test_models.py

Write `tests/test_models.py`. It must import **only** `core.models`.

| Test name | What it checks |
|-----------|----------------|
| `test_file_record_roundtrip` | `to_dict()` → `from_dict()` preserves all fields |
| `test_action_roundtrip` | Same for Action (including Enum fields) |
| `test_action_plan_roundtrip` | ActionPlan with 2 actions survives roundtrip |
| `test_duplicate_group_roundtrip` | DuplicateGroup roundtrip |
| `test_validate_action_move_no_dest` | MOVE with `destination=None` → returns error |
| `test_validate_action_delete_with_dest` | DELETE with destination set → returns error |
| `test_validate_action_empty_reason` | Empty `reason` → returns error |
| `test_validate_action_valid_delete` | Valid DELETE → empty error list |
| `test_validate_action_valid_move` | Valid MOVE with destination → empty error list |
| `test_risk_level_ordering` | `LOW < MEDIUM < HIGH` evaluates to `True` |
| `test_risk_level_equality` | `LOW == LOW` evaluates to `True` |

---

## Deliverables

1. `core/__init__.py` (empty)
2. `core/models.py` (complete)
3. `tests/__init__.py` (empty)
4. `tests/test_models.py` (all tests above)

**Verify:** `pytest tests/test_models.py -v` must pass with 0 failures.
