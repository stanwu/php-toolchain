# PHP Cleanup Toolkit

A safe, step-by-step assistant that scans your PHP project, finds files that
are no longer needed (old backups, duplicate copies, vendor libraries, overly
tangled code), and helps you delete or reorganize them — **without ever
touching a file you have not reviewed first**.

---

## Table of Contents

1. [What Does This Tool Do?](#1-what-does-this-tool-do)
2. [How It Keeps Your Files Safe](#2-how-it-keeps-your-files-safe)
3. [Before You Start — Requirements](#3-before-you-start--requirements)
4. [Installation](#4-installation)
5. [The Three-Step Workflow](#5-the-three-step-workflow)
   - [Step 1 — Scan: Build the Report](#step-1--scan-build-the-report)
   - [Step 2 — Analyze: Understand What Can Be Cleaned](#step-2--analyze-understand-what-can-be-cleaned)
   - [Step 3 — Execute: Actually Make the Changes](#step-3--execute-actually-make-the-changes)
   - [Bonus Step — Rollback: Undo Everything](#bonus-step--rollback-undo-everything)
6. [Reading the Terminal Output](#6-reading-the-terminal-output)
7. [Reading the HTML Report](#7-reading-the-html-report)
8. [Understanding Risk Levels](#8-understanding-risk-levels)
9. [Understanding Action Types](#9-understanding-action-types)
10. [What the Tool Looks For](#10-what-the-tool-looks-for)
11. [All Command Options](#11-all-command-options)
12. [Worked Example: A Messy Legacy PHP Site](#12-worked-example-a-messy-legacy-php-site)
13. [Frequently Asked Questions](#13-frequently-asked-questions)
14. [Glossary](#14-glossary)

---

## 1. What Does This Tool Do?

Over time, PHP projects accumulate clutter:

| Problem | Example |
|---------|---------|
| Old backup copies of files | `config_backup.php`, `index_OLD.php`, `style.css~` |
| Duplicate files scattered in different folders | `functions.php` in three different directories, all identical |
| Vendor / library folders committed to version control | `vendor/`, `node_modules/` checked into Git |
| Code files that are so deeply nested they are nearly impossible to maintain | A PHP file with 12 levels of `if`/`else` nesting |
| Directories that look suspiciously similar | `modules/` and `modules_backup/` containing almost the same files |

This toolkit:

1. **Reads** a JSON scan report about your project (produced by a compatible scanner tool that outputs the expected JSON format).
2. **Analyzes** the report to build a prioritized list of cleanup actions.
3. **Shows you** exactly what it plans to do, with a clear risk rating for every action.
4. **Executes** only what you approve — and always keeps a backup first.
5. **Rolls back** everything if something looks wrong afterward.

> **Nothing is deleted unless you explicitly run the execute command with the
> `--execute` flag.** The default mode is always a safe preview ("dry-run").

---

## 2. How It Keeps Your Files Safe

Before touching any file, the toolkit:

- **Hard-copies every file** to a personal backup folder:
  `~/.php-cleanup-backup/<timestamp>/`
- **Records every action** taken in an `action_log.json` file inside that
  backup folder.
- **Lets you roll back** to the exact state before cleanup with one command.

Think of it like a "Recycle Bin" that remembers the exact original location of
every file.

---

## 3. Before You Start — Requirements

You need the following installed on your computer. If you are not sure whether
they are installed, paste the check commands into your terminal.

| Requirement | Minimum Version | Check Command |
|-------------|-----------------|---------------|
| Python | 3.11 | `python3 --version` |
| pip | any recent | `pip3 --version` |

You also need a **JSON scan report** for your PHP project. This report is
produced by a compatible scanner tool (not included — see
[Step 1](#step-1--scan-build-the-report) for the expected format).

---

## 4. Installation

Open a terminal, go to the folder that contains this toolkit, then run:

```bash
# Go into the toolkit folder
cd /path/to/PHP_toolchain/claude

# Create a private Python environment (keeps this tool isolated)
python3 -m venv .venv

# Activate the environment
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows (use this line instead)

# Install the toolkit and its dependencies
pip install -e .
```

After installation, verify it works:

```bash
python main.py --help
```

You should see:

```
Usage: python main.py [OPTIONS] COMMAND [ARGS]...

  PHP Cleanup Toolkit — analyze, plan, execute, and rollback PHP project cleanups.

Commands:
  analyze   Load JSON report + scan disk → run all analyzers → save plan.
  execute   Load a saved plan → run safe_executor (dry-run unless --execute).
  rollback  Restore files from a backup directory created by execute.
```

> **Tip:** If you ran `pip install -e .`, you can also use the shorthand
> `php-cleanup` instead of `python main.py` — both are equivalent.

> **Each time you open a new terminal window** you must re-activate the
> environment first:
> ```bash
> source /path/to/PHP_toolchain/claude/.venv/bin/activate
> ```

---

## 5. The Three-Step Workflow

```
PHP project on disk
       │
       ▼
┌─────────────────┐
│  STEP 1: SCAN   │  (Your scanner tool — run once)
│  Produces       │
│  report.json    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ STEP 2: ANALYZE │  python main.py analyze …
│  Produces       │
│  action_plan.json
│  + report.html  │
└────────┬────────┘
         │ You review plan and HTML report
         ▼
┌─────────────────┐
│ STEP 3: EXECUTE │  python main.py execute … [--execute]
│  Cleans files   │
│  Keeps backup   │
└────────┬────────┘
         │ If something looks wrong:
         ▼
┌─────────────────┐
│    ROLLBACK     │  python main.py rollback …
│  Restores files │
└─────────────────┘
```

---

### Step 1 — Scan: Build the Report

The cleanup toolkit reads a JSON file produced by **a scanner tool of your choice** (not included in this toolkit). The scanner must parse your PHP source code and record complexity metrics in the format shown below. Run it first to create `report.json`.

```bash
# This command depends entirely on which scanner tool you use.
# Consult your scanner's documentation for the exact syntax.
<your-scanner> --project /var/www/mysite --output report.json
```

The `report.json` file looks like this (simplified):

```json
{
  "summary": {
    "total_files": 342,
    "total_branches": 1850
  },
  "files": {
    "app-content/themes/mytheme/functions.php": {
      "max_depth": 8,
      "total_branches": 64
    },
    "includes/config_backup.php": {
      "max_depth": 1,
      "total_branches": 2
    }
  }
}
```

You do not need to read or edit this file manually.

---

### Step 2 — Analyze: Understand What Can Be Cleaned

This is the main analysis step. It reads the JSON report, scans the actual
files on your disk, runs five detection checks in parallel, and produces:

- A **colored summary** in the terminal
- A **`action_plan.json`** file (the list of proposed changes)
- A **`report.html`** file (open in any browser for a visual overview)

**Basic usage:**

```bash
python main.py analyze \
  --report /path/to/report.json \
  --project-dir /var/www/mysite
```

**With all options spelled out:**

```bash
python main.py analyze \
  --report    /path/to/report.json \
  --project-dir /var/www/mysite \
  --risk-level  HIGH \
  --output-plan action_plan.json \
  --html-report report.html
```

**Real-world example** (legacy PHP site stored at `/var/www/mysite`):

```bash
python main.py analyze \
  --report    ~/scans/mysite_report.json \
  --project-dir /var/www/mysite \
  --risk-level  MEDIUM \
  --output-plan ~/scans/cleanup_plan.json \
  --html-report ~/scans/cleanup_report.html
```

After a few seconds you will see output similar to:

```
Analyzer Results
  ✔ VendorAnalyzer      — 2 actions
  ✔ DuplicateAnalyzer   — 14 actions
  ✔ BackupAnalyzer      — 31 actions
  ✔ ComplexityAnalyzer  — 7 actions
  ✔ StructureAnalyzer   — 3 actions

No conflicts detected.

Cleanup Plan Summary
  Total actions : 57
  LOW risk      : 33
  MEDIUM risk   : 19
  HIGH risk      : 5

┌──────────────────────────────────────────────────────────────────────┐
│  #  │ Type           │ Source                         │ Risk  │ Reason│
├──────────────────────────────────────────────────────────────────────┤
│  1  │ 🗑 DELETE      │ uploads/img_backup.php         │ LOW   │ Backup│
│  2  │ 🗑 DELETE      │ includes/old_functions.php~    │ LOW   │ Backup│
│  3  │ 📋 GITIGNORE   │ vendor                         │ LOW   │ Vendor│
│  4  │ 🗑 DELETE      │ app-content/cache/page-dup.php  │ MEDIUM│ Dupe  │
…
└──────────────────────────────────────────────────────────────────────┘

Plan saved → ~/scans/cleanup_plan.json
HTML report → ~/scans/cleanup_report.html
```

> **Nothing has been changed yet.** This step is read-only.

---

### Step 3 — Execute: Actually Make the Changes

First, **open `report.html` in your browser** and review the plan. When you
are satisfied, run the execute command.

**Preview mode (safe, no changes — always run this first):**

```bash
python main.py execute \
  --plan        ~/scans/cleanup_plan.json \
  --project-dir /var/www/mysite
```

This prints exactly what *would* happen without modifying anything:

```
[DRY-RUN] DELETE  uploads/img_backup.php
[DRY-RUN] DELETE  includes/old_functions.php~
[DRY-RUN] GITIGNORE  vendor/
…
Executed: 0  Skipped: 0  Errors: 0
```

**Live mode (actually deletes / moves files):**

```bash
python main.py execute \
  --plan        ~/scans/cleanup_plan.json \
  --project-dir /var/www/mysite \
  --execute
```

Sample output:

```
--- .gitignore diff ---
+++ .gitignore additions (2026-02-27 14:32:11)
+/vendor/
+/node_modules/

Backup dir : /Users/yourname/.php-cleanup-backup/20260227_143211
Action log : /Users/yourname/.php-cleanup-backup/20260227_143211/action_log.json

Executed: 45  Skipped: 2  Errors: 0
```

Write down the **Backup dir** path — you will need it if you want to undo.

---

### Bonus Step — Rollback: Undo Everything

If you discover something was deleted by mistake, restore all files with:

```bash
python main.py rollback \
  --backup-dir  /Users/yourname/.php-cleanup-backup/20260227_143211 \
  --project-dir /var/www/mysite
```

Output:

```
Restored 45 file(s) from /Users/yourname/.php-cleanup-backup/20260227_143211
```

Every file is put back in its exact original location.

---

## 6. Reading the Terminal Output

### Analyzer Results section

```
✔ BackupAnalyzer  — 31 actions
```

Each line tells you which detector ran and how many cleanup candidates it
found. Five detectors always run:

| Detector | What it finds |
|----------|---------------|
| VendorAnalyzer | `vendor/`, `node_modules/`, `bower_components/` directories |
| DuplicateAnalyzer | Files with identical content existing in multiple locations |
| BackupAnalyzer | Files with backup-like names (e.g., `_old`, `.bak`, `~`, `-20250115`) |
| ComplexityAnalyzer | PHP files that are too deeply nested to maintain safely |
| StructureAnalyzer | Directory pairs that look suspiciously alike |

### Summary Cards section

```
Total actions : 57
LOW risk      : 33
MEDIUM risk   : 19
HIGH risk      : 5
```

### Action Table section

| Column | Meaning |
|--------|---------|
| # | Row number |
| Type | What would happen (DELETE, MOVE, GITIGNORE, REPORT) |
| Source | The file or folder targeted |
| Risk | How confident the tool is that this is safe |
| Reason | Plain-English explanation of why this action was suggested |

Icon legend in the Type column:

| Icon | Action |
|------|--------|
| 🗑 | DELETE — remove the file |
| ➡ | MOVE — relocate the file |
| 📋 | ADD_GITIGNORE — add entry to `.gitignore` |
| 📊 | REPORT_ONLY — flag for manual review, no file touched |

---

## 7. Reading the HTML Report

Open `report.html` in any web browser (Chrome, Safari, Firefox, Edge).

The report has four sections:

### Summary Cards (top)
Four colored boxes showing total, LOW, MEDIUM, and HIGH action counts.
Click the **LOW / MEDIUM / HIGH** buttons to filter the table below.

### Action Table
A filterable table of every proposed action. Rows marked with ⚠ have a
conflict note — read the reason column carefully before approving those.

### Complexity Heatmap
A color-coded list of your most complex PHP files. Deep red = very complex.
These files are flagged for **your** review — the tool never auto-deletes code
that is actively used.

| Color | Meaning |
|-------|---------|
| Light yellow | Moderately complex (worth refactoring eventually) |
| Orange | Highly complex (consider refactoring soon) |
| Red | Critically complex (hard to maintain, high bug risk) |

### Directory Tree
All actions grouped by the top-level folder they affect. Useful for spotting
when an entire sub-directory should simply be removed.

---

## 8. Understanding Risk Levels

Every action has a risk label: **LOW**, **MEDIUM**, or **HIGH**.

| Level | What it means | Example |
|-------|--------------|---------|
| **LOW** | Very safe to delete — the file is clearly a throwaway backup with an obvious name | `index.php~`, `config_bak.php`, `vendor/` library folder |
| **MEDIUM** | Probably safe — strong evidence, but worth a quick look | A file named `functions-20240801.php` (date-stamped copy), or a duplicate where there is a clear original |
| **HIGH** | Needs your attention — something unusual or ambiguous | Two files that are identical but it is not obvious which one is the "real" one; or code that is extremely complex |

**The `--risk-level` option** in the `analyze` command controls the **maximum
risk level included in the plan**. Examples:

```bash
# Only include actions we are very confident about
--risk-level LOW

# Include LOW and MEDIUM (default is HIGH = include everything)
--risk-level MEDIUM

# Include everything (default)
--risk-level HIGH
```

Start with `--risk-level LOW` if you want the most conservative run.

---

## 9. Understanding Action Types

### DELETE
The file will be removed from disk.
- A backup copy is always saved first.
- Only files are deleted — never a directory that still contains files.
- Empty parent directories are cleaned up automatically.

### MOVE
The file will be relocated to a new path within the project.
- Used when a file should be archived rather than destroyed.
- Backup of the original is kept.

### ADD_GITIGNORE
A line like `/vendor/` will be added to your project's `.gitignore` file.
- This tells Git to stop tracking that folder in future commits.
- No files are deleted.
- The toolkit shows you a "diff" (before/after comparison) before writing.

### REPORT_ONLY
No file is touched at all.
- Used for complex code files and structurally similar directories.
- The action appears in the report so you can review it manually.
- Think of it as a "yellow sticky note" on a file.

---

## 10. What the Tool Looks For

### Backup Files (BackupAnalyzer)

Files are flagged if their name contains known backup patterns:

| Pattern | Examples | Risk |
|---------|---------|------|
| `_backup`, `_bak`, `_old` in name | `db_backup.php`, `header_old.php` | LOW |
| Ends with `.bak` or `.orig` | `config.php.bak`, `style.css.orig` | LOW |
| Ends with `~` (editor temp) | `functions.php~` | LOW |
| Starts with `copy_of_` | `copy_of_index.php` | LOW |
| Date stamp `YYYYMMDD` in name | `upload-20250312.php` | MEDIUM |
| `_copy`, `_test` in name | `header_copy.php`, `checkout_test.php` | MEDIUM |
| Prefix `x---` | `x---deprecated.php` | MEDIUM |

### Duplicate Files (DuplicateAnalyzer)

Every PHP file is fingerprinted using SHA-256 (a mathematical hash of the
file's content). Two files with the same fingerprint are byte-for-byte
identical. When duplicates are found:

- The most likely "original" is kept (scored by path depth, name patterns, etc.).
- The copies are marked for deletion.
- If it is ambiguous which is the original, both are marked HIGH risk.

### Vendor Directories (VendorAnalyzer)

Directories named `vendor/`, `node_modules/`, or `bower_components/` contain
third-party library code that is often hundreds of megabytes. They should be
listed in `.gitignore` so Git does not track them. The toolkit adds the
appropriate `.gitignore` entries automatically.

### Complex Code (ComplexityAnalyzer)

PHP files are scored by two measures from the JSON report:

| Measure | Meaning |
|---------|---------|
| `max_depth` | How many levels of `if`/`else`/`for`/`switch` are nested inside each other |
| `total_branches` | Total number of decision points (`if`, `elseif`, `case`, `while`, etc.) in the file |

| Severity | max_depth | total_branches | Risk |
|----------|-----------|-----------------|------|
| Moderate | ≥ 5 | ≥ 20 | LOW |
| High | ≥ 10 | ≥ 50 | MEDIUM |
| Critical | ≥ 15 | ≥ 100 | HIGH |

These files are never auto-deleted — they appear as **REPORT_ONLY** so you can
decide whether to refactor them.

### Similar Directories (StructureAnalyzer)

Two directories are flagged as suspicious if they share ≥ 70 % of their
filenames (by Jaccard similarity). This catches patterns like:

```
themes/storefront/       ← real theme
themes/storefront_bak/   ← old backup of the same theme
```

These are flagged as **REPORT_ONLY** because deciding which to keep requires
human judgment.

---

## 11. All Command Options

### `python main.py analyze`

> Shorthand after `pip install -e .`: `php-cleanup analyze`

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--report` | Yes | — | Path to the JSON scan report |
| `--project-dir` | Yes | — | Root folder of your PHP project |
| `--risk-level` | No | `HIGH` | Max risk to include: `LOW`, `MEDIUM`, or `HIGH` |
| `--output-plan` | No | `action_plan.json` | Where to save the action plan |
| `--html-report` | No | `report.html` | Where to save the HTML report |

### `python main.py execute`

> Shorthand after `pip install -e .`: `php-cleanup execute`

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--plan` | Yes | — | Path to the `action_plan.json` from the analyze step |
| `--project-dir` | Yes | — | Root folder of your PHP project |
| `--execute` | No | off | Add this flag to actually make changes. Without it, only a preview is shown. |

### `python main.py rollback`

> Shorthand after `pip install -e .`: `php-cleanup rollback`

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--backup-dir` | Yes | — | Path printed by the execute command (e.g., `~/.php-cleanup-backup/20260227_143211`) |
| `--project-dir` | Yes | — | Root folder of your PHP project |

---

## 12. Worked Example: A Messy Legacy PHP Site

**Scenario:** You have a legacy PHP site at `/var/www/myblog`. Over five years
it has accumulated old backup files, a committed `node_modules/` folder, and
several functions files that got duplicated across themes.

### Step A — Generate the scan report

```bash
php scanner.php --project /var/www/myblog --output ~/myblog_report.json
```

### Step B — Analyze (conservative first pass)

Start with only LOW-risk actions so you can get comfortable with the tool:

```bash
python main.py analyze \
  --report      ~/myblog_report.json \
  --project-dir /var/www/myblog \
  --risk-level  LOW \
  --output-plan ~/myblog_plan_low.json \
  --html-report ~/myblog_report_low.html
```

Terminal output:

```
Analyzer Results
  ✔ VendorAnalyzer      — 1 action
  ✔ DuplicateAnalyzer   — 3 actions
  ✔ BackupAnalyzer      — 18 actions
  ✔ ComplexityAnalyzer  — 0 actions
  ✔ StructureAnalyzer   — 0 actions

No conflicts detected.

Cleanup Plan Summary
  Total actions : 22
  LOW risk      : 22
  MEDIUM risk   :  0
  HIGH risk      :  0
```

### Step C — Preview the changes

```bash
python main.py execute \
  --plan        ~/myblog_plan_low.json \
  --project-dir /var/www/myblog
```

```
[DRY-RUN] GITIGNORE  node_modules/
[DRY-RUN] DELETE  app-content/themes/old-theme/functions.php.bak
[DRY-RUN] DELETE  app-content/uploads/backup_header.php
[DRY-RUN] DELETE  app-content/uploads/backup_header.php~
…
Executed: 0  Skipped: 0  Errors: 0
```

Everything looks right.

### Step D — Execute (for real)

```bash
python main.py execute \
  --plan        ~/myblog_plan_low.json \
  --project-dir /var/www/myblog \
  --execute
```

```
--- .gitignore diff ---
+++ .gitignore additions (2026-02-27 14:45:00)
+/node_modules/

Backup dir : /Users/me/.php-cleanup-backup/20260227_144500
Action log : /Users/me/.php-cleanup-backup/20260227_144500/action_log.json

Executed: 22  Skipped: 0  Errors: 0
```

### Step E — Check the site works, then do MEDIUM risk

```bash
python main.py analyze \
  --report      ~/myblog_report.json \
  --project-dir /var/www/myblog \
  --risk-level  MEDIUM \
  --output-plan ~/myblog_plan_medium.json \
  --html-report ~/myblog_report_medium.html
```

Open `~/myblog_report_medium.html`, review the duplicate-file entries, then
repeat Steps C and D.

### Step F — Rollback (if anything broke)

```bash
python main.py rollback \
  --backup-dir  /Users/me/.php-cleanup-backup/20260227_144500 \
  --project-dir /var/www/myblog
```

```
Restored 22 file(s) from /Users/me/.php-cleanup-backup/20260227_144500
```

---

## 13. Frequently Asked Questions

**Q: Will this tool break my live website?**

No action is taken until you run `execute --execute`. Even then, every file
is backed up first. If anything goes wrong, `rollback` restores everything in
seconds.

**Q: Do I need to understand Python to use this?**

No. Once the environment is set up (see [Installation](#4-installation)), you
only need to run `python main.py` in your terminal. No Python knowledge is
required.

**Q: The tool flagged a file I want to keep. Can I skip it?**

Yes — edit `action_plan.json` in a text editor and delete the line (the entire
`{ … }` block) for the action you want to skip, then save. The execute command
reads the plan from that file.

**Q: Can I run the tool on a production server?**

It is safest to run cleanup on a local copy or a staging environment first.
Copy your project to your local machine, run the toolkit, verify the results,
then apply the same changes on the server manually (or re-run the toolkit
there with the same plan).

**Q: The HTML report shows ⚠ next to some rows. What does that mean?**

Those actions had a conflict that the toolkit detected and resolved
automatically. For example, if both a DELETE and a MOVE were proposed for the
same file, the DELETE was removed and the MOVE was kept (promoted to HIGH risk
for your review). The reason column explains exactly what happened.

**Q: How big a project can this handle?**

The toolkit uses streaming JSON parsing, so it can handle projects with tens of
thousands of files without running out of memory. The only practical limit is
disk space for the backup copies.

**Q: Where are my backups stored?**

In your home directory: `~/.php-cleanup-backup/<timestamp>/`

Each run creates a new timestamped subfolder. The toolkit never deletes old
backup folders — you can remove them manually once you are satisfied with the
cleanup.

**Q: Can I run the analyze step multiple times?**

Yes. The analyze step is completely read-only and can be run as many times as
you like. Each run overwrites `action_plan.json` and `report.html` (unless you
specify different output paths with `--output-plan` and `--html-report`).

**Q: What does "conflict" mean?**

A conflict occurs when two different analysis rules suggest contradictory
actions for the same file — for example, one rule says "delete this file" while
another says "move this file". The conflict resolver picks the safer option and
marks it HIGH risk so you are aware.

---

## 14. Glossary

| Term | Plain-English Meaning |
|------|-----------------------|
| **Action plan** | The list of proposed changes saved as `action_plan.json` |
| **Analyzer** | One of the five detectors that looks for a specific type of problem |
| **Backup (toolkit)** | Hard-copy of your original files saved to `~/.php-cleanup-backup/` before any changes |
| **Branches (code)** | Decision points in PHP code: every `if`, `else`, `elseif`, `for`, `while`, `switch case` |
| **Dry-run** | Preview mode — shows what *would* happen without touching any files |
| **Duplicate** | Two or more files with byte-for-byte identical content |
| **Fingerprint / SHA-256** | A unique 64-character code derived from a file's content; two files with the same fingerprint are identical |
| **Jaccard similarity** | A percentage measuring how many filenames two directories share |
| **JSON report** | The input file produced by the PHP scanner, describing every file's complexity metrics |
| **.gitignore** | A text file that tells Git which files/folders to ignore (not track) |
| **Hard-link** | An efficient way to backup a file that shares storage with the original until one of them changes |
| **max_depth** | The deepest level of nesting inside a PHP function (e.g., an `if` inside a `for` inside another `if` = depth 3) |
| **REPORT_ONLY** | An action type that flags a file for human review without modifying it |
| **Risk level** | LOW / MEDIUM / HIGH — how confident the toolkit is that an action is safe |
| **Rollback** | Restoring all files to exactly how they were before an execute run |
| **Vendor directory** | A folder (`vendor/`, `node_modules/`) containing third-party library code you did not write |
