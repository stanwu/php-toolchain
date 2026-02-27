#!/usr/bin/env bats
# tests/test_build_sh.bats — Unit tests for build.sh
#
# Requirements: bats-core >= 1.5
#   macOS : brew install bats-core
#   Linux : apt-get install bats  (or clone https://github.com/bats-core/bats-core)
# Run:
#   bats tests/test_build_sh.bats     # directly
#   make test-build                    # via Makefile

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/build.sh"

# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

setup() {
    TMPDIR_ROOT="$(mktemp -d)"
    export OUTPUT_DIR="$TMPDIR_ROOT/output"
    MOCK_BIN="$TMPDIR_ROOT/bin"
    mkdir -p "$MOCK_BIN"

    # Minimal mock executables — succeed silently by default
    printf '#!/usr/bin/env bash\nexit 0\n' > "$MOCK_BIN/claude" && chmod +x "$MOCK_BIN/claude"
    printf '#!/usr/bin/env bash\nexit 0\n' > "$MOCK_BIN/pytest" && chmod +x "$MOCK_BIN/pytest"
    printf '#!/usr/bin/env bash\nexit 0\n' > "$MOCK_BIN/pip"    && chmod +x "$MOCK_BIN/pip"

    export PATH="$MOCK_BIN:$PATH"
}

teardown() {
    rm -rf "$TMPDIR_ROOT"
}

# Run build.sh with a restricted PATH (mock bin + system only) and stderr merged
# into stdout, so no real claude/pytest/pip leaks in and all assertions use $output.
run_build() {
    run env PATH="$MOCK_BIN:/usr/bin:/bin" bash -c '"$0" "$@" 2>&1' "$SCRIPT" "$@"
}

# ─────────────────────────────────────────────────────────────────────────────
# Help / usage
# ─────────────────────────────────────────────────────────────────────────────

@test "--help exits 0" {
    run_build --help
    [ "$status" -eq 0 ]
}

@test "--help prints usage text" {
    run_build --help
    [[ "$output" == *"build all modules"* ]]
}

@test "-h exits 0" {
    run_build -h
    [ "$status" -eq 0 ]
}

@test "-h succeeds even without claude or pytest installed" {
    rm "$MOCK_BIN/claude" "$MOCK_BIN/pytest"
    run_build -h
    [ "$status" -eq 0 ]
}

# ─────────────────────────────────────────────────────────────────────────────
# Unknown flag
# ─────────────────────────────────────────────────────────────────────────────

@test "unknown flag exits 1" {
    run_build --bogus
    [ "$status" -eq 1 ]
}

@test "unknown flag prints 'Unknown flag'" {
    run_build --bogus
    [[ "$output" == *"Unknown flag"* ]]
}

# ─────────────────────────────────────────────────────────────────────────────
# Dependency checks
# ─────────────────────────────────────────────────────────────────────────────

@test "missing claude exits 1" {
    rm "$MOCK_BIN/claude"
    run_build --only 01
    [ "$status" -eq 1 ]
}

@test "missing claude prints 'claude CLI not found'" {
    rm "$MOCK_BIN/claude"
    run_build --only 01
    [[ "$output" == *"claude CLI not found"* ]]
}

@test "missing pytest exits 1" {
    rm "$MOCK_BIN/pytest"
    run_build --only 01
    [ "$status" -eq 1 ]
}

@test "missing pytest prints 'pytest not found'" {
    rm "$MOCK_BIN/pytest"
    run_build --only 01
    [[ "$output" == *"pytest not found"* ]]
}

# ─────────────────────────────────────────────────────────────────────────────
# Output directory setup
# ─────────────────────────────────────────────────────────────────────────────

@test "creates OUTPUT_DIR when absent" {
    run_build --only 01
    [ -d "$OUTPUT_DIR" ]
}

@test "creates .built dir inside OUTPUT_DIR" {
    run_build --only 01
    [ -d "$OUTPUT_DIR/.built" ]
}

@test "--output-dir uses the specified directory" {
    CUSTOM="$TMPDIR_ROOT/custom"
    run env PATH="$MOCK_BIN:/usr/bin:/bin" bash -c '"$0" --output-dir "$1" --only 01 2>&1' "$SCRIPT" "$CUSTOM"
    [ "$status" -eq 0 ]
    [ -d "$CUSTOM/.built" ]
}

# ─────────────────────────────────────────────────────────────────────────────
# Sentinel (skip logic)
# ─────────────────────────────────────────────────────────────────────────────

@test "sentinel created after successful build" {
    run_build --only 01
    [ -f "$OUTPUT_DIR/.built/01" ]
}

@test "module skipped when sentinel exists" {
    mkdir -p "$OUTPUT_DIR/.built"
    touch "$OUTPUT_DIR/.built/01"
    run_build --only 01
    [[ "$output" == *"already built"* ]]
}

@test "claude not invoked when sentinel exists" {
    mkdir -p "$OUTPUT_DIR/.built"
    touch "$OUTPUT_DIR/.built/01"
    printf '#!/usr/bin/env bash\necho CLAUDE_CALLED\nexit 0\n' > "$MOCK_BIN/claude"
    chmod +x "$MOCK_BIN/claude"
    run_build --only 01
    [[ "$output" != *"CLAUDE_CALLED"* ]]
}

# ─────────────────────────────────────────────────────────────────────────────
# --agent flag
# ─────────────────────────────────────────────────────────────────────────────

