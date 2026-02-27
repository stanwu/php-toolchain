# PHP Cleanup Toolkit — Development Prompt Index

## Automated Build (recommended)

Prerequisites: `claude` CLI must be installed. Python dependencies (`pytest`, `ijson`, `rich`, `click`) are installed automatically into a local venv under `$OUTPUT_DIR/.venv` — no manual `pip install` needed.

```bash
cd /Users/stan/PHP_toolchain/PROMPTS

# Install Python dependencies
make install

# Build all 16 modules automatically
make
```

Output is written to `~/php-cleanup-toolkit` by default.

### Common commands

```bash
# Custom output directory
OUTPUT_DIR=~/my_project make

# Build only a specific layer
make core                # modules 01-03
make analyzers           # modules 04-08 (requires core)
make reporters           # modules 14-15 (requires core)
make planners            # modules 09-10 (requires analyzers)
make executors           # modules 11-13 (requires planners)
make main                # module 16 (requires all)

# Build analyzers in parallel (saves time)
make analyzers -j4

# Build or rebuild a single module
make module_05

# Run the full test suite
make test

# Show all available targets
make help
```

### Resuming after failure

Each module writes a sentinel file to `.built/` when it completes successfully.
If a build fails (crash, token limit, closed window), just re-run — completed
modules are skipped automatically:

```bash
# Re-run after any failure: already-built modules are skipped
make
# or
./build.sh

# Check which modules have completed
ls ~/php-cleanup-toolkit/.built/

# Force-rebuild a specific module (e.g. after editing its prompt)
rm ~/php-cleanup-toolkit/.built/05
make module_05

# Full clean rebuild
make clean && make
```

---

## Troubleshooting

### Bug 1 — Gemini enters interactive mode instead of executing automatically

**Symptom:** Running `./build.sh --agent gemini` causes the build to hang; gemini
prompts for user confirmation on every action instead of proceeding automatically.

**Root cause:** The `run_agent()` dispatcher called `gemini -p "$prompt"` without
the non-interactive flag.  Claude requires `--dangerously-skip-permissions` for the
same reason; gemini's equivalent is `--yolo`.

**Fix applied (`build.sh:68`):**
```bash
# Before
gemini) gemini -p "$prompt" ;;

# After
gemini) gemini --yolo -p "$prompt" ;;
```

---

### Bug 2 — `pip install` fails on macOS with Homebrew Python (PEP 668)

**Symptom:** The build exits immediately with:
```
error: externally-managed-environment
```
before any module is attempted.  Because `build.sh` uses `set -euo pipefail`, the
failed `pip install` causes the entire script to abort.

