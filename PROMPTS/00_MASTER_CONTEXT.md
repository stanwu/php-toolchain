# Master Context — PHP Cleanup Toolkit
> **How to use:** Paste this block FIRST before every module-specific prompt.
> It provides the shared schema, data models, architecture rules, and fixtures
> that every module relies on.

---

## Project Goal

Build a Python CLI tool that:
1. Reads `analysis_report.json` (output of a PHP static analysis script)
2. Scans the actual project directory on disk
3. Analyzes problems (vendor bloat, duplicates, backup files, complexity, structure)
4. Generates a prioritized, conflict-free cleanup action plan
5. Executes cleanup safely with dry-run, risk gating, backup, and rollback

---

## analysis_report.json — Schema Reference

The file can be **up to 32 MB**. Never load it all at once in production code.

```json
{
  "summary": {
    "total_files": 14630,
    "total_branches": 27625,
    "most_complex": [
      {
        "file": "services/api/fetch_orders1.php",
        "max_depth": 21,
        "total_branches": 63
      }
    ]
  },
  "files": {
    "relative/path/to/file.php": {
      "max_depth": 2,
      "total_branches": 2,
      "branches": [
        {
          "type": "if",
          "line": 11,
          "depth": 2,
          "condition": "$data"
        }
      ],
      "functions": [
        {
          "name": "CallAPI",
          "start_line": 3,
          "end_line": 34,
          "total_branches": 2,
          "max_depth": 2,
          "branches": [
            { "type": "if", "line": 11, "depth": 2, "condition": "$data" }
          ]
        }
      ]
    }
  }
}
```

**Key rules:**
- `"files"` keys are **relative paths** from project root, no leading `/`
- `branch.type` values: `if`, `elseif`, `else`, `for`, `foreach`, `while`, `switch`, `case`, `try`, `catch`
- A file with `max_depth: 0` and empty `branches` / `functions` is a zero-complexity file
- `<global>` in `functions[].name` means top-level code outside any function

---

## Project Layout

```
php-cleanup-toolkit/
├── core/
│   ├── __init__.py
│   ├── models.py          # Shared data models — ALL modules depend on this
│   ├── loader.py          # Streaming JSON parser
│   └── scanner.py         # Disk directory scanner + cross-validation
├── analyzers/
│   ├── __init__.py
│   ├── vendor_analyzer.py
│   ├── duplicate_analyzer.py
│   ├── backup_analyzer.py
│   ├── complexity_analyzer.py
│   └── structure_analyzer.py
├── planners/
│   ├── __init__.py
│   ├── action_planner.py
│   └── conflict_resolver.py
├── executors/
│   ├── __init__.py
│   ├── safe_executor.py
│   ├── file_ops.py
│   └── gitignore_gen.py
├── reporters/
│   ├── __init__.py
│   ├── cli_reporter.py
│   └── html_reporter.py
├── tests/
│   ├── fixtures/
│   │   ├── mini_report.json   # Minimal JSON for unit tests
│   │   └── project_tree/      # Fake project directory for scanner tests
│   └── test_*.py
├── main.py
└── pyproject.toml
```

---

## Dependency Rules (strictly enforced)

```
core/        ← depends on nothing internal
analyzers/   ← depends on core/ only
planners/    ← depends on analyzers/ + core/ only
executors/   ← depends on planners/ + core/ only
reporters/   ← read-only access to all layers
main.py      ← sole orchestrator; imports from all layers
```

Circular imports are a build error. Any module that violates this will be rejected.

---

## Shared Data Models (defined in core/models.py)

```python
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ActionType(Enum):
    DELETE = "DELETE"
    MOVE = "MOVE"
    ADD_GITIGNORE = "ADD_GITIGNORE"
    REPORT_ONLY = "REPORT_ONLY"

@dataclass
class FileRecord:
    path: str             # relative path (JSON key)
    max_depth: int
    total_branches: int
    exists_on_disk: bool = True   # set by scanner after cross-validation

@dataclass
class DuplicateGroup:
    sha256: str                   # was md5 — SHA-256 avoids hash-collision false positives
    files: list[str]              # relative paths
    canonical: Optional[str]      # inferred original
    copies: list[str]             # inferred copies

@dataclass
class Action:
    action_type: ActionType
    source: str                   # relative path
    destination: Optional[str]    # used for MOVE
    risk_level: RiskLevel
    reason: str
    conflict: bool = False        # set by conflict_resolver

@dataclass
class ActionPlan:
    actions: list[Action] = field(default_factory=list)
    created_at: str = ""
    project_dir: str = ""

@dataclass
class AnalysisResult:
    analyzer_name: str
    actions: list[Action]
    metadata: dict                # analyzer-specific extra info
```

---

## Coding Standards

| Rule | Detail |
|------|--------|
| Python version | 3.11+ |
| Allowed deps | `ijson`, `rich`, `click`, `pytest` |
| Type hints | Required on all functions and methods |
| Logging | Use `logging` module; never `print()` outside reporters |
| Tests | Each module tested independently: `pytest tests/test_<module>.py` |
| Style | PEP 8; no unused imports |

---

## Shared Test Fixture — tests/fixtures/mini_report.json

Every test module uses this file as its JSON input:

```json
{
  "summary": {
    "total_files": 6,
    "total_branches": 15,
    "most_complex": [
      {"file": "saas/service.php", "max_depth": 5, "total_branches": 10}
    ]
  },
  "files": {
    "index.php": {
      "max_depth": 1, "total_branches": 2,
      "branches": [{"type": "if", "line": 3, "depth": 1, "condition": "$_GET['id']"}],
      "functions": []
    },
    "vendor/autoload.php": {
      "max_depth": 0, "total_branches": 0, "branches": [], "functions": []
    },
    "vendor/lib/helper.php": {
      "max_depth": 2, "total_branches": 4, "branches": [], "functions": []
    },
    "saas/service.php": {
      "max_depth": 5, "total_branches": 10, "branches": [], "functions": [
        {"name": "processOrder", "start_line": 10, "end_line": 80,
         "total_branches": 10, "max_depth": 5, "branches": []}
      ]
    },
    "backup_old.php": {
      "max_depth": 1, "total_branches": 1, "branches": [], "functions": []
    },
    "utils_copy.php": {
      "max_depth": 1, "total_branches": 1, "branches": [], "functions": []
    }
  }
}
```

---

## Development Order

Build in this sequence — each step depends only on completed prior steps:

```
01 core/models.py
02 core/loader.py
03 core/scanner.py
04 analyzers/vendor_analyzer.py
05 analyzers/duplicate_analyzer.py
06 analyzers/backup_analyzer.py
07 analyzers/complexity_analyzer.py
08 analyzers/structure_analyzer.py
09 planners/action_planner.py
10 planners/conflict_resolver.py
11 executors/safe_executor.py
12 executors/file_ops.py
13 executors/gitignore_gen.py
14 reporters/cli_reporter.py
15 reporters/html_reporter.py
16 main.py  (integration)
```
