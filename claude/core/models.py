import functools
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@functools.total_ordering
class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    _order = ["LOW", "MEDIUM", "HIGH"]

    def __lt__(self, other: "RiskLevel") -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        order = ["LOW", "MEDIUM", "HIGH"]
        return order.index(self.value) < order.index(other.value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class ActionType(Enum):
    DELETE = "DELETE"
    MOVE = "MOVE"
    ADD_GITIGNORE = "ADD_GITIGNORE"
    REPORT_ONLY = "REPORT_ONLY"


@dataclass
class BranchRecord:
    type: str
    line: int
    depth: int
    condition: str

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "line": self.line,
            "depth": self.depth,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BranchRecord":
        return cls(
            type=d["type"],
            line=d["line"],
            depth=d["depth"],
            condition=d["condition"],
        )


@dataclass
class FunctionRecord:
    name: str
    start_line: int
    end_line: int
    total_branches: int
    max_depth: int
    branches: list[BranchRecord]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "total_branches": self.total_branches,
            "max_depth": self.max_depth,
            "branches": [b.to_dict() for b in self.branches],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FunctionRecord":
        return cls(
            name=d["name"],
            start_line=d["start_line"],
            end_line=d["end_line"],
            total_branches=d["total_branches"],
            max_depth=d["max_depth"],
            branches=[BranchRecord.from_dict(b) for b in d.get("branches", [])],
        )


@dataclass
class FileRecord:
    path: str
    max_depth: int
    total_branches: int
    exists_on_disk: bool = True

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "max_depth": self.max_depth,
            "total_branches": self.total_branches,
            "exists_on_disk": self.exists_on_disk,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileRecord":
        return cls(
            path=d["path"],
            max_depth=d["max_depth"],
            total_branches=d["total_branches"],
            exists_on_disk=d.get("exists_on_disk", True),
        )


@dataclass
class DuplicateGroup:
    sha256: str
    files: list[str]
    canonical: Optional[str]
    copies: list[str]

    def to_dict(self) -> dict:
        return {
            "sha256": self.sha256,
            "files": list(self.files),
            "canonical": self.canonical,
            "copies": list(self.copies),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DuplicateGroup":
        return cls(
            sha256=d["sha256"],
            files=d["files"],
            canonical=d.get("canonical"),
            copies=d.get("copies", []),
        )


@dataclass
class Action:
    action_type: ActionType
    source: str
    destination: Optional[str]
    risk_level: RiskLevel
    reason: str
    conflict: bool = False

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type.value,
            "source": self.source,
            "destination": self.destination,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "conflict": self.conflict,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        return cls(
            action_type=ActionType(d["action_type"]),
            source=d["source"],
            destination=d.get("destination"),
            risk_level=RiskLevel(d["risk_level"]),
            reason=d["reason"],
            conflict=d.get("conflict", False),
        )


@dataclass
class ActionPlan:
    actions: list[Action] = field(default_factory=list)
    created_at: str = ""
    project_dir: str = ""

    def to_dict(self) -> dict:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "project_dir": self.project_dir,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ActionPlan":
        return cls(
            actions=[Action.from_dict(a) for a in d.get("actions", [])],
            created_at=d.get("created_at", ""),
            project_dir=d.get("project_dir", ""),
        )


@dataclass
class AnalysisResult:
    analyzer_name: str
    actions: list[Action]
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "analyzer_name": self.analyzer_name,
            "actions": [a.to_dict() for a in self.actions],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisResult":
        return cls(
            analyzer_name=d["analyzer_name"],
            actions=[Action.from_dict(a) for a in d.get("actions", [])],
            metadata=d.get("metadata", {}),
        )


@dataclass
class BackupInfo:
    """Created by safe_executor before any real action."""
    timestamp: str
    backup_dir: Path
    action_log: list[dict]  # [{"action": Action, "backup_path": str}, ...]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "backup_dir": str(self.backup_dir),
            "action_log": [
                {
                    "action": entry["action"].to_dict() if isinstance(entry["action"], Action) else entry["action"],
                    "backup_path": entry["backup_path"],
                }
                for entry in self.action_log
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BackupInfo":
        action_log = []
        for entry in d.get("action_log", []):
            action_raw = entry["action"]
            action = Action.from_dict(action_raw) if isinstance(action_raw, dict) else action_raw
            action_log.append({"action": action, "backup_path": entry["backup_path"]})
        return cls(
            timestamp=d["timestamp"],
            backup_dir=Path(d["backup_dir"]),
            action_log=action_log,
        )


def validate_action(action: Action) -> list[str]:
    """
    Return a list of error strings.
    Empty list means the action is valid.
    Rules:
    - MOVE must have a non-empty destination
    - DELETE must NOT have a destination
    - reason must be non-empty
    - source must be non-empty
    """
    errors: list[str] = []

    if not action.source:
        errors.append("source must be non-empty")

    if not action.reason:
        errors.append("reason must be non-empty")

    if action.action_type == ActionType.MOVE:
        if not action.destination:
            errors.append("MOVE action must have a non-empty destination")

    if action.action_type == ActionType.DELETE:
        if action.destination is not None:
            errors.append("DELETE action must not have a destination")

    return errors
