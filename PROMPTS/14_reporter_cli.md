# Prompt 14 — reporters/cli_reporter.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ (01–03)

---

## Task

Implement `reporters/cli_reporter.py` using the `rich` library to produce
coloured, structured terminal output across all phases of the tool.

---

## Implementation Requirements

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.text import Text
from core.models import ActionPlan, AnalysisResult, Action, RiskLevel, ActionType, BackupInfo

console = Console()

class CLIReporter:

    def print_summary(self, plan: ActionPlan) -> None:
        """
        Print a summary panel:
        ┌─ Cleanup Plan ──────────────────────────────┐
        │  Total actions : 42                          │
        │  LOW risk      : 18  (auto-execute)          │
        │  MEDIUM risk   :  8  (batch confirm)         │
        │  HIGH risk     : 16  (manual per-action)     │
        └──────────────────────────────────────────────┘
        """

    def print_action_table(
        self,
        plan: ActionPlan,
        max_rows: int = 50
    ) -> None:
        """
        Rich Table with columns:
          # | Type | Source | Risk | Reason
        Colour-code Risk column: LOW=green, MEDIUM=yellow, HIGH=red
        If plan has more than max_rows actions, show first max_rows
        and print "... and N more actions (use --all to show all)"
        """

    def print_analyzer_results(
        self,
        results: list[AnalysisResult]
    ) -> None:
        """
        For each AnalysisResult, print:
          [analyzer_name] → N actions found
        with a summary of metadata highlights (vendor %, wasted bytes, etc.)
        """

    def print_execution_log(self, backup_info: BackupInfo) -> None:
        """
        Print post-execution summary:
          Executed  : N actions
          Skipped   : N actions
          Errors    : N actions
          Backup at : ~/.php-cleanup-backup/{timestamp}/
        """

    def progress_bar(self, total: int, description: str) -> Progress:
        """
        Return a configured rich Progress object for use as a context manager.
        Include SpinnerColumn, TextColumn(description), BarColumn.
        """

    def print_conflict_report(self, conflicts: list[dict]) -> None:
        """
        If conflicts exist, print a warning panel listing each conflict.
        If no conflicts, print "✓ No conflicts detected."
        """
```

### Colour scheme

| Risk Level | Colour |
|------------|--------|
| LOW | `green` |
| MEDIUM | `yellow` |
| HIGH | `red bold` |

| Action Type | Icon |
|-------------|------|
| DELETE | `🗑` |
| MOVE | `→` |
| ADD_GITIGNORE | `📝` |
| REPORT_ONLY | `📊` |

---

## Tests — tests/test_cli_reporter.py

Use `rich.console.Console(file=io.StringIO())` to capture output without printing to terminal.

```python
import io
from rich.console import Console
from core.models import ActionPlan, Action, ActionType, RiskLevel, BackupInfo, AnalysisResult

def make_console():
    buf = io.StringIO()
    return Console(file=buf, highlight=False, markup=False), buf
```

| Test name | What it checks |
|-----------|----------------|
| `test_print_summary_shows_total` | Output contains total action count |
| `test_print_summary_shows_risk_counts` | LOW/MEDIUM/HIGH counts in output |
| `test_print_action_table_headers` | "Type", "Source", "Risk" appear in output |
| `test_print_action_table_truncation` | More than max_rows → "... and N more" in output |
| `test_print_action_table_no_truncation` | Exactly max_rows actions → no truncation message |
| `test_print_analyzer_results_name` | Analyzer name appears in output |
| `test_print_analyzer_results_count` | Action count appears in output |
| `test_print_execution_log_backup_path` | Backup dir path appears in output |
| `test_print_conflict_report_with_conflicts` | Conflict type/source in output |
| `test_print_conflict_report_no_conflicts` | "No conflicts detected" in output |
| `test_progress_bar_returns_progress` | Returns `rich.progress.Progress` instance |

---

## Deliverables

1. `reporters/__init__.py` (empty)
2. `reporters/cli_reporter.py`
3. `tests/test_cli_reporter.py`

**Verify:** `pytest tests/test_cli_reporter.py -v` must pass with 0 failures.
