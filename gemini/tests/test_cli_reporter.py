import io
from dataclasses import dataclass

from rich.console import Console
from rich.progress import Progress

from core.models import Action, ActionPlan, ActionType, AnalysisResult, RiskLevel
from reporters.cli_reporter import CLIReporter


# Mock BackupInfo as its definition is not provided in the master context's core/models.py
# but is expected by the reporter as per the prompt for this step.
@dataclass
class MockBackupInfo:
    backup_path: str
    executed_count: int
    skipped_count: int
    error_count: int


def make_console():
    buf = io.StringIO()
    # disable markup and highlight for simple string comparison
    return Console(file=buf, highlight=False, markup=False, color_system=None), buf


def test_print_summary_shows_total():
    console, buf = make_console()
    # This is a bit of a hack, but we need to inject the console into the module-level instance
    # that the reporter class uses.
    import reporters.cli_reporter
    reporters.cli_reporter.console = console
    
    reporter = CLIReporter()
    plan = ActionPlan(
        actions=[
            Action(ActionType.DELETE, "a.php", None, RiskLevel.LOW, "reason"),
            Action(ActionType.DELETE, "b.php", None, RiskLevel.LOW, "reason"),
        ]
    )
    reporter.print_summary(plan)
    output = buf.getvalue()
    assert "Total actions : 2" in output


def test_print_summary_shows_risk_counts():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    plan = ActionPlan(
        actions=[
            Action(ActionType.DELETE, "a.php", None, RiskLevel.LOW, "reason"),
            Action(ActionType.DELETE, "b.php", None, RiskLevel.MEDIUM, "reason"),
            Action(ActionType.DELETE, "c.php", None, RiskLevel.MEDIUM, "reason"),
            Action(ActionType.DELETE, "d.php", None, RiskLevel.HIGH, "reason"),
        ]
    )
    reporter.print_summary(plan)
    output = buf.getvalue()
    assert "LOW risk      : 1" in output
    assert "MEDIUM risk   : 2" in output
    assert "HIGH risk     : 1" in output


def test_print_action_table_headers():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    plan = ActionPlan(actions=[])
    reporter.print_action_table(plan)
    output = buf.getvalue()
    assert "#" in output
    assert "Type" in output
    assert "Source" in output
    assert "Risk" in output
    assert "Reason" in output


def test_print_action_table_truncation():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    actions = [
        Action(ActionType.DELETE, f"f{i}.php", None, RiskLevel.LOW, "r")
        for i in range(6)
    ]
    plan = ActionPlan(actions=actions)
    reporter.print_action_table(plan, max_rows=5)
    output = buf.getvalue()
    assert "... and 1 more actions" in output


def test_print_action_table_no_truncation():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    actions = [
        Action(ActionType.DELETE, f"f{i}.php", None, RiskLevel.LOW, "r")
        for i in range(5)
    ]
    plan = ActionPlan(actions=actions)
    reporter.print_action_table(plan, max_rows=5)
    output = buf.getvalue()
    assert "... and" not in output


def test_print_analyzer_results_name():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    results = [AnalysisResult("Test Analyzer", [], {})]
    reporter.print_analyzer_results(results)
    output = buf.getvalue()
    assert "Test Analyzer" in output


def test_print_analyzer_results_count():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    actions = [Action(ActionType.DELETE, "f.php", None, RiskLevel.LOW, "r")]
    results = [AnalysisResult("Test Analyzer", actions, {})]
    reporter.print_analyzer_results(results)
    output = buf.getvalue()
    assert "1 actions found" in output


def test_print_execution_log_backup_path():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    backup_info = MockBackupInfo("/path/to/backup", 1, 2, 0)
    reporter.print_execution_log(backup_info)
    output = buf.getvalue()
    assert "Backup at : /path/to/backup" in output
    assert "Executed  : 1" in output
    assert "Skipped   : 2" in output
    assert "Errors    : 0" in output


def test_print_conflict_report_with_conflicts():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    conflicts = [
        {
            "type": "DELETE_PARENT",
            "source": "/path/to/dir",
            "reason": "Deletes dir with other targets",
        }
    ]
    reporter.print_conflict_report(conflicts)
    output = buf.getvalue()
    assert "Conflict Report" in output
    assert "DELETE_PARENT" in output
    assert "/path/to/dir" in output


def test_print_conflict_report_no_conflicts():
    console, buf = make_console()
    import reporters.cli_reporter
    reporters.cli_reporter.console = console

    reporter = CLIReporter()
    reporter.print_conflict_report([])
    output = buf.getvalue()
    assert "No conflicts detected" in output


def test_progress_bar_returns_progress():
    reporter = CLIReporter()
    progress = reporter.progress_bar(100, "Testing")
    assert isinstance(progress, Progress)
