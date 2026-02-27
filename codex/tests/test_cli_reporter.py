from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from core.models import Action, ActionPlan, ActionType, AnalysisResult, BackupInfo, RiskLevel
from reporters.cli_reporter import CLIReporter


def make_console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, highlight=False, markup=False, width=160), buf


def _make_action(idx: int, risk: RiskLevel = RiskLevel.LOW) -> Action:
    return Action(
        action_type=ActionType.DELETE,
        source=f"file{idx}.php",
        destination=None,
        risk_level=risk,
        reason="cleanup",
    )


def test_print_summary_shows_total() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    plan = ActionPlan(actions=[_make_action(1), _make_action(2)])

    reporter.print_summary(plan)
    out = buf.getvalue()
    assert "Total actions" in out
    assert "2" in out


def test_print_summary_shows_risk_counts() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    plan = ActionPlan(
        actions=[
            _make_action(1, RiskLevel.LOW),
            _make_action(2, RiskLevel.LOW),
            _make_action(3, RiskLevel.MEDIUM),
            _make_action(4, RiskLevel.HIGH),
            _make_action(5, RiskLevel.HIGH),
        ]
    )

    reporter.print_summary(plan)
    out = buf.getvalue()
    assert "LOW risk" in out
    assert "MEDIUM risk" in out
    assert "HIGH risk" in out
    assert "2" in out
    assert "1" in out


def test_print_action_table_headers() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    plan = ActionPlan(actions=[_make_action(1)])

    reporter.print_action_table(plan, max_rows=50)
    out = buf.getvalue()
    assert "Type" in out
    assert "Source" in out
    assert "Risk" in out


def test_print_action_table_truncation() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    plan = ActionPlan(actions=[_make_action(1), _make_action(2), _make_action(3)])

    reporter.print_action_table(plan, max_rows=2)
    out = buf.getvalue()
    assert "... and 1 more actions" in out


def test_print_action_table_no_truncation() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    plan = ActionPlan(actions=[_make_action(1), _make_action(2)])

    reporter.print_action_table(plan, max_rows=2)
    out = buf.getvalue()
    assert "... and" not in out


def test_print_analyzer_results_name() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    result = AnalysisResult(analyzer_name="vendor_analyzer", actions=[_make_action(1)], metadata={"vendor_percent": 50})

    reporter.print_analyzer_results([result])
    out = buf.getvalue()
    assert "vendor_analyzer" in out


def test_print_analyzer_results_count() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    result = AnalysisResult(analyzer_name="backup_analyzer", actions=[_make_action(1), _make_action(2)], metadata={})

    reporter.print_analyzer_results([result])
    out = buf.getvalue()
    assert "2" in out
    assert "actions found" in out


def test_print_execution_log_backup_path(tmp_path: Path) -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    backup_dir = tmp_path / "backup"
    info = BackupInfo(
        timestamp="2026-02-27T00:00:00Z",
        backup_dir=backup_dir,
        action_log=[{"status": "executed"}, {"status": "skipped"}, {"status": "error"}],
    )

    reporter.print_execution_log(info)
    out = buf.getvalue()
    assert str(backup_dir) in out


def test_print_conflict_report_with_conflicts() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)
    conflicts = [{"type": "MOVE_OVERWRITE", "source": "a.php", "detail": "destination exists"}]

    reporter.print_conflict_report(conflicts)
    out = buf.getvalue()
    assert "MOVE_OVERWRITE" in out
    assert "a.php" in out


def test_print_conflict_report_no_conflicts() -> None:
    console, buf = make_console()
    reporter = CLIReporter(console)

    reporter.print_conflict_report([])
    out = buf.getvalue()
    assert "No conflicts detected" in out


def test_progress_bar_returns_progress() -> None:
    console, _ = make_console()
    reporter = CLIReporter(console)
    progress = reporter.progress_bar(total=3, description="Scanning")
    assert isinstance(progress, Progress)

