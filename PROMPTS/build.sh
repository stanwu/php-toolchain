#!/usr/bin/env bash
# build.sh — PHP Cleanup Toolkit automated build
#
# Usage:
#   ./build.sh                           # build all modules to ~/php-cleanup-toolkit
#   OUTPUT_DIR=/path/to/dir ./build.sh
#   ./build.sh --from 05                 # resume from module 05
#   ./build.sh --only 07                 # build only one module
#   ./build.sh --dry-run                 # show what would run without executing anything
#   ./build.sh --agent gemini            # use Gemini instead of Claude (claude|gemini|codex)
#   ./build.sh --agent codex --only 03   # combine flags freely
#
# Each module is skipped if its sentinel file already exists in .built/.
# Delete a sentinel to force rebuild: rm .built/05

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/php-cleanup-toolkit}"
BUILT_DIR="$OUTPUT_DIR/.built"
FROM_MODULE=""
ONLY_MODULE=""
DRY_RUN=""
AGENT="claude"
VENV_DIR=""   # set after OUTPUT_DIR is finalised
PYTEST="pytest"

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --from)  FROM_MODULE="$2"; shift 2 ;;
        --only)  ONLY_MODULE="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; BUILT_DIR="$OUTPUT_DIR/.built"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --agent)
            case "$2" in
                claude|gemini|codex) AGENT="$2" ;;
                *) echo "Unknown agent: $2. Choose: claude, gemini, codex" >&2; exit 1 ;;
            esac
            shift 2 ;;
        -h|--help)
            sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
done

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[build]${NC} $*"; }
warn() { echo -e "${YELLOW}[skip] ${NC} $*"; }
step() { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }
fail() { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# ── Dependency check ──────────────────────────────────────────────────────────
if [[ -z "$DRY_RUN" ]]; then
    command -v "$AGENT"  >/dev/null 2>&1 || fail "$AGENT CLI not found."
    command -v python3   >/dev/null 2>&1 || fail "python3 not found."
fi

VENV_DIR="$OUTPUT_DIR/.venv"
mkdir -p "$OUTPUT_DIR" "$BUILT_DIR"

# ── Agent runner ──────────────────────────────────────────────────────────────
# run_agent <prompt>  — dispatches to the selected AI CLI
run_agent() {
    local prompt="$1"
    case "$AGENT" in
        claude) claude --dangerously-skip-permissions -p "$prompt" ;;
        gemini) gemini --yolo -p "$prompt" ;;
        codex)  echo "$prompt" | codex exec --dangerously-bypass-approvals-and-sandbox - ;;
    esac
}

# ── Module runner ─────────────────────────────────────────────────────────────
# run_module <id> <prompt_file> [test_file]
run_module() {
    local id="$1" prompt_file="$2" test_file="${3:-}"
    local sentinel="$BUILT_DIR/$id"

    # --only flag: skip modules that don't match
    if [[ -n "$ONLY_MODULE" && "$id" != "$ONLY_MODULE" ]]; then
        return 0
    fi

    # --from flag: skip modules before the start point
    if [[ -n "$FROM_MODULE" && "$id" < "$FROM_MODULE" ]]; then
        warn "Module $id — before --from $FROM_MODULE, skipping."
        return 0
    fi

    # Sentinel: already built
    if [[ -f "$sentinel" ]]; then
        warn "Module $id already built. (rm $sentinel to rebuild)"
        return 0
    fi

    step "Module $id — $prompt_file"

    # Build prompt: master context + module prompt + instruction
    local prompt
    prompt="$(cat \
        "$SCRIPT_DIR/00_MASTER_CONTEXT.md" \
        "$SCRIPT_DIR/$prompt_file")"
    prompt+=$'\n\n---\n'
    prompt+="Implement ALL deliverables listed above. "
    prompt+="Create every required file in the current working directory. "
    prompt+="Do not ask clarifying questions — implement everything now."

    # Run agent in the output directory
    if [[ -n "$DRY_RUN" ]]; then
        log "  [dry-run] $AGENT -p <prompt>"
    else
        (cd "$OUTPUT_DIR" && run_agent "$prompt")
    fi

    # Run tests if provided
    if [[ -n "$test_file" ]]; then
        log "Testing module $id → $test_file"
        if [[ -n "$DRY_RUN" ]]; then
            log "  [dry-run] pytest $test_file -v --tb=short"
        else
            (cd "$OUTPUT_DIR" && "$PYTEST" "$test_file" -v --tb=short) \
                || fail "Tests FAILED for module $id.\nFix the issue, then:\n  rm $sentinel\n  ./build.sh --from $id"
        fi
    fi

    [[ -z "$DRY_RUN" ]] && touch "$sentinel"
    log "Module $id ✓"
}

