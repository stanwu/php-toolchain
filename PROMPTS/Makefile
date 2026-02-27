# Makefile — PHP Cleanup Toolkit
#
# Usage:
#   make                      # build all modules
#   make core                 # build only core layer (01-03)
#   make analyzers            # build only analyzers (04-08)
#   make module_05            # build only one module
#   make test                 # run full test suite
#   make clean                # remove sentinel files (triggers rebuild on next make)
#   make reset                # remove entire output directory
#
#   OUTPUT_DIR=/custom/path make     # override output directory

PROMPTS_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
OUTPUT_DIR  ?= $(HOME)/php-cleanup-toolkit
BUILT       := $(OUTPUT_DIR)/.built
BUILD_SH    := bash $(PROMPTS_DIR)/build.sh

.PHONY: all core analyzers reporters planners executors main \
        test test-build install clean reset help \
        module_01 module_02 module_03 module_04 module_05 module_06 \
        module_07 module_08 module_09 module_10 module_11 module_12 \
        module_13 module_14 module_15 module_16

# ── Default target ────────────────────────────────────────────────────────────
all: main

# ── Per-layer phony targets ───────────────────────────────────────────────────
core:      $(BUILT)/01 $(BUILT)/02 $(BUILT)/03
analyzers: $(BUILT)/04 $(BUILT)/05 $(BUILT)/06 $(BUILT)/07 $(BUILT)/08
reporters: $(BUILT)/14 $(BUILT)/15
planners:  $(BUILT)/09 $(BUILT)/10
executors: $(BUILT)/11 $(BUILT)/12 $(BUILT)/13
main:      $(BUILT)/16

# ── Single-module shortcuts ───────────────────────────────────────────────────
module_01: $(BUILT)/01
module_02: $(BUILT)/02
module_03: $(BUILT)/03
module_04: $(BUILT)/04
module_05: $(BUILT)/05
module_06: $(BUILT)/06
module_07: $(BUILT)/07
module_08: $(BUILT)/08
module_09: $(BUILT)/09
module_10: $(BUILT)/10
module_11: $(BUILT)/11
module_12: $(BUILT)/12
module_13: $(BUILT)/13
module_14: $(BUILT)/14
module_15: $(BUILT)/15
module_16: $(BUILT)/16

# ── Install dependencies ──────────────────────────────────────────────────────
install:
	pip install ijson rich click pytest

# ── Run full test suite ───────────────────────────────────────────────────────
test:
	cd $(OUTPUT_DIR) && pytest tests/ -v --tb=short

# ── Run build.sh unit tests ───────────────────────────────────────────────────
test-build:
	bats tests/test_build_sh.bats

# ── Sentinel directory ────────────────────────────────────────────────────────
$(BUILT):
	mkdir -p $(BUILT)

# ── Level 1: Core (sequential) ───────────────────────────────────────────────
$(BUILT)/01: | $(BUILT)
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 01
	@touch $@

$(BUILT)/02: $(BUILT)/01
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 02
	@touch $@

$(BUILT)/03: $(BUILT)/02
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 03
	@touch $@

# ── Level 2: Analyzers (all depend on 03, independent of each other) ─────────
$(BUILT)/04: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 04
	@touch $@

$(BUILT)/05: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 05
	@touch $@

$(BUILT)/06: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 06
	@touch $@

$(BUILT)/07: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 07
	@touch $@

$(BUILT)/08: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 08
	@touch $@

# ── Level 3: Reporters (depend on core only) ─────────────────────────────────
$(BUILT)/14: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 14
	@touch $@

$(BUILT)/15: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 15
	@touch $@

# ── Level 4: Planners (depend on all analyzers) ──────────────────────────────
$(BUILT)/09: $(BUILT)/04 $(BUILT)/05 $(BUILT)/06 $(BUILT)/07 $(BUILT)/08
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 09
	@touch $@

$(BUILT)/10: $(BUILT)/09
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 10
	@touch $@

# ── Level 5: Executors ────────────────────────────────────────────────────────
$(BUILT)/11: $(BUILT)/10
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 11
	@touch $@

$(BUILT)/12: $(BUILT)/11
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 12
	@touch $@

$(BUILT)/13: $(BUILT)/03
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 13
	@touch $@

# ── Level 6: Main integration (depends on everything) ────────────────────────
$(BUILT)/16: $(BUILT)/09 $(BUILT)/10 $(BUILT)/11 $(BUILT)/12 $(BUILT)/13 $(BUILT)/14 $(BUILT)/15
	OUTPUT_DIR=$(OUTPUT_DIR) $(BUILD_SH) --only 16
	@touch $@

# ── Utilities ─────────────────────────────────────────────────────────────────
clean:
	rm -rf $(BUILT)
	@echo "Sentinel files removed. Run 'make' to rebuild all."

reset:
	rm -rf $(OUTPUT_DIR)
	@echo "Output directory $(OUTPUT_DIR) removed."

help:
	@echo ""
	@echo "PHP Cleanup Toolkit — Build System"
	@echo ""
	@echo "Targets:"
	@echo "  make              Build all 16 modules in order"
	@echo "  make core         Modules 01-03 (core layer)"
	@echo "  make analyzers    Modules 04-08 (require core)"
	@echo "  make reporters    Modules 14-15 (require core)"
	@echo "  make planners     Modules 09-10 (require analyzers)"
	@echo "  make executors    Modules 11-13 (require planners)"
	@echo "  make main         Module 16 integration (requires all)"
	@echo "  make module_NN    Build a single module (e.g. make module_05)"
	@echo "  make test         Run full test suite"
	@echo "  make install      Install Python dependencies"
	@echo "  make clean        Remove sentinels (force full rebuild)"
	@echo "  make reset        Remove entire output directory"
	@echo ""
	@echo "Variables:"
	@echo "  OUTPUT_DIR        Output directory (default: ~/php-cleanup-toolkit)"
	@echo ""
	@echo "Examples:"
	@echo "  make                                     # build everything"
	@echo "  make module_05                           # rebuild only duplicate_analyzer"
	@echo "  make analyzers -j4                       # build 04-08 in parallel"
	@echo "  OUTPUT_DIR=/tmp/test make core           # custom output dir"
	@echo "  make clean && make                       # full clean rebuild"
	@echo ""
