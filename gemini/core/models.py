from __future__ import annotations
import functools
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any, List


@functools.total_ordering
class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

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

    def __str__(self):
        return self.value

@dataclass
class FileRecord:
    path: str
    max_depth: int
    total_branches: int
    exists_on_disk: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileRecord:
        return cls(**data)

@dataclass
class DuplicateGroup:
    sha256: str
    files: list[str]
    canonical: Optional[str]
    copies: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DuplicateGroup:
        return cls(**data)

# unsafe_hash=True is necessary for using Action objects in sets or as dict keys,
# which is required for topological sort in the conflict resolver.
@dataclass(unsafe_hash=True)
class Action:
    action_type: ActionType
    source: str
    destination: Optional[str] = field(default=None, hash=False)
    risk_level: RiskLevel = field(default=RiskLevel.LOW, hash=False)
    reason: str = field(default="", hash=False)
    conflict: bool = field(default=False, hash=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['action_type'] = self.action_type.value
        data['risk_level'] = self.risk_level.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        data = dict(data)  # avoid mutating caller's dict
        data['action_type'] = ActionType(data['action_type'])
        data['risk_level'] = RiskLevel(data['risk_level'])
        return cls(**data)


@dataclass
class ActionPlan:
    actions: list[Action] = field(default_factory=list)
    created_at: str = ""
    project_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "project_dir": self.project_dir,
            "actions": [action.to_dict() for action in self.actions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionPlan:
        return cls(
            created_at=data.get("created_at", ""),
            project_dir=data.get("project_dir", ""),
            actions=[Action.from_dict(action_data) for action_data in data.get("actions", [])],
        )


@dataclass
class AnalysisResult:
    analyzer_name: str
    actions: list[Action]
    metadata: dict

@dataclass
class BackupInfo:
    backup_dir: Optional[Path]
    action_log: list[dict]
    started_at: str
    finished_at: str

def validate_action(action: Action) -> List[str]:
    """Validates an action, returning a list of error strings."""
    errors = []
    if not action.reason:
        errors.append("Action must have a non-empty reason.")

    if action.action_type == ActionType.MOVE:
        if not action.destination:
            errors.append("MOVE action must have a non-empty destination.")
    elif action.action_type == ActionType.DELETE:
        if action.destination:
            errors.append("DELETE action must not have a destination.")
    
    return errors
