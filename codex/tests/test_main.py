"""CLI-level tests for main.py — help output and risk-level filtering."""
from __future__ import annotations

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


# ── analyze --risk-level filtering ───────────────────────────────────────────

def _analyze(runner, report_path, project_dir, plan_path, risk_level="HIGH"):
    return runner.invoke(
        cli,
        [
            "analyze",
            "--report", str(report_path),
            "--project-dir", str(project_dir),
            "--risk-level", risk_level,
            "--output-plan", str(plan_path),
            "--html-report", str(plan_path.parent / "report.html"),
        ],
        catch_exceptions=False,
    )


def test_analyze_risk_level_high_includes_all(runner, project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_high = tmp_path / "plan_high.json"
    plan_low = tmp_path / "plan_low.json"

    _analyze(runner, report_path, project_dir, plan_high, "HIGH")
    _analyze(runner, report_path, project_dir, plan_low, "LOW")

    actions_high = json.loads(plan_high.read_text())["actions"]
    actions_low = json.loads(plan_low.read_text())["actions"]
    assert len(actions_high) >= len(actions_low)


def test_analyze_risk_level_low_no_high_actions(runner, project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"

    _analyze(runner, report_path, project_dir, plan_path, "LOW")

    actions = json.loads(plan_path.read_text())["actions"]
    high_actions = [a for a in actions if a["risk_level"] == "HIGH"]
    assert high_actions == [], "LOW filter must exclude HIGH-risk actions"


def test_analyze_risk_level_medium_no_high_actions(runner, project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"

    _analyze(runner, report_path, project_dir, plan_path, "MEDIUM")

    actions = json.loads(plan_path.read_text())["actions"]
    high_actions = [a for a in actions if a["risk_level"] == "HIGH"]
    assert high_actions == [], "MEDIUM filter must exclude HIGH-risk actions"


def test_analyze_risk_level_invalid_rejected(runner, project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"

    result = runner.invoke(
        cli,
        [
            "analyze",
            "--report", str(report_path),
            "--project-dir", str(project_dir),
            "--risk-level", "INVALID",
            "--output-plan", str(plan_path),
            "--html-report", str(tmp_path / "report.html"),
        ],
    )
    assert result.exit_code != 0
