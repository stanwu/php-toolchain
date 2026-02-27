# PHP Project Cleanup Toolkit — Design Plan

> Planning date: 2026-02-26
> Corresponding analysis report: `analysis_report.json` / `my-php-project_report.md`

---

## Feasibility Assessment

Fully feasible. `analysis_report.json` already contains all the analysis data needed; the toolkit only has to "read + scan the directory + execute actions".

---

## Toolkit Architecture (5 Layers)

```
php-cleanup-toolkit/
├── core/           # Data loading layer
├── analyzers/      # Analysis layer (5 modules)
├── planners/       # Decision layer
├── executors/      # Execution layer (with safety mechanisms)
├── reporters/      # Report output layer
└── main.py         # CLI entry point
```

---

## Module Responsibilities by Layer

| Layer | Module | Responsibility |
|-------|--------|---------------|
| **Core** | `loader.py` | Stream-parse the 32 MB JSON using `ijson` to avoid loading the entire file into memory at once |
| | `scanner.py` | Scan the actual directory, cross-validate against the JSON, and flag ghost files and newly added files |
| | `models.py` | Define shared data models (`FileRecord`, `DuplicateGroup`, `Action`) |
| **Analyzers** | `vendor_analyzer.py` | Identify vendor directories, calculate their size ratio, and generate `.gitignore` recommendations |
| | `duplicate_analyzer.py` | Use MD5 hashing plus path-semantic inference to determine which copy is the original and which is the duplicate |
| | `backup_analyzer.py` | Use regular expressions to identify stale backup files and classify them as "safe to delete" vs. "requires confirmation" |
| | `complexity_analyzer.py` | Extract the high-complexity file list from the JSON and produce a refactoring priority order |
| | `structure_analyzer.py` | Use Jaccard similarity to find semantically duplicate directory pairs |
| **Planners** | `action_planner.py` | Merge the five analysis reports into an ordered `Action` list, sorted by risk from lowest to highest |
| | `conflict_resolver.py` | Detect conflicts between actions (e.g. action A wants to move a file while action B wants to delete it) |
| **Executors** | `safe_executor.py` | Safety gate: dry-run is on by default; HIGH RISK actions require manual confirmation one by one |
| | `file_ops.py` | Perform actual move/delete operations, logging every step and supporting rollback |
| | `gitignore_gen.py` | Generate or update `.gitignore`, outputting a unified diff for review before writing |
| **Reporters** | `cli_reporter.py` | Colour-coded terminal output with progress bars |
| | `html_reporter.py` | Static HTML report with a complexity heatmap and an interactive directory tree |

---

## Module Dependency Graph

```
analysis_report.json ──→ core/loader.py ──┐
                                           ├──→ analyzers/ (5 modules, run in parallel) ──→ planners/action_planner.py
project_dir ──────────→ core/scanner.py ──┘              ↓                                              ↓
                                                   reporters/                         planners/conflict_resolver.py
                                                                                                         ↓
                                                                              executors/safe_executor.py
                                                                                    ↙              ↘
                                                                        executors/            executors/
                                                                        file_ops.py         gitignore_gen.py
```

**Strict one-way dependency rule:**
- `core/` does not depend on any other layer
- `analyzers/` depends only on `core/`
- `planners/` depends only on `analyzers/` + `core/`
- `executors/` depends only on `planners/` + `core/`
- `reporters/` may read from all layers (read-only)
- `main.py` is the sole orchestrator

---

## CLI Interface Design

```bash
# Analyse the project and output reports
php-cleanup analyze --report analysis_report.json --project-dir ./project

# Plan actions (filtered by risk level)
php-cleanup plan --risk-level MEDIUM

# Preview (dry-run, default)
php-cleanup execute --plan action_plan.json --dry-run

# Live execution
php-cleanup execute --plan action_plan.json --execute

# Full rollback
php-cleanup rollback --backup-dir ~/.php-cleanup-backup/2026-02-26/
```

---

## Execution Flow and Timing

```
Phase 1: Load (approx. 5–10 s)
  loader.py streams and parses JSON → builds FileRecord index
  scanner.py scans the directory   → builds DiskFileInfo index
  Cross-validation: flags ghost files and newly added files

Phase 2: Analyse (5 analyzers run in parallel, approx. 30–60 s)
  vendor_analyzer / duplicate_analyzer / backup_analyzer
  complexity_analyzer / structure_analyzer

Phase 3: Plan (approx. 5 s)
  action_planner merges the five reports → ActionPlan
  conflict_resolver resolves conflicts   → final ActionPlan

Phase 4: Preview
  cli_reporter prints the summary
  html_reporter generates the full report

Phase 5: Execute (interactive, user-controlled)
  safe_executor steps through actions by risk level, prompting for confirmation
  file_ops / gitignore_gen perform the actual changes, logging every step

Phase 6: Verify
  Re-run Phases 1–2 and output a "before vs. after cleanup" summary
```

---

## Safety Mechanisms

| Mechanism | Implemented in | Description |
|-----------|---------------|-------------|
| **Dry-run by default** | `safe_executor.py` | Without `--execute`, only a simulation is run — no files are touched |
| **Backup index** | `safe_executor.py` | Hard-links a backup of every file to `~/.php-cleanup-backup/{timestamp}/` before execution |
| **Risk classification** | `models.py` + `action_planner.py` | LOW → automatic; MEDIUM → batch confirmation; HIGH → per-action manual confirmation |
| **Conflict detection** | `conflict_resolver.py` | Resolves dependency conflicts between actions before execution begins |
| **Rollback** | `file_ops.py` | Fully restores any past operation from the backup index |
| **Cross-validation** | `loader.py` + `scanner.py` | Compares the JSON analysis against the actual state of files on disk |

---

## Estimated Benefits (for the sample project)

| Issue | Automation level |
|-------|-----------------|
| Add `vendor/` to `.gitignore` | Fully automatic |
| Delete 9 stale backup files | Fully automatic (LOW RISK) |
| Duplicate files (identical MD5) | Semi-automatic (execute after confirmation) |
| Duplicate files (diverged after forking) | Manual review (tool provides a diff) |
| Directory structure reorganisation | Tool provides recommendations; execution is manual |

---

## Recommended Development Order

1. `core/models.py` — Define all data models; the foundation every other module builds on
2. `core/loader.py` — Stream JSON parsing; performance-critical
3. `core/scanner.py` — Directory scanning and cross-validation
4. `analyzers/vendor_analyzer.py` — Highest impact; addresses 83% of the file-count problem
5. `analyzers/duplicate_analyzer.py` — Most complex; requires MD5 comparison and path-semantic inference
6. `analyzers/backup_analyzer.py` — Relatively straightforward; regex-based identification
7. `planners/action_planner.py` — Core decision-making logic
8. `executors/safe_executor.py` — The safety gate; the most important execution module
9. `executors/file_ops.py` + `gitignore_gen.py`
10. `reporters/` + `main.py`
