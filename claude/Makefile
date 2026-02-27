PYTHON  := .venv/bin/python
PYTEST  := .venv/bin/pytest
PIP     := .venv/bin/pip

.PHONY: help install test test-unit test-integration clean run

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install          Create .venv and install all dependencies"
	@echo "  test             Run all tests (unit + integration)"
	@echo "  test-unit        Run unit tests only (skip integration)"
	@echo "  test-integration Run integration tests only"
	@echo "  clean            Remove __pycache__, .pytest_cache, build artifacts"
	@echo "  run              Shortcut for: python main.py --help"

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	$(PYTEST) tests/ -v

test-unit:
	$(PYTEST) tests/ -v --ignore=tests/test_integration.py

test-integration:
	$(PYTEST) tests/test_integration.py -v

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -not -path './.venv/*' -delete 2>/dev/null || true
	rm -f action_plan.json report.html

# ── Run ───────────────────────────────────────────────────────────────────────
run:
	$(PYTHON) main.py --help
