.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help venv install test test-system clean

help:
	@printf "%s\n" \
		"Targets:" \
		"  make venv         Create/update virtualenv in $(VENV)" \
		"  make install      Install project + dev deps into $(VENV)" \
		"  make test         Run pytest using $(VENV)" \
		"  make test-system  Run pytest using $(PYTHON) (no venv)" \
		"  make clean        Remove common build/test artifacts"

venv: $(VENV_PY)

$(VENV_PY): pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip setuptools wheel

install: venv
	$(PIP) install -e ".[dev]"

test: venv
	$(VENV_PY) -m pytest

test-system:
	$(PYTHON) -m pytest

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
