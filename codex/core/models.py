from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import total_ordering
from pathlib import Path
from typing import Any, Optional, Self


@total_ordering
class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        return order[self] < order[other]


class ActionType(Enum):
    DELETE = "DELETE"
    MOVE = "MOVE"
    ADD_GITIGNORE = "ADD_GITIGNORE"
    REPORT_ONLY = "REPORT_ONLY"


@dataclass(frozen=True, slots=True)
class BranchRecord:
    type: str
    line: int
    depth: int
    condition: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "line": self.line,
            "depth": self.depth,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            type=str(d["type"]),
            line=int(d["line"]),
            depth=int(d["depth"]),
            condition=str(d.get("condition", "")),
        )


@dataclass(frozen=True, slots=True)
class FunctionRecord:
    name: str
    start_line: int
    end_line: int
    total_branches: int
    max_depth: int
    branches: list[BranchRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "total_branches": self.total_branches,
            "max_depth": self.max_depth,
            "branches": [b.to_dict() for b in self.branches],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        branches_raw = d.get("branches") or []
        return cls(
            name=str(d["name"]),
            start_line=int(d["start_line"]),
            end_line=int(d["end_line"]),
            total_branches=int(d["total_branches"]),
            max_depth=int(d["max_depth"]),
            branches=[BranchRecord.from_dict(b) for b in branches_raw],
        )


@dataclass(slots=True)
class FileRecord:
    path: str
    max_depth: int
    total_branches: int
    exists_on_disk: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "max_depth": self.max_depth,
            "total_branches": self.total_branches,
            "exists_on_disk": self.exists_on_disk,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            path=str(d["path"]),
            max_depth=int(d["max_depth"]),
            total_branches=int(d["total_branches"]),
            exists_on_disk=bool(d.get("exists_on_disk", True)),
        )


@dataclass(slots=True)
class DuplicateGroup:
    sha256: str
    files: list[str]
    canonical: Optional[str]
    copies: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "files": list(self.files),
            "canonical": self.canonical,
            "copies": list(self.copies),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            sha256=str(d["sha256"]),
            files=[str(p) for p in d.get("files", [])],
            canonical=(None if d.get("canonical") is None else str(d.get("canonical"))),
            copies=[str(p) for p in d.get("copies", [])],
        )


@dataclass(slots=True)
class Action:
    action_type: ActionType
    source: str
    destination: Optional[str]
    risk_level: RiskLevel
    reason: str
    conflict: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "source": self.source,
            "destination": self.destination,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "conflict": self.conflict,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        dest = d.get("destination", None)
        return cls(
            action_type=ActionType(str(d["action_type"])),
            source=str(d["source"]),
            destination=(None if dest is None else str(dest)),
            risk_level=RiskLevel(str(d["risk_level"])),
            reason=str(d.get("reason", "")),
            conflict=bool(d.get("conflict", False)),
        )


@dataclass(slots=True)
class ActionPlan:
    actions: list[Action] = field(default_factory=list)
    created_at: str = ""
    project_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "project_dir": self.project_dir,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            actions=[Action.from_dict(a) for a in d.get("actions", [])],
            created_at=str(d.get("created_at", "")),
            project_dir=str(d.get("project_dir", "")),
        )


@dataclass(slots=True)
class AnalysisResult:
    analyzer_name: str
    actions: list[Action]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyzer_name": self.analyzer_name,
            "actions": [a.to_dict() for a in self.actions],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            analyzer_name=str(d["analyzer_name"]),
            actions=[Action.from_dict(a) for a in d.get("actions", [])],
            metadata=dict(d.get("metadata", {})),
        )


@dataclass(slots=True)
class BackupInfo:
    """Created by safe_executor before any real action."""

    timestamp: str
    backup_dir: Path
    action_log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        serialized_log: list[dict[str, Any]] = []
        for entry in self.action_log:
            entry_out: dict[str, Any] = dict(entry)
            if "action" in entry_out and isinstance(entry_out["action"], Action):
                entry_out["action"] = entry_out["action"].to_dict()
            if "backup_path" in entry_out and isinstance(entry_out["backup_path"], Path):
                entry_out["backup_path"] = str(entry_out["backup_path"])
            serialized_log.append(entry_out)

        return {
            "timestamp": self.timestamp,
            "backup_dir": str(self.backup_dir),
            "action_log": serialized_log,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        log_raw = d.get("action_log", []) or []
        parsed_log: list[dict[str, Any]] = []
        for entry in log_raw:
            entry_out: dict[str, Any] = dict(entry)
            if "action" in entry_out and isinstance(entry_out["action"], dict):
                entry_out["action"] = Action.from_dict(entry_out["action"])
            if "backup_path" in entry_out and entry_out["backup_path"] is not None:
                entry_out["backup_path"] = str(entry_out["backup_path"])
            parsed_log.append(entry_out)

        return cls(
            timestamp=str(d["timestamp"]),
            backup_dir=Path(str(d["backup_dir"])),
            action_log=parsed_log,
        )


def validate_action(action: Action) -> list[str]:
    errors: list[str] = []

    if not action.source or not action.source.strip():
        errors.append("source must be non-empty")
    if not action.reason or not action.reason.strip():
        errors.append("reason must be non-empty")

    if action.action_type == ActionType.MOVE:
        if action.destination is None or not str(action.destination).strip():
            errors.append("MOVE must have a non-empty destination")
    if action.action_type == ActionType.DELETE:
        if action.destination is not None and str(action.destination).strip():
            errors.append("DELETE must NOT have a destination")

    return errors

