.DEFAULT_GOAL := help

CLAUDE_VENV  := claude/.venv/bin/python
CODEX_VENV   := codex/.venv/bin/python

.PHONY: help build \
        install install-claude install-codex \
        test test-claude test-codex \
        test-unit-claude test-unit-codex \
        clean clean-claude clean-codex

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "PHP Cleanup Toolkit — root Makefile"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install deps for both implementations"
	@echo "  make install-claude   Install deps for claude/ only"
	@echo "  make install-codex    Install deps for codex/ only"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests (claude + codex)"
	@echo "  make test-claude      Run claude/ test suite"
	@echo "  make test-codex       Run codex/ test suite"
	@echo "  make test-unit-claude Run claude/ unit tests (skip integration)"
	@echo "  make test-unit-codex  Run codex/ unit tests (skip integration)"
	@echo ""
	@echo "Build:"
	@echo "  make build            Regenerate source from PROMPTS/ (build.sh)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove pycache and test artifacts from all"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
install-claude:
	cd claude && python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -e ".[dev]"

install-codex:
	cd codex && python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -e ".[dev]"

install: install-claude install-codex

# ── Tests ─────────────────────────────────────────────────────────────────────
test-claude: $(CLAUDE_VENV)
	cd claude && .venv/bin/python -m pytest tests/ -v

test-codex: $(CODEX_VENV)
	cd codex && .venv/bin/python -m pytest tests/ -v

test: test-claude test-codex

test-unit-claude: $(CLAUDE_VENV)
	cd claude && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_integration.py

test-unit-codex: $(CODEX_VENV)
	cd codex && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_integration.py

# ── Build ─────────────────────────────────────────────────────────────────────
build:
	@bash PROMPTS/build.sh

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean-claude:
	find claude -type d -name __pycache__ -not -path 'claude/.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find claude -type d -name .pytest_cache -not -path 'claude/.venv/*' -exec rm -rf {} + 2>/dev/null || true

clean-codex:
	find codex -type d -name __pycache__ -not -path 'codex/.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find codex -type d -name .pytest_cache -not -path 'codex/.venv/*' -exec rm -rf {} + 2>/dev/null || true

clean: clean-claude clean-codex
