"""Unit tests for main.py CLI — edge cases and error paths."""
import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from main import cli

FIXTURE_DIR = Path(__file__).parent / "fixtures"
MINI_REPORT = FIXTURE_DIR / "mini_report.json"

PROJECT_FILES = {
    "index.php": "<?php echo 'index'; ?>",
    "vendor/autoload.php": "<?php // vendor autoload",
    "backup_old.php": "<?php // backup old",
    "utils_copy.php": "<?php // utils copy",
}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def project_setup(tmp_path: Path):
    report_path = tmp_path / "report.json"
    shutil.copy(MINI_REPORT, report_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    for rel_path, content in PROJECT_FILES.items():
        abs_path = project_dir / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content)

    return report_path, project_dir


@pytest.fixture
def patched_backup_root(tmp_path: Path, monkeypatch):
    import executors.safe_executor as se
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    monkeypatch.setattr(se, "BACKUP_ROOT", backup_root)
    return backup_root


# ── help ──────────────────────────────────────────────────────────────────────

def test_top_level_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.output
    assert "execute" in result.output
    assert "rollback" in result.output


def test_analyze_help(runner):
    result = runner.invoke(cli, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--report" in result.output
    assert "--project-dir" in result.output
    assert "--risk-level" in result.output


def test_execute_help(runner):
    result = runner.invoke(cli, ["execute", "--help"])
    assert result.exit_code == 0
    assert "--plan" in result.output
    assert "--execute" in result.output


def test_rollback_help(runner):
    result = runner.invoke(cli, ["rollback", "--help"])
    assert result.exit_code == 0
    assert "--backup-dir" in result.output
    assert "--project-dir" in result.output


# ── analyze output messages ───────────────────────────────────────────────────

def test_analyze_output_shows_plan_saved(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    result = runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    assert "Plan saved" in result.output


def test_analyze_output_shows_html_report(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    result = runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    assert "HTML report" in result.output


# ── analyze --risk-level filtering ───────────────────────────────────────────

def test_analyze_risk_level_high_includes_all(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--risk-level", "HIGH",
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    with open(plan_path) as f:
        data_high = json.load(f)

    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--risk-level", "LOW",
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    with open(plan_path) as f:
        data_low = json.load(f)

    # HIGH includes at least as many actions as LOW
    assert len(data_high["actions"]) >= len(data_low["actions"])


def test_analyze_risk_level_low_no_high_actions(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--risk-level", "LOW",
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    with open(plan_path) as f:
        data = json.load(f)
    high_actions = [a for a in data["actions"] if a["risk_level"] == "HIGH"]
    assert high_actions == [], "LOW filter must exclude HIGH-risk actions"


def test_analyze_risk_level_medium_no_high_actions(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--risk-level", "MEDIUM",
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    with open(plan_path) as f:
        data = json.load(f)
    high_actions = [a for a in data["actions"] if a["risk_level"] == "HIGH"]
    assert high_actions == [], "MEDIUM filter must exclude HIGH-risk actions"


# ── execute dry-run output ────────────────────────────────────────────────────

def test_execute_dry_run_shows_execution_summary(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        cli,
        ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "Executed" in result.output
    # dry-run must not delete files
    assert (project_dir / "backup_old.php").exists()


def test_execute_dry_run_no_backup_dir_output(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        cli,
        ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir)],
        catch_exceptions=False,
    )
    # "Backup dir" line is only printed on real execute
    assert "Backup dir" not in result.output


# ── execute live-run output ───────────────────────────────────────────────────

def test_execute_real_output_shows_backup_dir(runner, project_setup, patched_backup_root):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    result = runner.invoke(
        cli,
        ["execute", "--plan", str(plan_path),
         "--project-dir", str(project_dir), "--execute"],
        catch_exceptions=False,
    )
    assert "Backup dir" in result.output
    assert "Action log" in result.output


# ── rollback error path ───────────────────────────────────────────────────────

def test_rollback_missing_action_log_raises(runner, tmp_path):
    backup_dir = tmp_path / "backup_empty"
    backup_dir.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    result = runner.invoke(
        cli,
        ["rollback", "--backup-dir", str(backup_dir),
         "--project-dir", str(project_dir)],
    )
    assert result.exit_code != 0
    assert "action_log.json" in result.output


def test_rollback_output_shows_restored_count(runner, project_setup, patched_backup_root):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"

    runner.invoke(
        cli,
        ["analyze", "--report", str(report_path),
         "--project-dir", str(project_dir),
         "--output-plan", str(plan_path),
         "--html-report", str(html_path)],
        catch_exceptions=False,
    )
    runner.invoke(
        cli,
        ["execute", "--plan", str(plan_path),
         "--project-dir", str(project_dir), "--execute"],
        catch_exceptions=False,
    )

    backup_dirs = [d for d in patched_backup_root.iterdir() if d.is_dir()]
    result = runner.invoke(
        cli,
        ["rollback", "--backup-dir", str(backup_dirs[0]),
         "--project-dir", str(project_dir)],
        catch_exceptions=False,
    )
    assert "Restored" in result.output
    assert result.exit_code == 0
