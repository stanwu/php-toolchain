import collections
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from core.models import (Action, ActionPlan, ActionType, AnalysisResult,
                         RiskLevel)

# The prompt for this step implies BackupInfo exists in core.models,
# so we type hint with 'Any' and use getattr for safety.
# from core.models import BackupInfo

console = Console()


class CLIReporter:
    RISK_STYLES = {
        RiskLevel.LOW: "green",
        RiskLevel.MEDIUM: "yellow",
        RiskLevel.HIGH: "red bold",
    }

    ACTION_ICONS = {
        ActionType.DELETE: "🗑",
        ActionType.MOVE: "→",
        ActionType.ADD_GITIGNORE: "📝",
        ActionType.REPORT_ONLY: "📊",
    }

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
        risk_counts = collections.Counter(a.risk_level for a in plan.actions)

        summary_text = Text()
        summary_text.append(f" Total actions : {len(plan.actions):<2}\n")
        summary_text.append(
            f" LOW risk      : {risk_counts[RiskLevel.LOW]:<2}  (auto-execute)\n",
            style=self.RISK_STYLES[RiskLevel.LOW],
        )
        summary_text.append(
            f" MEDIUM risk   : {risk_counts[RiskLevel.MEDIUM]:<2}  (batch confirm)\n",
            style=self.RISK_STYLES[RiskLevel.MEDIUM],
        )
        summary_text.append(
            f" HIGH risk     : {risk_counts[RiskLevel.HIGH]:<2}  (manual per-action)",
            style=self.RISK_STYLES[RiskLevel.HIGH],
        )

        console.print(Panel(summary_text, title="Cleanup Plan", expand=False))

    def print_action_table(self, plan: ActionPlan, max_rows: int = 50) -> None:
        """
        Rich Table with columns:
          # | Type | Source | Risk | Reason
        Colour-code Risk column: LOW=green, MEDIUM=yellow, HIGH=red
        If plan has more than max_rows actions, show first max_rows
        and print "... and N more actions (use --all to show all)"
        """
        table = Table()
        table.add_column("#", justify="right", style="dim")
        table.add_column("Type", justify="center")
        table.add_column("Source", style="cyan")
        table.add_column("Risk")
        table.add_column("Reason")

        actions_to_show = plan.actions
        truncated = False
        if len(plan.actions) > max_rows:
            actions_to_show = plan.actions[:max_rows]
            truncated = True

        for i, action in enumerate(actions_to_show, 1):
            icon = self.ACTION_ICONS.get(action.action_type, "?")
            risk_style = self.RISK_STYLES.get(action.risk_level, "default")

            destination = f" → {action.destination}" if action.destination else ""
            source_text = f"{action.source}{destination}"

            table.add_row(
                str(i),
                icon,
                source_text,
                Text(action.risk_level.name, style=risk_style),
                action.reason,
            )

        console.print(table)

        if truncated:
            remaining = len(plan.actions) - max_rows
            console.print(f"... and {remaining} more actions (use --all to show all)")

    def print_analyzer_results(self, results: list[AnalysisResult]) -> None:
        """
        For each AnalysisResult, print:
          [analyzer_name] → N actions found
        with a summary of metadata highlights (vendor %, wasted bytes, etc.)
        """
        for result in results:
            metadata_summary = ""
            if result.metadata:
                parts = []
                if "vendor_percentage" in result.metadata:
                    parts.append(
                        f"{result.metadata['vendor_percentage']:.1f}% vendor code"
                    )
                if "wasted_bytes" in result.metadata:
                    parts.append(f"{result.metadata['wasted_bytes'] // 1024} KB wasted")
                if "duplicate_sets" in result.metadata:
                    parts.append(f"{result.metadata['duplicate_sets']} duplicate sets")
                if "backup_files_found" in result.metadata:
                    parts.append(
                        f"{result.metadata['backup_files_found']} backup files"
                    )
                if "complex_files" in result.metadata:
                    parts.append(f"{result.metadata['complex_files']} complex files")
                if "structure_issues" in result.metadata:
                    parts.append(
                        f"{result.metadata['structure_issues']} structure issues"
                    )

                if parts:
                    metadata_summary = f" ({', '.join(parts)})"

            console.print(
                f"[bold blue]{result.analyzer_name}[/bold blue] → {len(result.actions)} actions found{metadata_summary}"
            )

    def print_execution_log(self, backup_info: Any) -> None:
        """
        Print post-execution summary:
          Executed  : N actions
          Skipped   : N actions
          Errors    : N actions
          Backup at : ~/.php-cleanup-backup/{timestamp}/
        """
        summary_text = (
            f" Executed  : {getattr(backup_info, 'executed_count', 'N/A')}\n"
            f" Skipped   : {getattr(backup_info, 'skipped_count', 'N/A')}\n"
            f" Errors    : {getattr(backup_info, 'error_count', 'N/A')}\n"
            f" Backup at : {getattr(backup_info, 'backup_path', 'N/A')}"
        )
        console.print(Panel(summary_text, title="Execution Summary", expand=False))

    def progress_bar(self, total: int, description: str) -> Progress:
        """
        Return a configured rich Progress object for use as a context manager.
        Include SpinnerColumn, TextColumn(description), BarColumn.
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        )

    def print_conflict_report(self, conflicts: list[dict]) -> None:
        """
        If conflicts exist, print a warning panel listing each conflict.
        If no conflicts, print "✓ No conflicts detected."
        """
        if not conflicts:
            console.print("✓ No conflicts detected.", style="green")
            return

        text = Text()
        for conflict in conflicts:
            text.append(
                f"• {conflict.get('type')}: {conflict.get('source')}\n  Reason: {conflict.get('reason')}\n"
            )

        console.print(
            Panel(
                text,
                title="[yellow]Conflict Report[/yellow]",
                border_style="yellow",
                expand=False,
            )
        )
