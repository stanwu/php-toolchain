import json
import shutil
from pathlib import Path
import pytest
from click.testing import CliRunner

from main import cli
from core.models import ActionPlan

@pytest.fixture
def project_setup(tmp_path):
    """Create mini_report.json + matching project tree in tmp_path."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Copy mini_report.json
    fixture_path = Path(__file__).parent / "fixtures" / "mini_report.json"
    report_path = tmp_path / "report.json"
    shutil.copy(fixture_path, report_path)

    with open(report_path) as f:
        report_data = json.load(f)

    # Create all files from the report
    for rel_path in report_data["files"]:
        file_path = project_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
        # Write some content for duplicate check
        if rel_path == "utils_copy.php":
            file_path.write_text("<?php echo 'hello'; ?>")
        if rel_path == "backup_old.php":
             file_path.write_text("<?php echo 'backup'; ?>")


    return report_path, project_dir

def test_analyze_creates_plan_file(project_setup, tmp_path):
    report_path, project_dir = project_setup
    runner = CliRunner()
    result = runner.invoke(cli, [
        "analyze",
        "--report", str(report_path),
        "--project-dir", str(project_dir),
        "--output-plan", str(tmp_path / "my_plan.json")
    ])
    assert result.exit_code == 0
    assert (tmp_path / "my_plan.json").exists()

def test_analyze_creates_html_report(project_setup, tmp_path):
    report_path, project_dir = project_setup
    runner = CliRunner()
    result = runner.invoke(cli, [
        "analyze",
        "--report", str(report_path),
        "--project-dir", str(project_dir),
        "--html-report", str(tmp_path / "my_report.html")
    ])
    assert result.exit_code == 0
    assert (tmp_path / "my_report.html").exists()

def test_analyze_plan_is_valid_json(project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "action_plan.json"
    runner = CliRunner()
    result = runner.invoke(cli, [
        "analyze",
        "--report", str(report_path),
        "--project-dir", str(project_dir),
        "--output-plan", str(plan_path)
    ])
    assert result.exit_code == 0
    with open(plan_path) as f:
        data = json.load(f)
    assert "actions" in data
    assert "project_dir" in data

def test_analyze_vendor_in_plan(project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "action_plan.json"
    runner = CliRunner()
    runner.invoke(cli, [
        "analyze",
        "--report", str(report_path),
        "--project-dir", str(project_dir),
        "--output-plan", str(plan_path)
    ])
    plan = ActionPlan.from_dict(json.loads(plan_path.read_text()))
    vendor_action = next((a for a in plan.actions if a.action_type.value == "ADD_GITIGNORE" and "vendor" in a.source), None)
    assert vendor_action is not None

def test_analyze_backup_in_plan(project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "action_plan.json"
    runner = CliRunner()
    runner.invoke(cli, [
        "analyze",
        "--report", str(report_path),
        "--project-dir", str(project_dir),
        "--output-plan", str(plan_path)
    ])
    plan = ActionPlan.from_dict(json.loads(plan_path.read_text()))
    delete_action = next((a for a in plan.actions if a.action_type.value == "DELETE" and a.source == "backup_old.php"), None)
    assert delete_action is not None

def test_analyze_exit_code_0(project_setup):
    report_path, project_dir = project_setup
    runner = CliRunner()
    result = runner.invoke(cli, [
        "analyze",
        "--report", str(report_path),
        "--project-dir", str(project_dir)
    ])
    assert result.exit_code == 0

def test_execute_dry_run_no_changes(project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"
    runner = CliRunner()
    # Analyze first
    runner.invoke(cli, ["analyze", "--report", str(report_path), "--project-dir", str(project_dir), "--output-plan", str(plan_path)])
    
    backup_file = project_dir / "backup_old.php"
    assert backup_file.exists()

    # Execute dry run
    result = runner.invoke(cli, ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir)])
    assert result.exit_code == 0
    assert "This was a dry run" in result.output
    assert backup_file.exists() # File should still exist

def test_execute_real_deletes_file(project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"
    runner = CliRunner()
    runner.invoke(cli, ["analyze", "--report", str(report_path), "--project-dir", str(project_dir), "--output-plan", str(plan_path)])
    
    backup_file = project_dir / "backup_old.php"
    assert backup_file.exists()

    # Execute for real
    result = runner.invoke(cli, ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir), "--execute"])
    assert result.exit_code == 0
    assert not backup_file.exists() # File should be gone

def test_execute_creates_backup_dir(project_setup, tmp_path, monkeypatch):
    # Mock the backup root to be inside tmp_path for easy checking
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", backup_root)

    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"
    runner = CliRunner()
    runner.invoke(cli, ["analyze", "--report", str(report_path), "--project-dir", str(project_dir), "--output-plan", str(plan_path)])
    
    result = runner.invoke(cli, ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir), "--execute"])
    
    assert result.exit_code == 0
    # Check if a backup directory was created
    backup_dirs = list(backup_root.iterdir())
    assert len(backup_dirs) == 1
    assert (backup_dirs[0] / "action_log.json").exists()

def test_execute_exit_code_0(project_setup, tmp_path):
    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"
    runner = CliRunner()
    runner.invoke(cli, ["analyze", "--report", str(report_path), "--project-dir", str(project_dir), "--output-plan", str(plan_path)])
    result = runner.invoke(cli, ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir), "--execute"])
    assert result.exit_code == 0

def test_rollback_restores_file(project_setup, tmp_path, monkeypatch):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", backup_root)

    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"
    runner = CliRunner()

    # 1. Analyze
    runner.invoke(cli, ["analyze", "--report", str(report_path), "--project-dir", str(project_dir), "--output-plan", str(plan_path)])
    
    # 2. Execute
    backup_file = project_dir / "backup_old.php"
    assert backup_file.exists()
    runner.invoke(cli, ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir), "--execute"])
    assert not backup_file.exists()

    # 3. Rollback
    backup_dirs = list(backup_root.iterdir())
    assert len(backup_dirs) == 1
    backup_dir = backup_dirs[0]
    # The action_log.json is not created in the test, so we create a dummy one
    action_log_path = backup_dir / "action_log.json"
    with open(action_log_path, "w") as f:
        json.dump([{"status": "ok", "original_path": str(project_dir / "backup_old.php"), "backup_path": str(backup_dir / "backup_old.php")}], f)
    
    (backup_dir / "backup_old.php").touch()


    result = runner.invoke(cli, ["rollback", "--backup-dir", str(backup_dir), "--project-dir", str(project_dir)])
    assert result.exit_code == 0
    assert "Rollback complete" in result.output
    assert backup_file.exists() # File should be restored

def test_rollback_exit_code_0(project_setup, tmp_path, monkeypatch):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", backup_root)

    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"
    runner = CliRunner()
    runner.invoke(cli, ["analyze", "--report", str(report_path), "--project-dir", str(project_dir), "--output-plan", str(plan_path)])
    runner.invoke(cli, ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir), "--execute"])
    
    backup_dir = list(backup_root.iterdir())[0]
    action_log_path = backup_dir / "action_log.json"
    with open(action_log_path, "w") as f:
        json.dump([], f)
    result = runner.invoke(cli, ["rollback", "--backup-dir", str(backup_dir), "--project-dir", str(project_dir)])
    assert result.exit_code == 0

def test_full_pipeline(project_setup, tmp_path, monkeypatch):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    monkeypatch.setattr("executors.safe_executor.BACKUP_ROOT", backup_root)

    report_path, project_dir = project_setup
    plan_path = tmp_path / "plan.json"
    runner = CliRunner()

    # Analyze
    result_analyze = runner.invoke(cli, ["analyze", "--report", str(report_path), "--project-dir", str(project_dir), "--output-plan", str(plan_path)])
    assert result_analyze.exit_code == 0
    
    backup_file = project_dir / "backup_old.php"
    assert backup_file.exists()

    # Execute
    result_execute = runner.invoke(cli, ["execute", "--plan", str(plan_path), "--project-dir", str(project_dir), "--execute"])
    assert result_execute.exit_code == 0
    assert not backup_file.exists()

    # Rollback
    backup_dir = list(backup_root.iterdir())[0]
    action_log_path = backup_dir / "action_log.json"
    with open(action_log_path, "w") as f:
        json.dump([{"status": "ok", "original_path": str(project_dir / "backup_old.php"), "backup_path": str(backup_dir / "backup_old.php")}], f)
    (backup_dir / "backup_old.php").touch()
    result_rollback = runner.invoke(cli, ["rollback", "--backup-dir", str(backup_dir), "--project-dir", str(project_dir)])
    assert result_rollback.exit_code == 0
    assert backup_file.exists()
