import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from core.models import Action, ActionPlan, ActionType, AnalysisResult, BackupInfo, RiskLevel

logger = logging.getLogger(__name__)

console = Console()

_RISK_STYLE: dict[RiskLevel, str] = {
    RiskLevel.LOW: "green",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.HIGH: "red bold",
}

_ACTION_ICON: dict[ActionType, str] = {
    ActionType.DELETE: "🗑",
    ActionType.MOVE: "→",
    ActionType.ADD_GITIGNORE: "📝",
    ActionType.REPORT_ONLY: "📊",
}


class CLIReporter:

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def print_summary(self, plan: ActionPlan) -> None:
        """Print a summary panel showing total and per-risk action counts."""
        total = len(plan.actions)
        low = sum(1 for a in plan.actions if a.risk_level == RiskLevel.LOW)
        medium = sum(1 for a in plan.actions if a.risk_level == RiskLevel.MEDIUM)
        high = sum(1 for a in plan.actions if a.risk_level == RiskLevel.HIGH)

        lines = [
            f"  Total actions : {total}",
            f"  LOW risk      : {low:>3}  (auto-execute)",
            f"  MEDIUM risk   : {medium:>3}  (batch confirm)",
            f"  HIGH risk     : {high:>3}  (manual per-action)",
        ]
        content = "\n".join(lines)
        self.console.print(Panel(content, title="Cleanup Plan", expand=False))

    def print_action_table(
        self,
        plan: ActionPlan,
        max_rows: int = 50,
    ) -> None:
        """Print a Rich Table of actions, truncating at max_rows."""
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim", justify="right")
        table.add_column("Type")
        table.add_column("Source")
        table.add_column("Risk")
        table.add_column("Reason")

        actions = plan.actions
        visible = actions[:max_rows]

        for idx, action in enumerate(visible, start=1):
            icon = _ACTION_ICON.get(action.action_type, "?")
            type_label = f"{icon} {action.action_type.value}"
            risk_style = _RISK_STYLE.get(action.risk_level, "")
            risk_text = Text(action.risk_level.value, style=risk_style)
            table.add_row(
                str(idx),
                type_label,
                action.source,
                risk_text,
                action.reason,
            )

        self.console.print(table)

        overflow = len(actions) - max_rows
        if overflow > 0:
            self.console.print(
                f"... and {overflow} more actions (use --all to show all)"
            )

    def print_analyzer_results(self, results: list[AnalysisResult]) -> None:
        """Print a one-line summary per analyzer with metadata highlights."""
        for result in results:
            count = len(result.actions)
            self.console.print(
                f"[{result.analyzer_name}] → {count} action{'s' if count != 1 else ''} found"
            )
            for key, value in result.metadata.items():
                self.console.print(f"    {key}: {value}")

    def print_execution_log(self, backup_info: BackupInfo) -> None:
        """Print post-execution summary derived from backup_info."""
        executed = sum(
            1 for entry in backup_info.action_log if entry.get("backup_path")
        )
        skipped = sum(
            1 for entry in backup_info.action_log if not entry.get("backup_path")
        )
        errors = 0  # BackupInfo doesn't track errors; caller may extend if needed

        lines = [
            f"  Executed  : {executed} actions",
            f"  Skipped   : {skipped} actions",
            f"  Errors    : {errors} actions",
            f"  Backup at : {backup_info.backup_dir}",
        ]
        content = "\n".join(lines)
        self.console.print(Panel(content, title="Execution Log", expand=False))

    def progress_bar(self, total: int, description: str) -> Progress:
        """Return a configured rich Progress object for use as a context manager."""
        return Progress(
            SpinnerColumn(),
            TextColumn(description),
            BarColumn(),
            console=self.console,
        )

    def print_conflict_report(self, conflicts: list[dict]) -> None:
        """Print a warning panel listing conflicts, or a success message."""
        if not conflicts:
            self.console.print("✓ No conflicts detected.")
            return

        lines = []
        for conflict in conflicts:
            ctype = conflict.get("type", "unknown")
            source = conflict.get("source", "unknown")
            lines.append(f"  [{ctype}] {source}")

        content = "\n".join(lines)
        self.console.print(
            Panel(content, title="⚠ Conflicts Detected", border_style="yellow", expand=False)
        )
