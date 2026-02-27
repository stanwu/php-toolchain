# php-cleanup-toolkit (Codex README)

This repository provides a small CLI (run it as `python main.py …`, or install the optional `php-cleanup` wrapper) that:

- Loads a JSON code-metrics report (summary + per-file stats)
- Cross-validates the report against the project directory on disk
- Runs analyzers (vendor/duplicates/backups/complexity/structure)
- Produces an actionable plan (`action_plan.json`) plus an HTML report (`report.html`)
- Optionally executes the plan with backups and an interactive safety gate

## For beginners (copy/paste)

If you don't know Python or CLI tools, follow this section exactly.

### 0) What you need

- Python 3.11+ installed
- A terminal:
  - macOS: Terminal
  - Windows: PowerShell
  - Linux: your terminal app

### 1) Get into this repo folder

In your terminal, `cd` into the folder that contains this `README.md`.

Example:

```bash
cd /path/to/php-cleanup-toolkit
```

### 2) Create and activate a virtual environment (recommended)

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

Windows (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -U pip
```

### 3) Install the CLI (developer install)

This installs an optional `php-cleanup` command into the virtual environment (the README examples use `python main.py …` so they work even without installing).

```bash
python -m pip install -e .
python main.py --help
```

If you prefer the wrapper command, `php-cleanup --help` should work after the install above. If it doesn't, just use `python main.py …` (shown throughout this README).

Tip (Windows): you can use `py main.py …` instead of `python main.py …`.

### 4) Run analysis (safe: no file changes)

You need two inputs:

- `--report`: a JSON metrics report (see “Input report format” below)
- `--project-dir`: your PHP project folder on disk

Example (replace the paths with yours):

```bash
python main.py analyze \
  --report /path/to/report.json \
  --project-dir /path/to/your-php-project \
  --output-plan action_plan.json \
  --html-report report.html
```

Outputs:

- `action_plan.json`: what the tool *suggests* doing
- `report.html`: a human-readable HTML report you can open in a browser

### 5) Dry-run execution (still safe: no file changes)

```bash
python main.py execute --plan action_plan.json --project-dir /path/to/your-php-project
```

### 6) Execute for real (will change files)

Only do this after you reviewed `report.html` and `action_plan.json`.

```bash
python main.py execute --plan action_plan.json --project-dir /path/to/your-php-project --execute
```

Backups are created automatically (see `rollback` below).

### Path tips (common beginner issues)

- If your path has spaces, wrap it in quotes:
  - `--project-dir "/Users/you/My Projects/site"`
- Use absolute paths if you're unsure where you are.
- On Windows, prefer `C:\full\path\to\project` (PowerShell also accepts quoted paths).

## Installation

Prereqs: Python 3.11+.

```bash
python -m pip install -e .
python main.py --help
```

You can also run it without installing:

```bash
python main.py --help
```

## Quickstart (recommended flow)

1) Generate a plan + HTML report (no filesystem changes):

```bash
python main.py analyze \
  --report path/to/report.json \
  --project-dir path/to/php/project \
  --output-plan action_plan.json \
  --html-report report.html
```

2) Dry-run the executor (still no filesystem changes):

```bash
python main.py execute --plan action_plan.json --project-dir path/to/php/project
```

3) Execute for real (creates backups, may prompt):

```bash
python main.py execute --plan action_plan.json --project-dir path/to/php/project --execute
```

## Commands

### `analyze`

```bash
python main.py analyze --help
```

Key options:
- `--report FILE` (required): JSON metrics report.
- `--project-dir DIR` (required): PHP project root on disk.
- `--risk-level [low|medium|high]`: filters actions included in the output plan (default: `HIGH`).
- `--output-plan PATH`: where to write the plan JSON (default: `action_plan.json`).
- `--html-report PATH`: where to write the HTML report (default: `report.html`).

### `plan`

Loads an existing plan, prints a summary, and writes an HTML report.

```bash
python main.py plan --plan action_plan.json --html-report report.html
```

### `execute`

Applies a saved plan using a “safe executor”.

- Default is **dry-run** (logs what would happen; does not modify files).
- Use `--execute` to actually modify files.
- Backups are created under `~/.php-cleanup-backup/<UTC_TIMESTAMP>/` when executing for real.

```bash
python main.py execute --plan action_plan.json --project-dir path/to/php/project
python main.py execute --plan action_plan.json --project-dir path/to/php/project --execute
```

Safety notes:
- MEDIUM-risk actions are gated as a batch confirmation.
- HIGH-risk actions are gated per-action.
- In non-interactive contexts (no TTY), confirmations default to **deny**.

### `rollback`

Restores files from a backup directory created during `execute --execute`.

```bash
python main.py rollback \
  --backup-dir ~/.php-cleanup-backup/20260227T120000Z \
  --project-dir path/to/php/project
```

Notes:
- `rollback` requires `action_log.json` inside the backup directory.
- The persisted rollback log is intended for `DELETE` and `MOVE` actions; it does not necessarily cover every mutation type.

## Input report format (JSON)

The CLI expects a JSON object with:

- `summary`: small aggregate info
- `files`: mapping of relative file path → metrics

Minimal example:

```json
{
  "summary": {
    "total_files": 6,
    "total_branches": 15,
    "most_complex": [{"file": "saas/service.php", "max_depth": 5, "total_branches": 10}]
  },
  "files": {
    "index.php": {"max_depth": 1, "total_branches": 2},
    "vendor/autoload.php": {"max_depth": 0, "total_branches": 0}
  }
}
```

`files` entries may contain additional details (e.g. `branches`, `functions`); the loader only requires `max_depth` and `total_branches`.

## Scenario examples

### 1) Conservative plan for a large repo

Only include low-risk actions in the saved plan:

```bash
python main.py analyze \
  --report report.json \
  --project-dir . \
  --risk-level LOW \
  --output-plan action_plan.low.json \
  --html-report report.low.html
```

### 2) Generate HTML later from a saved plan

Useful if you want to re-render a report (e.g. after sharing the plan JSON):

```bash
python main.py plan --plan action_plan.json --html-report report.html
```

### 3) CI usage (no prompts, no mutations)

Run analysis and produce artifacts without changing the repo:

```bash
python main.py analyze --report report.json --project-dir . --output-plan action_plan.json --html-report report.html
python main.py execute --plan action_plan.json --project-dir .
```

### 4) Real execution with backups + rollback

```bash
python main.py execute --plan action_plan.json --project-dir . --execute
ls -la ~/.php-cleanup-backup
python main.py rollback --backup-dir ~/.php-cleanup-backup/<timestamp> --project-dir .
```

### 5) Debugging analyzer behavior

Enable debug logging (and optionally capture logs):

```bash
python main.py --verbose analyze --report report.json --project-dir . 2>debug.log
```

## Troubleshooting

- “Malformed JSON…”: validate the report JSON and ensure it contains top-level `summary` and `files`.
- “Path traversal detected…”: the report contains `..` segments in a file key; fix the report generator.
- Missing `action_log.json` during rollback: only `execute --execute` writes a rollback-compatible log into the backup directory.

### “php-cleanup: command not found”

Use `python main.py …` instead (or `py main.py …` on Windows). The `php-cleanup` command only exists if it was installed into the currently-active Python environment.
