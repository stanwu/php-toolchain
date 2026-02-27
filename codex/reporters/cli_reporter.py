from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from core.models import ActionPlan, ActionType, AnalysisResult, BackupInfo, RiskLevel

console = Console()


def _risk_style(risk: RiskLevel) -> str:
    if risk == RiskLevel.LOW:
        return "green"
    if risk == RiskLevel.MEDIUM:
        return "yellow"
    return "red bold"


def _action_icon(action_type: ActionType) -> str:
    return {
        ActionType.DELETE: "🗑",
        ActionType.MOVE: "→",
        ActionType.ADD_GITIGNORE: "📝",
        ActionType.REPORT_ONLY: "📊",
    }.get(action_type, "?")


class CLIReporter:
    def __init__(self, console_instance: Console | None = None) -> None:
        self.console = console_instance or console

    def print_summary(self, plan: ActionPlan) -> None:
        low = sum(1 for a in plan.actions if a.risk_level == RiskLevel.LOW)
        medium = sum(1 for a in plan.actions if a.risk_level == RiskLevel.MEDIUM)
        high = sum(1 for a in plan.actions if a.risk_level == RiskLevel.HIGH)

        lines = [
            f"Total actions : {len(plan.actions)}",
            f"LOW risk      : {low}  (auto-execute)",
            f"MEDIUM risk   : {medium}  (batch confirm)",
            f"HIGH risk     : {high}  (manual per-action)",
        ]
        self.console.print(Panel("\n".join(lines), title="Cleanup Plan"))

    def print_action_table(self, plan: ActionPlan, max_rows: int = 50) -> None:
        table = Table(title="Actions", show_lines=False)
        table.add_column("#", justify="right", no_wrap=True)
        table.add_column("Type", no_wrap=True)
        table.add_column("Source", overflow="fold")
        table.add_column("Risk", no_wrap=True)
        table.add_column("Reason", overflow="fold")

        actions = plan.actions
        show_actions = actions[:max_rows]
        for idx, action in enumerate(show_actions, start=1):
            action_label = f"{_action_icon(action.action_type)} {action.action_type.value}"
            risk_label = action.risk_level.value
            table.add_row(
                str(idx),
                action_label,
                action.source,
                Text(risk_label, style=_risk_style(action.risk_level)),
                action.reason,
            )

        self.console.print(table)

        if len(actions) > max_rows:
            remaining = len(actions) - max_rows
            self.console.print(f"... and {remaining} more actions (use --all to show all)")

    def print_analyzer_results(self, results: list[AnalysisResult]) -> None:
        if not results:
            self.console.print("No analyzer results.")
            return

        for result in results:
            header = f"{result.analyzer_name} → {len(result.actions)} actions found"
            meta_lines = _format_metadata_highlights(result.metadata)
            body = header if not meta_lines else header + "\n" + "\n".join(meta_lines)
            self.console.print(Panel(body, title="Analyzer Result"))

    def print_execution_log(self, backup_info: BackupInfo) -> None:
        executed, skipped, errors = _count_execution_statuses(backup_info.action_log)
        lines = [
            f"Executed  : {executed}",
            f"Skipped   : {skipped}",
            f"Errors    : {errors}",
            f"Backup at : {backup_info.backup_dir}",
        ]
        self.console.print(Panel("\n".join(lines), title="Execution Summary"))

    def progress_bar(self, total: int, description: str) -> Progress:
        return Progress(
            SpinnerColumn(),
            TextColumn(description),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=self.console,
        )

    def print_conflict_report(self, conflicts: list[dict[str, Any]]) -> None:
        if not conflicts:
            self.console.print("✓ No conflicts detected.")
            return

        items: list[str] = []
        for c in conflicts:
            conflict_type = str(c.get("type", "conflict"))
            source = str(c.get("source", c.get("path", "")))
            detail = str(c.get("detail", c.get("reason", c.get("message", ""))))
            if source and detail:
                items.append(f"- {conflict_type}: {source} ({detail})")
            elif source:
                items.append(f"- {conflict_type}: {source}")
            else:
                items.append(f"- {conflict_type}")

        self.console.print(Panel("\n".join(items), title="Conflicts", style="yellow"))


def _format_metadata_highlights(metadata: dict[str, Any]) -> list[str]:
    highlights: list[str] = []
    if not metadata:
        return highlights

    preferred_keys = [
        "vendor_percent",
        "wasted_bytes",
        "duplicate_groups",
        "backup_files",
        "most_complex_files",
        "vendor_roots",
    ]

    def render_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            return f"{len(value)} items"
        if isinstance(value, (list, tuple, set)):
            return f"{len(value)} items"
        return str(value)

    used: set[str] = set()
    for key in preferred_keys:
        if key in metadata:
            used.add(key)
            rendered = render_value(metadata[key])
            if rendered is not None:
                highlights.append(f"{key}: {rendered}")

    for key, value in metadata.items():
        if key in used:
            continue
        rendered = render_value(value)
        if rendered is not None:
            highlights.append(f"{key}: {rendered}")
        if len(highlights) >= 6:
            break

    return highlights


def _count_execution_statuses(action_log: Iterable[dict[str, Any]]) -> tuple[int, int, int]:
    executed = 0
    skipped = 0
    errors = 0

    for entry in action_log:
        status = str(entry.get("status") or entry.get("result") or "").lower()
        if status in {"executed", "done", "success", "ok"}:
            executed += 1
        elif status in {"skipped", "noop"}:
            skipped += 1
        elif status in {"error", "failed", "failure"}:
            errors += 1

    return executed, skipped, errors
