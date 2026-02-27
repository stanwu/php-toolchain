import io
from pathlib import Path

import pytest
from rich.console import Console
from rich.progress import Progress

from core.models import Action, ActionPlan, ActionType, AnalysisResult, BackupInfo, RiskLevel
from reporters.cli_reporter import CLIReporter


def make_console() -> tuple[CLIReporter, io.StringIO]:
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, markup=False)
    reporter = CLIReporter(console=con)
    return reporter, buf


def _action(
    action_type: ActionType = ActionType.DELETE,
    source: str = "file.php",
    risk: RiskLevel = RiskLevel.LOW,
    reason: str = "test reason",
    destination: str | None = None,
) -> Action:
    return Action(
        action_type=action_type,
        source=source,
        destination=destination,
        risk_level=risk,
        reason=reason,
    )


def _plan(*actions: Action) -> ActionPlan:
    return ActionPlan(actions=list(actions))


# ---------------------------------------------------------------------------
# print_summary
# ---------------------------------------------------------------------------

def test_print_summary_shows_total() -> None:
    reporter, buf = make_console()
    plan = _plan(
        _action(risk=RiskLevel.LOW),
        _action(risk=RiskLevel.MEDIUM),
        _action(risk=RiskLevel.HIGH),
    )
    reporter.print_summary(plan)
    output = buf.getvalue()
    assert "3" in output


def test_print_summary_shows_risk_counts() -> None:
    reporter, buf = make_console()
    plan = _plan(
        _action(risk=RiskLevel.LOW),
        _action(risk=RiskLevel.LOW),
        _action(risk=RiskLevel.MEDIUM),
        _action(risk=RiskLevel.HIGH),
        _action(risk=RiskLevel.HIGH),
        _action(risk=RiskLevel.HIGH),
    )
    reporter.print_summary(plan)
    output = buf.getvalue()
    assert "LOW" in output
    assert "MEDIUM" in output
    assert "HIGH" in output
    assert "2" in output   # LOW count
    assert "1" in output   # MEDIUM count
    assert "3" in output   # HIGH count


# ---------------------------------------------------------------------------
# print_action_table
# ---------------------------------------------------------------------------

def test_print_action_table_headers() -> None:
    reporter, buf = make_console()
    plan = _plan(_action())
    reporter.print_action_table(plan)
    output = buf.getvalue()
    assert "Type" in output
    assert "Source" in output
    assert "Risk" in output


def test_print_action_table_truncation() -> None:
    reporter, buf = make_console()
    actions = [_action(source=f"file_{i}.php") for i in range(60)]
    plan = ActionPlan(actions=actions)
    reporter.print_action_table(plan, max_rows=50)
    output = buf.getvalue()
    assert "... and 10 more" in output


def test_print_action_table_no_truncation() -> None:
    reporter, buf = make_console()
    actions = [_action(source=f"file_{i}.php") for i in range(50)]
    plan = ActionPlan(actions=actions)
    reporter.print_action_table(plan, max_rows=50)
    output = buf.getvalue()
    assert "more actions" not in output


# ---------------------------------------------------------------------------
# print_analyzer_results
# ---------------------------------------------------------------------------

def test_print_analyzer_results_name() -> None:
    reporter, buf = make_console()
    result = AnalysisResult(
        analyzer_name="VendorAnalyzer",
        actions=[_action()],
        metadata={},
    )
    reporter.print_analyzer_results([result])
    output = buf.getvalue()
    assert "VendorAnalyzer" in output


def test_print_analyzer_results_count() -> None:
    reporter, buf = make_console()
    result = AnalysisResult(
        analyzer_name="DuplicateAnalyzer",
        actions=[_action(), _action(source="other.php")],
        metadata={"wasted_bytes": 1024},
    )
    reporter.print_analyzer_results([result])
    output = buf.getvalue()
    assert "2" in output


# ---------------------------------------------------------------------------
# print_execution_log
# ---------------------------------------------------------------------------

def test_print_execution_log_backup_path() -> None:
    reporter, buf = make_console()
    backup_dir = Path("/home/user/.php-cleanup-backup/20240101_120000")
    backup_info = BackupInfo(
        timestamp="20240101_120000",
        backup_dir=backup_dir,
        action_log=[
            {"action": _action(), "backup_path": str(backup_dir / "file.php")},
        ],
    )
    reporter.print_execution_log(backup_info)
    output = buf.getvalue()
    assert str(backup_dir) in output


# ---------------------------------------------------------------------------
# print_conflict_report
# ---------------------------------------------------------------------------

def test_print_conflict_report_with_conflicts() -> None:
    reporter, buf = make_console()
    conflicts = [
        {"type": "overlap", "source": "vendor/lib/helper.php"},
        {"type": "duplicate", "source": "utils_copy.php"},
    ]
    reporter.print_conflict_report(conflicts)
    output = buf.getvalue()
    assert "overlap" in output
    assert "vendor/lib/helper.php" in output


def test_print_conflict_report_no_conflicts() -> None:
    reporter, buf = make_console()
    reporter.print_conflict_report([])
    output = buf.getvalue()
    assert "No conflicts detected" in output


# ---------------------------------------------------------------------------
# progress_bar
# ---------------------------------------------------------------------------

def test_progress_bar_returns_progress() -> None:
    reporter, _ = make_console()
    result = reporter.progress_bar(total=100, description="Processing...")
    assert isinstance(result, Progress)
