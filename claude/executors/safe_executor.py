import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from core.models import Action, ActionPlan, ActionType, BackupInfo, RiskLevel

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path.home() / ".php-cleanup-backup"


class SafeExecutor:
    def __init__(
        self,
        plan: ActionPlan,
        project_dir: Path,
        dry_run: bool = True,
        confirm_fn: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._plan = plan
        self._project_dir = project_dir
        self._dry_run = dry_run
        self._confirm_fn = confirm_fn

    def execute(self) -> BackupInfo:
        """
        Main entry point.

        Dry-run mode (default): logs every action as [DRY-RUN] and returns a
        BackupInfo with an empty action_log. Never touches the filesystem.

        Live mode: creates a backup directory, gates actions by risk level, and
        dispatches each approved action. Returns BackupInfo with the full log.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        if self._dry_run:
            for action in self._plan.actions:
                logger.info(
                    "[DRY-RUN] %-15s %-40s (%s)  — %s",
                    action.action_type.value,
                    action.source,
                    action.risk_level.value,
                    action.reason,
                )
            return BackupInfo(
                timestamp=timestamp,
                backup_dir=BACKUP_ROOT / timestamp,
                action_log=[],
            )

        backup_dir = self._create_backup_dir()
        action_log: list[dict] = []

        low = [a for a in self._plan.actions if a.risk_level == RiskLevel.LOW]
        medium = [a for a in self._plan.actions if a.risk_level == RiskLevel.MEDIUM]
        high = [a for a in self._plan.actions if a.risk_level == RiskLevel.HIGH]

        # LOW: execute immediately, no confirmation needed
        for action in low:
            entry = self._dispatch(action, backup_dir)
            action_log.append(entry)

        # MEDIUM: single batch confirmation for all MEDIUM actions
        if medium:
            if self._gate_medium(medium):
                for action in medium:
                    entry = self._dispatch(action, backup_dir)
                    action_log.append(entry)
            else:
                for action in medium:
                    action_log.append({
                        "action": action,
                        "status": "skipped",
                        "backup_path": None,
                        "error": None,
                    })

        # HIGH: per-action confirmation
        for action in high:
            if self._gate_high(action):
                entry = self._dispatch(action, backup_dir)
                action_log.append(entry)
            else:
                action_log.append({
                    "action": action,
                    "status": "skipped",
                    "backup_path": None,
                    "error": None,
                })

        return BackupInfo(
            timestamp=backup_dir.name,
            backup_dir=backup_dir,
            action_log=action_log,
        )

    def _dispatch(self, action: Action, backup_dir: Path) -> dict:
        """
        Route action to the correct file operation.
        Returns a log entry dict with keys: action, status, backup_path, error.
        """
        backup_path: Optional[str] = None
        error: Optional[str] = None
        status = "executed"

        try:
            abs_source = self._project_dir / action.source

            if action.action_type == ActionType.DELETE:
                if abs_source.exists():
                    rel_backup = backup_dir / action.source
                    rel_backup.parent.mkdir(parents=True, exist_ok=True)
                    os.link(abs_source, rel_backup)
                    backup_path = str(rel_backup)
                    abs_source.unlink()
                else:
                    logger.warning(
                        "DELETE: source not found on disk: %s", action.source
                    )

            elif action.action_type == ActionType.MOVE:
                if abs_source.exists() and action.destination:
                    rel_backup = backup_dir / action.source
                    rel_backup.parent.mkdir(parents=True, exist_ok=True)
                    os.link(abs_source, rel_backup)
                    backup_path = str(rel_backup)
                    dest = self._project_dir / action.destination
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    abs_source.rename(dest)
                else:
                    if not abs_source.exists():
                        logger.warning(
                            "MOVE: source not found on disk: %s", action.source
                        )
                    elif not action.destination:
                        logger.warning(
                            "MOVE: no destination set for: %s", action.source
                        )

            elif action.action_type in (ActionType.ADD_GITIGNORE, ActionType.REPORT_ONLY):
                logger.info(
                    "%s %s noted (no file ops)",
                    action.action_type.value,
                    action.source,
                )

        except Exception as e:
            status = "error"
            error = str(e)
            logger.error(
                "Error executing %s on %s: %s",
                action.action_type.value,
                action.source,
                e,
            )

        return {
            "action": action,
            "status": status,
            "backup_path": backup_path,
            "error": error,
        }

    def _create_backup_dir(self) -> Path:
        """
        Create ~/.php-cleanup-backup/{timestamp}/ and return the path.
        SECURITY: chmod 0o700 so only the current user can read the backup
        (backed-up PHP files may contain database passwords, API keys, etc.).
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = BACKUP_ROOT / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.chmod(0o700)
        return backup_dir

    def _gate_medium(self, actions: list[Action]) -> bool:
        """Batch confirmation for all MEDIUM-risk actions."""
        if self._confirm_fn is None:
            return True
        prompt = f"Proceed with batch of {len(actions)} MEDIUM actions? [y/N]"
        return self._confirm_fn(prompt)

    def _gate_high(self, action: Action) -> bool:
        """Per-action confirmation for HIGH-risk actions."""
        if self._confirm_fn is None:
            return True
        prompt = f"{action.action_type.value} {action.source}? [y/N]"
        return self._confirm_fn(prompt)
