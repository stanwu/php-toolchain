"""Integration tests: full pipeline analyze → execute → rollback."""
import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from main import cli

FIXTURE_DIR = Path(__file__).parent / "fixtures"
MINI_REPORT = FIXTURE_DIR / "mini_report.json"

# Distinct file contents so no duplicates are detected by SHA-256
PROJECT_FILES = {
    "index.php": "<?php echo 'index'; ?>",
    "vendor/autoload.php": "<?php // vendor autoload",
    "vendor/lib/helper.php": "<?php // vendor lib helper",
    "saas/service.php": "<?php // saas service",
    "backup_old.php": "<?php // backup old",
    "utils_copy.php": "<?php // utils copy",
}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def project_setup(tmp_path: Path):
    """Create mini_report.json + matching project tree in tmp_path."""
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
    """Redirect SafeExecutor's BACKUP_ROOT to avoid polluting ~/.php-cleanup-backup/."""
    import executors.safe_executor as se

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    monkeypatch.setattr(se, "BACKUP_ROOT", backup_root)
    return backup_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_analyze(runner, report_path, project_dir, plan_path, html_path):
    return runner.invoke(
        cli,
        [
            "analyze",
            "--report", str(report_path),
            "--project-dir", str(project_dir),
            "--output-plan", str(plan_path),
            "--html-report", str(html_path),
        ],
        catch_exceptions=False,
    )


def _invoke_execute(runner, plan_path, project_dir, *, real: bool = False):
    args = [
        "execute",
        "--plan", str(plan_path),
        "--project-dir", str(project_dir),
    ]
    if real:
        args.append("--execute")
    return runner.invoke(cli, args, catch_exceptions=False)


def _invoke_rollback(runner, backup_dir, project_dir):
    return runner.invoke(
        cli,
        [
            "rollback",
            "--backup-dir", str(backup_dir),
            "--project-dir", str(project_dir),
        ],
        catch_exceptions=False,
    )


def _find_backup_dir(backup_root: Path) -> Path:
    """Return the single timestamped subdirectory created under backup_root."""
    dirs = [d for d in backup_root.iterdir() if d.is_dir()]
    assert len(dirs) == 1, f"Expected 1 backup dir, found: {dirs}"
    return dirs[0]


# ---------------------------------------------------------------------------
# Analyze tests
# ---------------------------------------------------------------------------

def test_analyze_creates_plan_file(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    assert plan_path.exists()


def test_analyze_creates_html_report(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    assert html_path.exists()


def test_analyze_plan_is_valid_json(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    with open(plan_path) as f:
        data = json.load(f)
    assert "actions" in data
    assert isinstance(data["actions"], list)


def test_analyze_vendor_in_plan(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    with open(plan_path) as f:
        data = json.load(f)
    vendor_actions = [
        a for a in data["actions"]
        if a["action_type"] == "ADD_GITIGNORE" and a["source"] == "vendor"
    ]
    assert vendor_actions, "Expected ADD_GITIGNORE action for 'vendor' in plan"


def test_analyze_backup_in_plan(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    with open(plan_path) as f:
        data = json.load(f)
    backup_actions = [
        a for a in data["actions"]
        if a["action_type"] == "DELETE" and a["source"] == "backup_old.php"
    ]
    assert backup_actions, "Expected DELETE action for 'backup_old.php' in plan"


def test_analyze_exit_code_0(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    result = _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Execute tests
# ---------------------------------------------------------------------------

def test_execute_dry_run_no_changes(runner, project_setup):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)

    # Dry-run execute (no --execute flag)
    _invoke_execute(runner, plan_path, project_dir, real=False)

    # All original files must still exist
    for rel_path in PROJECT_FILES:
        assert (project_dir / rel_path).exists(), f"{rel_path} should still exist after dry-run"


def test_execute_real_deletes_file(runner, project_setup, patched_backup_root):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    _invoke_execute(runner, plan_path, project_dir, real=True)

    assert not (project_dir / "backup_old.php").exists(), (
        "backup_old.php should be deleted after real execute"
    )


def test_execute_creates_backup_dir(runner, project_setup, patched_backup_root):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    _invoke_execute(runner, plan_path, project_dir, real=True)

    backup_dirs = list(patched_backup_root.iterdir())
    assert len(backup_dirs) >= 1, "A backup directory should have been created"
    assert backup_dirs[0].is_dir()


def test_execute_exit_code_0(runner, project_setup, patched_backup_root):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    result = _invoke_execute(runner, plan_path, project_dir, real=True)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Rollback tests
# ---------------------------------------------------------------------------

def test_rollback_restores_file(runner, project_setup, patched_backup_root):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"

    # analyze → execute (deletes files)
    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    _invoke_execute(runner, plan_path, project_dir, real=True)
    assert not (project_dir / "backup_old.php").exists()

    # rollback
    backup_dir = _find_backup_dir(patched_backup_root)
    _invoke_rollback(runner, backup_dir, project_dir)

    assert (project_dir / "backup_old.php").exists(), (
        "backup_old.php should be restored after rollback"
    )


def test_rollback_exit_code_0(runner, project_setup, patched_backup_root):
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"

    _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    _invoke_execute(runner, plan_path, project_dir, real=True)

    backup_dir = _find_backup_dir(patched_backup_root)
    result = _invoke_rollback(runner, backup_dir, project_dir)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Full pipeline test
# ---------------------------------------------------------------------------

def test_full_pipeline(runner, project_setup, patched_backup_root):
    """analyze → execute → rollback: deleted file should be restored."""
    report_path, project_dir = project_setup
    plan_path = project_dir.parent / "plan.json"
    html_path = project_dir.parent / "report.html"

    # Step 1: analyze
    result = _invoke_analyze(runner, report_path, project_dir, plan_path, html_path)
    assert result.exit_code == 0
    assert plan_path.exists()

    # Step 2: execute (real)
    result = _invoke_execute(runner, plan_path, project_dir, real=True)
    assert result.exit_code == 0
    assert not (project_dir / "backup_old.php").exists()

    # Step 3: rollback
    backup_dir = _find_backup_dir(patched_backup_root)
    result = _invoke_rollback(runner, backup_dir, project_dir)
    assert result.exit_code == 0

    # File restored
    assert (project_dir / "backup_old.php").exists(), (
        "backup_old.php should be restored after rollback"
    )
