import concurrent.futures
import json
import logging
from pathlib import Path

import click

from analyzers.backup_analyzer import BackupAnalyzer
from analyzers.complexity_analyzer import ComplexityAnalyzer
from analyzers.duplicate_analyzer import DuplicateAnalyzer
from analyzers.structure_analyzer import StructureAnalyzer
from analyzers.vendor_analyzer import VendorAnalyzer
from core.loader import ReportLoader
from core.models import Action, ActionPlan, BackupInfo, RiskLevel
from core.scanner import DirectoryScanner
from executors.file_ops import FileOps
from executors.gitignore_gen import GitignoreGen
from executors.safe_executor import SafeExecutor
from planners.action_planner import ActionPlanner
from planners.conflict_resolver import ConflictResolver
from reporters.cli_reporter import CLIReporter
from reporters.html_reporter import HTMLReporter

logging.basicConfig(level=logging.WARNING)


@click.group()
def cli() -> None:
    """PHP Cleanup Toolkit — analyze, plan, execute, and rollback PHP project cleanups."""


@cli.command()
@click.option("--report", required=True, type=click.Path(exists=True))
@click.option("--project-dir", required=True, type=click.Path(exists=True))
@click.option(
    "--risk-level",
    default="HIGH",
    type=click.Choice(["LOW", "MEDIUM", "HIGH"]),
    help="Only include actions up to this risk level.",
)
@click.option("--output-plan", default="action_plan.json")
@click.option("--html-report", default="report.html")
def analyze(
    report: str,
    project_dir: str,
    risk_level: str,
    output_plan: str,
    html_report: str,
) -> None:
    """Load JSON report + scan disk → run all analyzers → save plan."""
    reporter = CLIReporter()

    # 1. Stream-load JSON report
    loader = ReportLoader(Path(report))
    summary = loader.load_summary()
    records = loader.load_all()

    # 2. Cross-validate disk vs. JSON (sets exists_on_disk flags on records)
    scanner = DirectoryScanner(Path(project_dir))
    scanner.cross_validate(records)

    # 3. Run 5 analyzers in parallel (read-only access to records)
    def _run_vendor() -> "AnalysisResult":  # type: ignore[name-defined]
        return VendorAnalyzer(records, Path(project_dir)).analyze()

    def _run_duplicate() -> "AnalysisResult":  # type: ignore[name-defined]
        return DuplicateAnalyzer(records, Path(project_dir)).analyze()

    def _run_backup() -> "AnalysisResult":  # type: ignore[name-defined]
        return BackupAnalyzer(records).analyze()

    def _run_complexity() -> "AnalysisResult":  # type: ignore[name-defined]
        return ComplexityAnalyzer(records, summary).analyze()

    def _run_structure() -> "AnalysisResult":  # type: ignore[name-defined]
        return StructureAnalyzer(records).analyze()

    tasks = [_run_vendor, _run_duplicate, _run_backup, _run_complexity, _run_structure]
    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(t): t for t in tasks}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # 4. Build consolidated plan
    planner = ActionPlanner(results, project_dir)
    plan = planner.build_plan()

    # 5. Filter by requested risk level
    max_risk = RiskLevel(risk_level)
    plan.actions = [a for a in plan.actions if a.risk_level <= max_risk]

    # 6. Resolve conflicts
    resolver = ConflictResolver(plan)
    plan = resolver.resolve()

    # 7. Report to CLI
    reporter.print_analyzer_results(results)
    reporter.print_conflict_report(resolver.conflict_report())
    reporter.print_summary(plan)
    reporter.print_action_table(plan)

    # 8. Save plan to JSON
    with open(output_plan, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, indent=2)
    click.echo(f"Plan saved → {output_plan}")

    # 9. Write HTML report
    html_reporter = HTMLReporter(plan, results, project_dir)
    html_reporter.write(Path(html_report))
    click.echo(f"HTML report → {html_report}")


@cli.command()
@click.option("--plan", required=True, type=click.Path(exists=True))
@click.option("--project-dir", required=True, type=click.Path(exists=True))
@click.option(
    "--execute",
    "do_execute",
    is_flag=True,
    default=False,
    help="Actually execute actions (default is dry-run).",
)
def execute(plan: str, project_dir: str, do_execute: bool) -> None:
    """Load a saved plan → run safe_executor (dry-run unless --execute)."""
    reporter = CLIReporter()

    # 1. Load plan
    with open(plan, encoding="utf-8") as f:
        plan_data = json.load(f)
    action_plan = ActionPlan.from_dict(plan_data)

    # 2. Apply .gitignore entries
    gitignore_gen = GitignoreGen(Path(project_dir))
    diff = gitignore_gen.apply(action_plan.actions, dry_run=not do_execute)
    if diff:
        click.echo("--- .gitignore diff ---")
        click.echo(diff)

    # 3. Execute actions (confirm_fn=None → auto-approve all risk levels)
    executor = SafeExecutor(
        plan=action_plan,
        project_dir=Path(project_dir),
        dry_run=not do_execute,
        confirm_fn=None,
    )
    backup_info = executor.execute()

    # 4. Persist action log for later rollback (live runs only)
    if do_execute:
        action_log_path = backup_info.backup_dir / "action_log.json"
        action_log_data = {
            "backup_dir": str(backup_info.backup_dir),
            "action_log": [
                {
                    "action": (
                        entry["action"].to_dict()
                        if isinstance(entry["action"], Action)
                        else entry["action"]
                    ),
                    "status": entry.get("status", "ok"),
                    "backup_path": entry.get("backup_path"),
                    "error": entry.get("error"),
                }
                for entry in backup_info.action_log
            ],
        }
        with open(action_log_path, "w", encoding="utf-8") as f:
            json.dump(action_log_data, f, indent=2)
        click.echo(f"Backup dir : {backup_info.backup_dir}")
        click.echo(f"Action log : {action_log_path}")

    # 5. Print execution summary
    reporter.print_execution_log(backup_info)


@cli.command()
@click.option("--backup-dir", required=True, type=click.Path(exists=True))
@click.option("--project-dir", required=True, type=click.Path(exists=True))
def rollback(backup_dir: str, project_dir: str) -> None:
    """Restore files from a backup directory created by execute."""
    backup_path = Path(backup_dir)
    action_log_path = backup_path / "action_log.json"

    if not action_log_path.exists():
        raise click.ClickException(f"action_log.json not found in {backup_dir}")

    with open(action_log_path, encoding="utf-8") as f:
        data = json.load(f)

    action_log = data["action_log"]
    file_ops = FileOps(Path(project_dir), backup_path)
    count = file_ops.rollback(backup_path, action_log)
    click.echo(f"Restored {count} file(s) from {backup_dir}")


if __name__ == "__main__":
    cli()
