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
