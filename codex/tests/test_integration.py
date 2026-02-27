from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

import executors.safe_executor as safe_executor_mod
from main import cli


@pytest.fixture
def project_setup(tmp_path: Path) -> tuple[Path, Path]:
    """
    Create a report.json (from fixtures) + a matching project directory tree.
    Returns (report_path, project_dir).
    """
    report_src = Path(__file__).parent / "fixtures" / "mini_report.json"
    report_path = tmp_path / "report.json"
    report_path.write_text(report_src.read_text(encoding="utf-8"), encoding="utf-8")

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    files = [
        "index.php",
        "vendor/autoload.php",
        "vendor/lib/helper.php",
        "saas/service.php",
        "backup_old.php",
        "utils_copy.php",
    ]
    contents = {
        "index.php": "<?php\nif (isset($_GET['id'])) { echo $_GET['id']; }\n",
        "vendor/autoload.php": "<?php\n// autoload stub\n",
        "vendor/lib/helper.php": "<?php\nfunction helper() { return 1; }\n",
        "saas/service.php": "<?php\nfunction processOrder() { return true; }\n",
        "backup_old.php": "<?php\n// old backup\n",
        "utils_copy.php": "<?php\n// utils copy\n",
    }

    for rel in files:
        p = project_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contents[rel], encoding="utf-8")

    return report_path, project_dir


def _run_analyze(runner: CliRunner, report_path: Path, project_dir: Path, plan_path: Path, html_path: Path):
    return runner.invoke(
        cli,
        [
            "analyze",
            "--report",
            str(report_path),
            "--project-dir",
            str(project_dir),
            "--output-plan",
            str(plan_path),
            "--html-report",
            str(html_path),
        ],
    )


def _run_execute(runner: CliRunner, plan_path: Path, project_dir: Path, do_execute: bool = False):
    args = ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir)]
    if do_execute:
        args.append("--execute")
    return runner.invoke(cli, args)


def _run_rollback(runner: CliRunner, backup_dir: Path, project_dir: Path):
    return runner.invoke(cli, ["rollback", "--backup-dir", str(backup_dir), "--project-dir", str(project_dir)])


def _load_plan(plan_path: Path) -> dict:
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _find_backup_dir(backup_root: Path) -> Path:
    candidates = [p for p in backup_root.iterdir() if p.is_dir()]
    assert candidates, f"no backup dirs under {backup_root}"
    return sorted(candidates)[-1]


def test_analyze_exit_code_0(project_setup: tuple[Path, Path], tmp_path: Path) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"

    result = _run_analyze(runner, report_path, project_dir, plan_path, html_path)

    assert result.exit_code == 0, result.output


def test_analyze_creates_plan_file(project_setup: tuple[Path, Path], tmp_path: Path) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)

    assert plan_path.exists()


def test_analyze_creates_html_report(project_setup: tuple[Path, Path], tmp_path: Path) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)

    assert html_path.exists()


def test_analyze_plan_is_valid_json(project_setup: tuple[Path, Path], tmp_path: Path) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)

    parsed = _load_plan(plan_path)
    assert isinstance(parsed, dict)
    assert "actions" in parsed


def test_analyze_vendor_in_plan(project_setup: tuple[Path, Path], tmp_path: Path) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)

    parsed = _load_plan(plan_path)
    actions = parsed.get("actions", [])
    assert any(a.get("action_type") == "ADD_GITIGNORE" and a.get("source") == "vendor" for a in actions)


def test_analyze_backup_in_plan(project_setup: tuple[Path, Path], tmp_path: Path) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)

    parsed = _load_plan(plan_path)
    actions = parsed.get("actions", [])
    assert any(a.get("action_type") == "DELETE" and a.get("source") == "backup_old.php" for a in actions)


def test_execute_exit_code_0(project_setup: tuple[Path, Path], tmp_path: Path, monkeypatch) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"
    backup_root = tmp_path / "backup-root"
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", backup_root)

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)
    result = _run_execute(runner, plan_path, project_dir, do_execute=False)

    assert result.exit_code == 0, result.output


def test_execute_dry_run_no_changes(project_setup: tuple[Path, Path], tmp_path: Path, monkeypatch) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"
    backup_root = tmp_path / "backup-root"
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", backup_root)

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)

    target = project_dir / "backup_old.php"
    original = target.read_text(encoding="utf-8")
    result = _run_execute(runner, plan_path, project_dir, do_execute=False)

    assert result.exit_code == 0, result.output
    assert target.exists()
    assert target.read_text(encoding="utf-8") == original
    assert not backup_root.exists()


def test_execute_real_deletes_file(project_setup: tuple[Path, Path], tmp_path: Path, monkeypatch) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"
    backup_root = tmp_path / "backup-root"
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", backup_root)

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)
    result = _run_execute(runner, plan_path, project_dir, do_execute=True)

    assert result.exit_code == 0, result.output
    assert not (project_dir / "backup_old.php").exists()


def test_execute_creates_backup_dir(project_setup: tuple[Path, Path], tmp_path: Path, monkeypatch) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"
    backup_root = tmp_path / "backup-root"
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", backup_root)

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)
    result = _run_execute(runner, plan_path, project_dir, do_execute=True)

    assert result.exit_code == 0, result.output
    assert backup_root.exists()
    assert any(p.is_dir() for p in backup_root.iterdir())


def test_rollback_exit_code_0(project_setup: tuple[Path, Path], tmp_path: Path, monkeypatch) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"
    backup_root = tmp_path / "backup-root"
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", backup_root)

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)
    _run_execute(runner, plan_path, project_dir, do_execute=True)
    backup_dir = _find_backup_dir(backup_root)

    result = _run_rollback(runner, backup_dir, project_dir)

    assert result.exit_code == 0, result.output


def test_rollback_restores_file(project_setup: tuple[Path, Path], tmp_path: Path, monkeypatch) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"
    backup_root = tmp_path / "backup-root"
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", backup_root)

    target = project_dir / "backup_old.php"
    original = target.read_text(encoding="utf-8")

    _run_analyze(runner, report_path, project_dir, plan_path, html_path)
    _run_execute(runner, plan_path, project_dir, do_execute=True)
    assert not target.exists()

    backup_dir = _find_backup_dir(backup_root)
    _run_rollback(runner, backup_dir, project_dir)

    assert target.exists()
    assert target.read_text(encoding="utf-8") == original


def test_full_pipeline(project_setup: tuple[Path, Path], tmp_path: Path, monkeypatch) -> None:
    report_path, project_dir = project_setup
    runner = CliRunner()
    plan_path = tmp_path / "action_plan.json"
    html_path = tmp_path / "report.html"
    backup_root = tmp_path / "backup-root"
    monkeypatch.setattr(safe_executor_mod, "BACKUP_ROOT", backup_root)

    target = project_dir / "backup_old.php"
    original = target.read_text(encoding="utf-8")

    r1 = _run_analyze(runner, report_path, project_dir, plan_path, html_path)
    assert r1.exit_code == 0

    r2 = _run_execute(runner, plan_path, project_dir, do_execute=True)
    assert r2.exit_code == 0
    assert not target.exists()

    backup_dir = _find_backup_dir(backup_root)
    r3 = _run_rollback(runner, backup_dir, project_dir)
    assert r3.exit_code == 0

    assert target.exists()
    assert target.read_text(encoding="utf-8") == original