**Root cause:** macOS Python 3.14 (Homebrew) enforces
[PEP 668](https://peps.python.org/pep-0668/) and refuses system-wide `pip install`
to protect the managed environment.  Neither `pip install` nor `pip install --user`
is permitted.

**Fix applied (`build.sh`, `install_deps()`):**

`install_deps()` now creates a dedicated virtual environment under
`$OUTPUT_DIR/.venv` and installs into it.  All subsequent `pytest` calls use
`$VENV_DIR/bin/pytest` from that venv.

```bash
# Before
pip install --quiet ijson rich click pytest

# After
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet ijson rich click pytest
PYTEST="$VENV_DIR/bin/pytest"   # used for all test runs
```

The `.deps` sentinel in `.built/` still prevents the venv from being recreated on
subsequent runs.

---

## Manual Build (alternative)

If you prefer to run each module yourself:

1. Open a **fresh Claude conversation** for each module.
2. Paste **`00_MASTER_CONTEXT.md`** in full.
3. Paste the **module-specific prompt** immediately after.
4. Ask Claude to implement the module and its tests.
5. Run `pytest tests/test_<module>.py -v` to verify before moving on.

Never skip a module — later ones depend on the interfaces defined by earlier ones.

---

## Prompt Sequence

| # | File | Module | Depends on |
|---|------|--------|------------|
| 00 | `00_MASTER_CONTEXT.md` | Shared context | — |
| 01 | `01_core_models.md` | `core/models.py` | nothing |
| 02 | `02_core_loader.md` | `core/loader.py` | 01 |
| 03 | `03_core_scanner.md` | `core/scanner.py` | 01, 02 |
| 04 | `04_analyzer_vendor.md` | `analyzers/vendor_analyzer.py` | 01–03 |
| 05 | `05_analyzer_duplicate.md` | `analyzers/duplicate_analyzer.py` | 01–03 |
| 06 | `06_analyzer_backup.md` | `analyzers/backup_analyzer.py` | 01–03 |
| 07 | `07_analyzer_complexity.md` | `analyzers/complexity_analyzer.py` | 01–03 |
| 08 | `08_analyzer_structure.md` | `analyzers/structure_analyzer.py` | 01–03 |
| 09 | `09_planner_action.md` | `planners/action_planner.py` | 01–08 |
| 10 | `10_planner_conflict.md` | `planners/conflict_resolver.py` | 01–03, 09 |
| 11 | `11_executor_safe.md` | `executors/safe_executor.py` | 01–03, 09–10 |
| 12 | `12_executor_fileops.md` | `executors/file_ops.py` | 01–03, 11 |
| 13 | `13_executor_gitignore.md` | `executors/gitignore_gen.py` | 01–03 |
| 14 | `14_reporter_cli.md` | `reporters/cli_reporter.py` | 01–03 |
| 15 | `15_reporter_html.md` | `reporters/html_reporter.py` | 01–03 |
| 16 | `16_main_integration.md` | `main.py` + integration tests | ALL |

---

## Dependency levels

```
Level 1 (core):      01 → 02 → 03
Level 2 (analyzers): 04, 05, 06, 07, 08  ← parallel
Level 3 (reporters): 14, 15              ← parallel with level 2
Level 4 (planners):  09 → 10            ← after level 2
Level 5 (executors): 11 → 12            ← after level 4; 13 parallel with 11-12
Level 6 (main):      16                  ← after all
```

---

## Security fixes applied to prompts

The following security issues were identified and patched before automation.
Each point below describes what the generated code must implement:

| Severity | Module | Fix |
|----------|--------|-----|
| High | `12_executor_fileops.md` | `_safe_resolve()` blocks path traversal (`../../etc/passwd`) in `delete()` and `move()` |
| Medium | `15_reporter_html.md` | `html.escape()` on all user-derived strings before embedding in HTML (prevents XSS) |
| Medium | `05_analyzer_duplicate.md` | SHA-256 instead of MD5 for file hashing (prevents hash-collision false positives) |
| Low | `02_core_loader.md` | JSON keys containing `..` segments rejected with `ValueError` during streaming parse |
| Low | `11_executor_safe.md` | Backup directory created with `mode=0o700` (prevents other users reading backed-up PHP files) |
| Low | `16_main_integration.md` | `records` dict passed to `ThreadPoolExecutor` analyzers is explicitly read-only |

---

## Test commands

### Toolkit module tests (pytest)

Run from `~/php-cleanup-toolkit` after a successful build:

```bash
# Individual module
pytest tests/test_models.py -v
pytest tests/test_loader.py -v
pytest tests/test_scanner.py -v
pytest tests/test_vendor_analyzer.py -v
pytest tests/test_duplicate_analyzer.py -v
pytest tests/test_backup_analyzer.py -v
pytest tests/test_complexity_analyzer.py -v
pytest tests/test_structure_analyzer.py -v
pytest tests/test_action_planner.py -v
pytest tests/test_conflict_resolver.py -v
pytest tests/test_safe_executor.py -v
pytest tests/test_file_ops.py -v
pytest tests/test_gitignore_gen.py -v
pytest tests/test_cli_reporter.py -v
pytest tests/test_html_reporter.py -v
pytest tests/test_integration.py -v

# Everything
pytest tests/ -v --tb=short
```

---

### Build system unit tests (bats)

`tests/test_build_sh.bats` tests the behaviour of `build.sh` itself — no
modules are actually built; all external commands (`claude`, `pytest`, `pip`)
are replaced with lightweight mocks.

**Install bats-core once:**

```bash
brew install bats-core          # macOS
apt-get install bats            # Debian/Ubuntu
```

**Run:**

```bash
bats tests/test_build_sh.bats   # directly
make test-build                  # via Makefile
```

**Coverage (29 tests):**

| Category | Tests | What is verified |
|----------|-------|-----------------|
| Help / usage | 4 | `--help`/`-h` exit code and output; works without dependencies |
| Unknown flag | 2 | Exit code 1, "Unknown flag" message |
| Dependency checks | 4 | Missing `claude` or `pytest` → exit 1 + correct error message |
| Output directory | 3 | `OUTPUT_DIR` and `.built/` created; `--output-dir` flag |
| Sentinel logic | 3 | Sentinel created on success; module skipped when it exists; `claude` not called twice |
| `--only` flag | 3 | Only the specified module is built; others untouched |
| `--from` flag | 3 | Skip message printed; no sentinel for skipped modules; build resumes at start point |
| `install_deps` | 3 | `.deps` sentinel created; pip called when absent, skipped when present |
| Test execution | 4 | Failing pytest → exit 1 + "Tests FAILED" + no sentinel; passing → sentinel created |