# ── Install Python dependencies ───────────────────────────────────────────────
install_deps() {
    if [[ -n "$DRY_RUN" ]]; then
        log "[dry-run] python3 -m venv $VENV_DIR && pip install ijson rich click pytest"
        return 0
    fi
    if [[ ! -f "$BUILT_DIR/.deps" ]]; then
        log "Installing Python dependencies into $VENV_DIR ..."
        python3 -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install --quiet ijson rich click pytest
        touch "$BUILT_DIR/.deps"
    fi
    PYTEST="$VENV_DIR/bin/pytest"
}

# ── Build sequence ────────────────────────────────────────────────────────────
log "Output directory : $OUTPUT_DIR"
log "Prompts directory: $SCRIPT_DIR"
log "Agent            : $AGENT"
[[ -n "$DRY_RUN"     ]] && log "Dry-run mode      : no files will be written"
[[ -n "$FROM_MODULE" ]] && log "Resuming from module $FROM_MODULE"
[[ -n "$ONLY_MODULE" ]] && log "Building only module $ONLY_MODULE"
echo ""

install_deps

# Level 1 — Core (sequential, each depends on previous)
run_module "01" "01_core_models.md"   "tests/test_models.py"
run_module "02" "02_core_loader.md"   "tests/test_loader.py"
run_module "03" "03_core_scanner.md"  "tests/test_scanner.py"

# Level 2 — Analyzers (all depend on 01-03, independent of each other)
# Level 3 — Reporters (also depend only on 01-03, safe to interleave)
run_module "04" "04_analyzer_vendor.md"     "tests/test_vendor_analyzer.py"
run_module "05" "05_analyzer_duplicate.md"  "tests/test_duplicate_analyzer.py"
run_module "06" "06_analyzer_backup.md"     "tests/test_backup_analyzer.py"
run_module "07" "07_analyzer_complexity.md" "tests/test_complexity_analyzer.py"
run_module "08" "08_analyzer_structure.md"  "tests/test_structure_analyzer.py"
run_module "14" "14_reporter_cli.md"        "tests/test_cli_reporter.py"
run_module "15" "15_reporter_html.md"       "tests/test_html_reporter.py"

# Level 4 — Planners (depend on analyzers 04-08)
run_module "09" "09_planner_action.md"   "tests/test_action_planner.py"
run_module "10" "10_planner_conflict.md" "tests/test_conflict_resolver.py"

# Level 5 — Executors (11-12 sequential; 13 depends only on core)
run_module "11" "11_executor_safe.md"      "tests/test_safe_executor.py"
run_module "12" "12_executor_fileops.md"   "tests/test_file_ops.py"
run_module "13" "13_executor_gitignore.md" "tests/test_gitignore_gen.py"

# Level 6 — Main integration (depends on everything)
run_module "16" "16_main_integration.md" "tests/test_integration.py"

echo ""
log "All modules built successfully! 🎉"
log ""
log "Next steps:"
log "  cd $OUTPUT_DIR"
log "  pip install -e ."
log "  php-cleanup analyze --report ~/analysis_report.json --project-dir ~/my-php-project"