@test "default agent is claude" {
    run_build --dry-run --only 01
    [[ "$output" == *"Agent"*"claude"* ]]
}

@test "--agent gemini is accepted" {
    printf '#!/usr/bin/env bash\nexit 0\n' > "$MOCK_BIN/gemini" && chmod +x "$MOCK_BIN/gemini"
    run_build --agent gemini --dry-run --only 01
    [ "$status" -eq 0 ]
    [[ "$output" == *"Agent"*"gemini"* ]]
}

@test "--agent codex is accepted" {
    printf '#!/usr/bin/env bash\nexit 0\n' > "$MOCK_BIN/codex" && chmod +x "$MOCK_BIN/codex"
    run_build --agent codex --dry-run --only 01
    [ "$status" -eq 0 ]
    [[ "$output" == *"Agent"*"codex"* ]]
}

@test "--agent with unknown value exits 1" {
    run_build --agent badagent
    [ "$status" -eq 1 ]
}

@test "--agent with unknown value prints error" {
    run_build --agent badagent
    [[ "$output" == *"Unknown agent"* ]]
}

@test "--agent gemini calls gemini binary not claude" {
    printf '#!/usr/bin/env bash\necho GEMINI_CALLED\nexit 0\n' > "$MOCK_BIN/gemini" && chmod +x "$MOCK_BIN/gemini"
    printf '#!/usr/bin/env bash\necho CLAUDE_CALLED\nexit 0\n' > "$MOCK_BIN/claude" && chmod +x "$MOCK_BIN/claude"
    run_build --agent gemini --only 01
    [[ "$output" == *"GEMINI_CALLED"* ]]
    [[ "$output" != *"CLAUDE_CALLED"* ]]
}

@test "missing agent binary exits 1" {
    run_build --agent gemini --only 01
    [ "$status" -eq 1 ]
}

# ─────────────────────────────────────────────────────────────────────────────
# --only flag
# ─────────────────────────────────────────────────────────────────────────────

@test "--only builds exactly the specified module" {
    run_build --only 01
    [ -f "$OUTPUT_DIR/.built/01" ]
}

@test "--only does not build other modules" {
    run_build --only 01
    [ ! -f "$OUTPUT_DIR/.built/02" ]
    [ ! -f "$OUTPUT_DIR/.built/03" ]
}

@test "--only with an unknown module id exits 0 and builds nothing" {
    run_build --only 99
    [ "$status" -eq 0 ]
    [ ! -f "$OUTPUT_DIR/.built/01" ]
}

# ─────────────────────────────────────────────────────────────────────────────
# --from flag
# ─────────────────────────────────────────────────────────────────────────────

@test "--from prints 'before --from' for every skipped module" {
    run_build --from 15
    [[ "$output" == *"before --from"* ]]
}

@test "--from does not create sentinels for skipped modules" {
    run_build --from 15
    [ ! -f "$OUTPUT_DIR/.built/01" ]
    [ ! -f "$OUTPUT_DIR/.built/14" ]
}

@test "--from builds modules at and after the start point" {
    run_build --from 15
    [ -f "$OUTPUT_DIR/.built/15" ]
    [ -f "$OUTPUT_DIR/.built/16" ]
}

# ─────────────────────────────────────────────────────────────────────────────
# install_deps
# ─────────────────────────────────────────────────────────────────────────────

@test "install_deps creates .deps sentinel on first run" {
    run_build --only 01
    [ -f "$OUTPUT_DIR/.built/.deps" ]
}

@test "install_deps calls pip when .deps absent" {
    printf '#!/usr/bin/env bash\necho PIP_CALLED\nexit 0\n' > "$MOCK_BIN/pip"
    chmod +x "$MOCK_BIN/pip"
    run_build --only 01
    [[ "$output" == *"PIP_CALLED"* ]]
}

@test "install_deps skips pip when .deps sentinel exists" {
    mkdir -p "$OUTPUT_DIR/.built"
    touch "$OUTPUT_DIR/.built/.deps"
    printf '#!/usr/bin/env bash\necho PIP_CALLED\nexit 0\n' > "$MOCK_BIN/pip"
    chmod +x "$MOCK_BIN/pip"
    run_build --only 01
    [[ "$output" != *"PIP_CALLED"* ]]
}

# ─────────────────────────────────────────────────────────────────────────────
# Test execution
# ─────────────────────────────────────────────────────────────────────────────

@test "failing tests cause module build to exit 1" {
    printf '#!/usr/bin/env bash\nexit 1\n' > "$MOCK_BIN/pytest"
    chmod +x "$MOCK_BIN/pytest"
    run_build --only 01
    [ "$status" -eq 1 ]
}

@test "failing tests print 'Tests FAILED'" {
    printf '#!/usr/bin/env bash\nexit 1\n' > "$MOCK_BIN/pytest"
    chmod +x "$MOCK_BIN/pytest"
    run_build --only 01
    [[ "$output" == *"Tests FAILED"* ]]
}

@test "failing tests do not create sentinel" {
    printf '#!/usr/bin/env bash\nexit 1\n' > "$MOCK_BIN/pytest"
    chmod +x "$MOCK_BIN/pytest"
    run_build --only 01
    [ ! -f "$OUTPUT_DIR/.built/01" ]
}

@test "passing tests create sentinel" {
    run_build --only 01
    [ "$status" -eq 0 ]
    [ -f "$OUTPUT_DIR/.built/01" ]
}
