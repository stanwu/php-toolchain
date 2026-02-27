import click
import json
import concurrent.futures
from pathlib import Path
import logging
from datetime import datetime

from core.loader import ReportLoader
from core.scanner import DirectoryScanner
from core.models import ActionPlan, RiskLevel, ActionType, Action
from analyzers.vendor_analyzer import VendorAnalyzer
from analyzers.duplicate_analyzer import DuplicateAnalyzer
from analyzers.backup_analyzer import BackupAnalyzer
from analyzers.complexity_analyzer import ComplexityAnalyzer
from analyzers.structure_analyzer import StructureAnalyzer
from planners.action_planner import ActionPlanner
from planners.conflict_resolver import ConflictResolver
from executors.safe_executor import SafeExecutor
from executors.file_ops import FileOps
from executors.gitignore_gen import GitignoreGen
from reporters.cli_reporter import CLIReporter
from reporters.html_reporter import HTMLReporter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@click.group()
def cli():
    """A CLI tool to analyze and clean up PHP projects."""
    pass

@cli.command()
@click.option("--report", required=True, type=click.Path(exists=True, dir_okay=False), help="Path to analysis_report.json")
@click.option("--project-dir", required=True, type=str, help="Path to the PHP project directory.")
@click.option("--risk-level", default="HIGH", type=click.Choice([r.name for r in RiskLevel], case_sensitive=False), help="Maximum risk level to include.")
@click.option("--output-plan", default="action_plan.json", type=str, help="Path to save the generated action plan.")
@click.option("--html-report", default="report.html", type=str, help="Path to save the HTML report.")
def analyze(report, project_dir, risk_level, output_plan, html_report):
    """Load JSON, scan disk, run analyzers, and generate a cleanup plan."""
    project_path = Path(project_dir)
    report_path = Path(report).resolve()
    output_plan_path = Path(output_plan).resolve()
    html_report_path = Path(html_report).resolve()
    max_risk = RiskLevel[risk_level.upper()]

    click.echo(f"Starting analysis of '{project_path}'...")

    # 1. Load and Scan
    loader = ReportLoader(report_path)
    scanner = DirectoryScanner(str(project_path))
    
    records = loader.load()
    scanner.scan()
    records = scanner.cross_validate(records)

    # 2. Analyze
    analyzers = [
        VendorAnalyzer(project_path),
        DuplicateAnalyzer(project_path),
        BackupAnalyzer(project_path),
        ComplexityAnalyzer(),
        StructureAnalyzer(project_path),
    ]
    
    analysis_results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_analyzer = {executor.submit(analyzer.analyze, records): analyzer for analyzer in analyzers}
        for future in concurrent.futures.as_completed(future_to_analyzer):
            try:
                result = future.result()
                analysis_results.append(result)
            except Exception as exc:
                analyzer_name = future_to_analyzer[future].__class__.__name__
                logging.error(f'{analyzer_name} generated an exception: {exc}')

    # 3. Plan
    planner = ActionPlanner()
    plan = planner.build_plan(analysis_results, str(project_path))
    
    resolver = ConflictResolver()
    plan = resolver.resolve(plan)

    # 4. Filter by risk
    original_action_count = len(plan.actions)
    plan.actions = [action for action in plan.actions if action.risk_level <= max_risk]
    filtered_action_count = len(plan.actions)

    # 5. Report and Save
    reporter = CLIReporter(plan)
    click.echo("\n--- Analysis Complete ---")
    reporter.print_analyzer_results(analysis_results)
    click.echo("\n--- Action Plan Summary ---")
    reporter.print_summary()
    
    if filtered_action_count < original_action_count:
        click.echo(f"Filtered out {original_action_count - filtered_action_count} actions based on risk level '{risk_level}'.")

    with open(output_plan_path, "w") as f:
        json.dump(plan.to_dict(), f, indent=2)
    click.echo(f"\nAction plan saved to '{output_plan_path}'")

    html_reporter = HTMLReporter(plan, analysis_results, str(project_path))
    html_reporter.write(html_report_path)
    click.echo(f"HTML report saved to '{html_report_path}'")


@cli.command()
@click.option("--plan", required=True, type=click.Path(exists=True, dir_okay=False), help="Path to the action plan JSON file.")
@click.option("--project-dir", required=True, type=str, help="Path to the PHP project directory.")
@click.option("--execute", "do_execute", is_flag=True, default=False, help="Execute the plan. Omit for a dry run.")
def execute(plan, project_dir, do_execute):
    """Execute a cleanup plan."""
    plan_path = Path(plan).resolve()
    project_path = Path(project_dir)

    with open(plan_path, "r") as f:
        plan_data = json.load(f)
    
    action_plan = ActionPlan.from_dict(plan_data)
    
    if str(project_path) != action_plan.project_dir:
        click.confirm(
            f"Warning: The project directory '{project_path}' is different from the one in the plan ('{action_plan.project_dir}'). Continue?",
            abort=True
        )

    # Apply gitignore actions first
    gitignore_actions = [action for action in action_plan.actions if action.action_type == ActionType.ADD_GITIGNORE]
    if gitignore_actions:
        click.echo("Applying .gitignore modifications...")
        gitignore_gen = GitignoreGen(project_path)
        gitignore_gen.apply(gitignore_actions, dry_run=not do_execute)

    # Execute other actions
    executor = SafeExecutor(action_plan, project_path, dry_run=not do_execute, confirm_fn=click.confirm)
    backup_info = executor.execute()

    reporter = CLIReporter(action_plan)
    click.echo("\n--- Execution Log ---")
    reporter.print_execution_log(backup_info, dry_run=not do_execute)

    if do_execute and backup_info.backup_dir:
        click.echo(f"\nBackup created at: {backup_info.backup_dir}")
    elif not do_execute:
        click.echo("\nThis was a dry run. No files were changed.")


@cli.command()
@click.option("--backup-dir", required=True, type=str, help="Path to the backup directory to restore from.")
@click.option("--project-dir", required=True, type=str, help="Path to the PHP project directory to restore files to.")
def rollback(backup_dir, project_dir):
    """Roll back changes from a backup directory."""
    project_path = Path(project_dir)
    backup_path = Path(backup_dir).resolve()
    
    click.echo(f"Starting rollback from '{backup_path}' to '{project_path}'...")
    
    action_log_path = backup_path / "action_log.json"
    if not action_log_path.exists():
        click.echo(f"Error: action_log.json not found in '{backup_path}'", err=True)
        return

    with open(action_log_path, "r") as f:
        action_log = json.load(f)

    file_ops = FileOps(project_path, backup_path)
    restored_count = file_ops.rollback(action_log)
    
    click.echo(f"\nRollback complete. {restored_count} files/directories were restored.")


if __name__ == "__main__":
    cli()