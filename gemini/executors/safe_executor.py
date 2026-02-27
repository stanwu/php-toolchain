from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime, timezone
import logging
import os

from core.models import ActionPlan, Action, RiskLevel, ActionType, BackupInfo
from executors.file_ops import FileOps

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
        self.plan = plan
        self.project_dir = project_dir
        self.dry_run = dry_run
        self.confirm_fn = confirm_fn or (lambda prompt: False)
        self.action_log: list[dict] = []

    def execute(self) -> BackupInfo:
        start_time = datetime.now(timezone.utc).isoformat()
        backup_dir = None if self.dry_run else self._create_backup_dir()
        
        if not self.dry_run:
            self.file_ops = FileOps(self.project_dir, backup_dir)

        if self.dry_run:
            for action in self.plan.actions:
                logger.info(f"[DRY-RUN] {action.action_type.value:<12} {action.source:<25} ({action.risk_level.name}) — {action.reason}")
        else:
            medium_actions = [a for a in self.plan.actions if a.risk_level == RiskLevel.MEDIUM]
            
            proceed_medium = not medium_actions or self._gate_medium(medium_actions)
            
            for action in self.plan.actions:
                if action.action_type == ActionType.ADD_GITIGNORE:
                    # Gitignore is handled separately in main
                    continue

                if action.risk_level == RiskLevel.LOW:
                    log_entry = self._dispatch(action)
                    self.action_log.append(log_entry)
                elif action.risk_level == RiskLevel.MEDIUM:
                    if proceed_medium:
                        log_entry = self._dispatch(action)
                        self.action_log.append(log_entry)
                    else:
                        self.action_log.append({"action": action.to_dict(), "status": "skipped", "reason": "Medium-risk batch denied"})
                elif action.risk_level == RiskLevel.HIGH:
                    if self._gate_high(action):
                        log_entry = self._dispatch(action)
                        self.action_log.append(log_entry)
                    else:
                        self.action_log.append({"action": action.to_dict(), "status": "skipped", "reason": "High-risk action denied"})

        end_time = datetime.now(timezone.utc).isoformat()
        
        return BackupInfo(
            backup_dir=backup_dir,
            action_log=self.action_log,
            started_at=start_time,
            finished_at=end_time,
        )

    def _dispatch(self, action: Action) -> dict:
        log_entry = {"action": action.to_dict()}
        try:
            if action.action_type == ActionType.DELETE:
                result = self.file_ops.delete(action)
                log_entry.update(result)
            elif action.action_type == ActionType.MOVE:
                result = self.file_ops.move(action)
                log_entry.update(result)
            else:
                log_entry.update({"status": "skipped", "reason": f"Unsupported action type: {action.action_type}"})

        except Exception as e:
            log_entry.update({"status": "error", "reason": str(e)})
            logger.error(f"Failed to execute action {action}: {e}")
        
        return log_entry

    def _create_backup_dir(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_dir = BACKUP_ROOT / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        return backup_dir

    def _gate_medium(self, actions: list[Action]) -> bool:
        prompt = f"Proceed with batch of {len(actions)} MEDIUM risk actions? [y/N]"
        return self.confirm_fn(prompt)

    def _gate_high(self, action: Action) -> bool:
        prompt = f"Execute HIGH risk action: {action.action_type.value} {action.source}? ({action.reason}) [y/N]"
        return self.confirm_fn(prompt)
