# Prompt 16 — main.py + Integration
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** ALL previous modules (01–15) complete and passing tests.

---

## Task

Implement `main.py` and `pyproject.toml`.
Wire all modules together into a single `click`-based CLI.
Then write **integration tests** that run the full pipeline end-to-end.

---

## CLI Design

```
php-cleanup <subcommand> [options]

Subcommands:
  analyze   Load JSON + scan disk → run all analyzers → save plan
  plan      Load a saved plan → show summary + HTML report
  execute   Load a saved plan → run safe_executor
  rollback  Restore files from a backup directory
```

### analyze

```bash
php-cleanup analyze \
  --report analysis_report.json \
  --project-dir ./my-php-project \
  [--risk-level MEDIUM]          # filter: only include actions up to this level
  [--output-plan action_plan.json]
  [--html-report report.html]
```

**Flow:**
1. `ReportLoader` → stream JSON
2. `DirectoryScanner` → cross-validate
3. Run 5 analyzers (parallel with `concurrent.futures.ThreadPoolExecutor`)
   Each analyzer receives the `records` dict as **read-only input** — no analyzer
   may mutate `FileRecord` fields or the dict itself during parallel execution.
   (`exists_on_disk` is set exclusively by `DirectoryScanner.cross_validate()` before
   the thread pool starts, and never written again.)
4. `ActionPlanner.build_plan()`
5. `ConflictResolver.resolve()`
6. `CLIReporter.print_analyzer_results()` + `print_summary()`
7. Save plan to `--output-plan` (JSON via `ActionPlan.to_dict()`)
8. `HTMLReporter.write()` to `--html-report`

### execute

```bash
php-cleanup execute \
  --plan action_plan.json \
  [--execute]                    # omit = dry-run
  [--project-dir ./my-php-project]
```

**Flow:**
1. Load plan from JSON (`ActionPlan.from_dict()`)
2. `GitignoreGen.apply()` for ADD_GITIGNORE actions
3. `SafeExecutor.execute()`
4. `CLIReporter.print_execution_log()`

### rollback

```bash
php-cleanup rollback \
  --backup-dir ~/.php-cleanup-backup/2026-02-26T10-00-00/
  [--project-dir ./my-php-project]
```

**Flow:**
1. Load `action_log.json` from backup dir
2. `FileOps.rollback()`
3. Print restored file count

---

## Implementation — main.py

```python
import click
import json
import concurrent.futures
from pathlib import Path

from core.loader import ReportLoader
from core.scanner import DirectoryScanner
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

@click.group()
def cli(): ...

@cli.command()
@click.option("--report", required=True, type=click.Path(exists=True))
@click.option("--project-dir", required=True, type=click.Path(exists=True))
@click.option("--risk-level", default="HIGH", type=click.Choice(["LOW","MEDIUM","HIGH"]))
@click.option("--output-plan", default="action_plan.json")
@click.option("--html-report", default="report.html")
def analyze(report, project_dir, risk_level, output_plan, html_report): ...

@cli.command()
@click.option("--plan", required=True, type=click.Path(exists=True))
@click.option("--project-dir", required=True, type=click.Path(exists=True))
@click.option("--execute", "do_execute", is_flag=True, default=False)
def execute(plan, project_dir, do_execute): ...

@cli.command()
@click.option("--backup-dir", required=True, type=click.Path(exists=True))
@click.option("--project-dir", required=True, type=click.Path(exists=True))
def rollback(backup_dir, project_dir): ...

if __name__ == "__main__":
    cli()
```

---

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "php-cleanup-toolkit"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "ijson>=3.2",
    "rich>=13.0",
    "click>=8.1",
]

[project.scripts]
php-cleanup = "main:cli"

[tool.pytest.ini_options]
testpaths = ["tests"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]
```

---

## Integration Tests — tests/test_integration.py

Use `tmp_path` + `click.testing.CliRunner` for full pipeline tests.
These tests use `mini_report.json` and a matching fake project directory.

```python
from click.testing import CliRunner
from main import cli

@pytest.fixture
def project_setup(tmp_path):
    """Create mini_report.json + matching project tree in tmp_path."""
    # Copy tests/fixtures/mini_report.json to tmp_path/report.json
    # Create all 6 files from mini_report in tmp_path/project/
    # Return (report_path, project_dir)
```

| Test name | What it checks |
|-----------|----------------|
| `test_analyze_creates_plan_file` | `action_plan.json` created after analyze |
| `test_analyze_creates_html_report` | `report.html` created after analyze |
| `test_analyze_plan_is_valid_json` | `action_plan.json` is parseable JSON |
| `test_analyze_vendor_in_plan` | ADD_GITIGNORE for `vendor` in plan |
| `test_analyze_backup_in_plan` | DELETE for `backup_old.php` in plan |
| `test_analyze_exit_code_0` | CLI exits with code 0 |
| `test_execute_dry_run_no_changes` | Files unchanged after dry-run execute |
| `test_execute_real_deletes_file` | `backup_old.php` deleted after real execute |
| `test_execute_creates_backup_dir` | `~/.php-cleanup-backup/` entry created |
| `test_execute_exit_code_0` | CLI exits with code 0 |
| `test_rollback_restores_file` | Deleted file restored after rollback |
| `test_rollback_exit_code_0` | CLI exits with code 0 |
| `test_full_pipeline` | analyze → execute → rollback → file restored |

---

## Final Verification

After all modules are implemented, run the **full test suite**:

```bash
# Install dependencies
pip install ijson rich click pytest

# Run all tests
pytest tests/ -v --tb=short

# Run integration tests only
pytest tests/test_integration.py -v

# Smoke test with real data (dry-run only)
php-cleanup analyze \
  --report ~/analysis_report.json \
  --project-dir ~/my-php-project \
  --output-plan /tmp/plan.json \
  --html-report /tmp/report.html

php-cleanup execute --plan /tmp/plan.json --project-dir ~/my-php-project
# (no --execute flag = dry-run)
```

**Expected result:**
- All unit tests pass (15 modules × ~10 tests each ≈ 150 tests)
- Integration tests pass (13 tests)
- Dry-run execute logs actions without touching any files

---

## Deliverables

1. `main.py`
2. `pyproject.toml`
3. `tests/test_integration.py`

**Verify:** `pytest tests/ -v` — all tests pass with 0 failures.
