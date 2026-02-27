from __future__ import annotations

import concurrent.futures
import json
import logging
from pathlib import Path
from typing import Any

import click

from analyzers.backup_analyzer import BackupAnalyzer
from analyzers.complexity_analyzer import ComplexityAnalyzer
from analyzers.duplicate_analyzer import DuplicateAnalyzer
from analyzers.structure_analyzer import StructureAnalyzer
from analyzers.vendor_analyzer import VendorAnalyzer
from core.loader import ReportLoader
from core.models import ActionPlan, RiskLevel
from core.scanner import DirectoryScanner
from executors.file_ops import FileOps
from executors.gitignore_gen import GitignoreGen
from executors.safe_executor import SafeExecutor
from planners.action_planner import ActionPlanner
from planners.conflict_resolver import ConflictResolver
from reporters.cli_reporter import CLIReporter
from reporters.html_reporter import HTMLReporter


logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def _risk_ceiling(name: str) -> RiskLevel:
    return RiskLevel(str(name))


def _filter_plan_by_risk(plan: ActionPlan, ceiling: RiskLevel) -> ActionPlan:
    if ceiling == RiskLevel.HIGH:
        return plan
    allowed = [a for a in plan.actions if a.risk_level <= ceiling]
    return ActionPlan(actions=allowed, created_at=plan.created_at, project_dir=plan.project_dir)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_plan(path: Path) -> ActionPlan:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Plan JSON must be an object")
    return ActionPlan.from_dict(raw)


@click.group()
@click.option("--verbose", is_flag=True, default=False, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    _configure_logging(verbose)


@cli.command()
@click.option("--report", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--project-dir", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--risk-level",
    default="HIGH",
    type=click.Choice(["LOW", "MEDIUM", "HIGH"], case_sensitive=False),
    show_default=True,
    help="Only include actions up to this risk level.",
)
@click.option("--output-plan", default="action_plan.json", show_default=True, type=click.Path(path_type=Path))
@click.option("--html-report", default="report.html", show_default=True, type=click.Path(path_type=Path))
def analyze(report: Path, project_dir: Path, risk_level: str, output_plan: Path, html_report: Path) -> None:
    """
    Load JSON + scan disk → run all analyzers → save plan + HTML report.
    """
    reporter = CLIReporter()

    loader = ReportLoader(report)
    summary = loader.load_summary()

    json_records: dict[str, Any] = {}
    for rel_path, record in loader.iter_files():
        json_records[rel_path] = record

    scanner = DirectoryScanner(project_dir)
    scan_result = scanner.cross_validate(json_records)
    records = scan_result.matched

    def run_vendor() -> Any:
        return VendorAnalyzer(records, project_dir).analyze()

    def run_dupes() -> Any:
        return DuplicateAnalyzer(records, project_dir).analyze()

    def run_backup() -> Any:
        return BackupAnalyzer(records).analyze()

    def run_complexity() -> Any:
        return ComplexityAnalyzer(records, summary).analyze()

    def run_structure() -> Any:
        return StructureAnalyzer(records).analyze()

    analyzers = [run_vendor, run_dupes, run_backup, run_complexity, run_structure]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(analyzers)) as pool:
        futures = [pool.submit(fn) for fn in analyzers]
        for f in futures:
            results.append(f.result())

    reporter.print_analyzer_results(results)

    plan = ActionPlanner(results, project_dir=str(project_dir)).build_plan()
    resolver = ConflictResolver(plan)
    plan = resolver.resolve()
    reporter.print_conflict_report(resolver.conflict_report())

    ceiling = _risk_ceiling(risk_level.upper())
    plan = _filter_plan_by_risk(plan, ceiling)

    reporter.print_summary(plan)

    _write_json(output_plan, plan.to_dict())
    HTMLReporter(plan=plan, results=results, project_dir=str(project_dir)).write(html_report)


@cli.command()
@click.option("--plan", "plan_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--html-report", default="report.html", show_default=True, type=click.Path(path_type=Path))
def plan(plan_path: Path, html_report: Path) -> None:
    """
    Load a saved plan → show summary + write HTML report.
    """
    reporter = CLIReporter()
    loaded = _load_plan(plan_path)
    reporter.print_summary(loaded)
    HTMLReporter(plan=loaded, results=[], project_dir=loaded.project_dir).write(html_report)


@cli.command()
@click.option("--plan", "plan_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--project-dir", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--execute", "do_execute", is_flag=True, default=False, help="Actually modify files (default: dry-run).")
def execute(plan_path: Path, project_dir: Path, do_execute: bool) -> None:
    """
    Load a saved plan → apply safe executor (dry-run by default).
    """
    reporter = CLIReporter()
    loaded = _load_plan(plan_path)

    # Generate a proposed .gitignore diff for ADD_GITIGNORE actions.
    # SafeExecutor still owns the actual mutation + backup handling.
    try:
        diff_str = GitignoreGen(project_dir).apply(loaded.actions, dry_run=True)
        if diff_str:
            logger.info("Proposed .gitignore diff:\n%s", diff_str)
    except Exception:
        logger.exception("Failed to generate .gitignore diff")

    def confirm_fn(prompt: str) -> bool:
        """
        Prefer interactive prompting when a TTY is available.
        In non-interactive contexts (e.g., tests/CI), deny by default
        instead of raising due to EOF.
        """
        try:
            stdin = click.get_text_stream("stdin")
            if hasattr(stdin, "isatty") and not stdin.isatty():
                return False
            return bool(click.confirm(prompt, default=False))
        except (EOFError, click.Abort):
            return False

    ex = SafeExecutor(loaded, project_dir, dry_run=not do_execute, confirm_fn=confirm_fn)
    backup_info = ex.execute()

    # Persist a rollback-compatible action log only for real execution.
    if do_execute and backup_info.backup_dir.exists():
        action_log_for_rollback: list[dict[str, Any]] = []
        for entry in backup_info.action_log:
            action = entry.get("action")
            backup_path = entry.get("backup_path")
            if backup_path is None:
                continue
            action_type = getattr(action, "action_type", None)
            if action_type is not None and str(getattr(action_type, "value", action_type)) not in {"DELETE", "MOVE"}:
                continue
            status_raw = str(entry.get("status", "")).lower()
            ok = status_raw in {"executed", "ok", "done", "success"}
            out_entry: dict[str, Any] = {
                "status": "ok" if ok else "skipped",
                "backup_path": (None if backup_path is None else str(backup_path)),
            }
            if action is not None and hasattr(action, "to_dict"):
                out_entry["action"] = action.to_dict()
            elif isinstance(action, dict):
                out_entry["action"] = dict(action)
            action_log_for_rollback.append(out_entry)

        _write_json(
            backup_info.backup_dir / "action_log.json",
            {"backup_dir": str(backup_info.backup_dir), "action_log": action_log_for_rollback},
        )

    reporter.print_execution_log(backup_info)


@cli.command()
@click.option("--backup-dir", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--project-dir", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
def rollback(backup_dir: Path, project_dir: Path) -> None:
    """
    Restore files from a backup directory created during execute.
    """
    action_log_path = backup_dir / "action_log.json"
    if not action_log_path.exists():
        raise click.ClickException(f"Missing action_log.json in backup directory: {backup_dir}")

    raw = json.loads(action_log_path.read_text(encoding="utf-8"))
    action_log = raw.get("action_log", []) if isinstance(raw, dict) else []
    if not isinstance(action_log, list):
        raise click.ClickException("Invalid action_log.json: action_log must be a list")

    ops = FileOps(project_dir=project_dir, backup_dir=backup_dir)
    restored = ops.rollback(backup_dir, action_log)
    click.echo(f"Restored {restored} file(s) from {backup_dir}")


if __name__ == "__main__":
    cli()
