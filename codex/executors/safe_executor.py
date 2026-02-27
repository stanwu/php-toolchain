from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from core.models import Action, ActionPlan, ActionType, BackupInfo, RiskLevel

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path.home() / ".php-cleanup-backup"


def _default_confirm(prompt: str) -> bool:
    try:
        answer = input(prompt + " ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


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
        self._confirm_fn: Callable[[str], bool] = confirm_fn or _default_confirm

    def execute(self) -> BackupInfo:
        """
        Main entry point.
        1. If dry_run: log every action as "[DRY-RUN]" and return a BackupInfo
           with empty action_log. Never call file_ops.
        2. If not dry_run:
           a. Create backup directory: BACKUP_ROOT / {timestamp}/
           b. For each action, gate by risk level:
              - LOW:    execute immediately
              - MEDIUM: ask confirm_fn("Proceed with batch of N MEDIUM actions? [y/N]")
              - HIGH:   ask confirm_fn per action ("Delete X? [y/N]")
           c. On confirm=False: skip action, log as SKIPPED
           d. On confirm=True:  call _dispatch(action), log result
        3. Return BackupInfo with complete action_log.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir_hint = BACKUP_ROOT / timestamp

        if self.dry_run:
            for action in self.plan.actions:
                logger.info(self._format_dry_run(action))
            return BackupInfo(timestamp=timestamp, backup_dir=backup_dir_hint, action_log=[])

        backup_dir = self._create_backup_dir(timestamp=timestamp)

        medium_actions = [a for a in self.plan.actions if a.risk_level == RiskLevel.MEDIUM]
        medium_ok = True
        if medium_actions:
            medium_ok = self._gate_medium(medium_actions)

        action_log: list[dict[str, Any]] = []
        for action in self.plan.actions:
            if action.risk_level == RiskLevel.MEDIUM and not medium_ok:
                entry = {
                    "action": action,
                    "status": "skipped",
                    "backup_path": None,
                    "error": "medium-risk batch denied",
                }
                logger.info("SKIPPED %s %s (MEDIUM) — %s", action.action_type.value, action.source, action.reason)
                action_log.append(entry)
                continue

            if action.risk_level == RiskLevel.HIGH and not self._gate_high(action):
                entry = {
                    "action": action,
                    "status": "skipped",
                    "backup_path": None,
                    "error": "high-risk action denied",
                }
                logger.info("SKIPPED %s %s (HIGH) — %s", action.action_type.value, action.source, action.reason)
                action_log.append(entry)
                continue

            entry = self._dispatch(action, backup_dir=backup_dir)
            action_log.append(entry)

        return BackupInfo(timestamp=timestamp, backup_dir=backup_dir, action_log=action_log)

    def _dispatch(self, action: Action, backup_dir: Path) -> dict[str, Any]:
        """
        Route action to correct executor method.
        Returns log entry: {action, status, backup_path, error}
        """
        entry: dict[str, Any] = {"action": action, "status": "executed", "backup_path": None, "error": None}
        try:
            if action.action_type == ActionType.REPORT_ONLY:
                logger.info("REPORT_ONLY %s (%s) — %s", action.source, action.risk_level.value, action.reason)
                return entry

            if action.action_type == ActionType.ADD_GITIGNORE:
                backup_path = self._backup_path_for(".gitignore", backup_dir=backup_dir)
                self._backup_if_exists(self.project_dir / ".gitignore", backup_path)
                self._append_gitignore_entry(action.source)
                entry["backup_path"] = backup_path if (self.project_dir / ".gitignore").exists() else None
                logger.info("ADD_GITIGNORE %s (%s) — %s", action.source, action.risk_level.value, action.reason)
                return entry

            src_path = self.project_dir / action.source

            if action.action_type == ActionType.DELETE:
                if not src_path.exists():
                    raise FileNotFoundError(f"source not found: {action.source}")
                backup_path = self._backup_path_for(action.source, backup_dir=backup_dir)
                self._backup_file(src_path, backup_path)
                src_path.unlink()
                entry["backup_path"] = backup_path
                logger.info("DELETE %s (%s) — %s", action.source, action.risk_level.value, action.reason)
                return entry

            if action.action_type == ActionType.MOVE:
                if not action.destination:
                    raise ValueError("MOVE requires destination")
                if not src_path.exists():
                    raise FileNotFoundError(f"source not found: {action.source}")
                backup_path = self._backup_path_for(action.source, backup_dir=backup_dir)
                self._backup_file(src_path, backup_path)
                dest_path = self.project_dir / action.destination
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_path), str(dest_path))
                entry["backup_path"] = backup_path
                logger.info(
                    "MOVE %s -> %s (%s) — %s",
                    action.source,
                    action.destination,
                    action.risk_level.value,
                    action.reason,
                )
                return entry

            raise ValueError(f"unsupported action_type: {action.action_type}")
        except Exception as e:
            entry["status"] = "skipped"
            entry["error"] = f"{type(e).__name__}: {e}"
            logger.exception("Failed to execute action: %s", action.to_dict())
            return entry

    def _create_backup_dir(self, *, timestamp: str) -> Path:
        """
        Create ~/.php-cleanup-backup/{timestamp}/ and return the path.
        SECURITY: use mode=0o700 so only the current user can read the backup
        (backed-up PHP files may contain database passwords, API keys, etc.).
        """
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(BACKUP_ROOT, 0o700)
        except PermissionError:
            # Best-effort; on some filesystems chmod may be restricted.
            pass

        backup_dir = BACKUP_ROOT / timestamp
        backup_dir.mkdir(parents=False, exist_ok=False, mode=0o700)
        try:
            os.chmod(backup_dir, 0o700)
        except PermissionError:
            pass
        return backup_dir

    def _gate_medium(self, actions: list[Action]) -> bool:
        """Call confirm_fn with a batch prompt. Return True to proceed."""
        prompt = f"Proceed with batch of {len(actions)} MEDIUM actions? [y/N]"
        return bool(self._confirm_fn(prompt))

    def _gate_high(self, action: Action) -> bool:
        """Call confirm_fn with a per-action prompt. Return True to proceed."""
        prompt = f"{action.action_type.value} {action.source}? [y/N]"
        return bool(self._confirm_fn(prompt))

    def _format_dry_run(self, action: Action) -> str:
        return (
            f"[DRY-RUN] {action.action_type.value:<12} {action.source:<24} "
            f"({action.risk_level.value}) — {action.reason}"
        )

    def _backup_path_for(self, rel_path: str, *, backup_dir: Path) -> Path:
        rel = rel_path.replace("\\", "/").lstrip("/")
        return backup_dir / rel

    def _backup_if_exists(self, src_path: Path, backup_path: Path) -> None:
        if not src_path.exists():
            return
        self._backup_file(src_path, backup_path)

    def _backup_file(self, src_path: Path, backup_path: Path) -> None:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if backup_path.exists():
            return

        if src_path.is_symlink():
            shutil.copy2(src_path, backup_path, follow_symlinks=False)
            return

        try:
            os.link(src_path, backup_path)
        except OSError:
            shutil.copy2(src_path, backup_path)

    def _append_gitignore_entry(self, rel_dir: str) -> None:
        norm = rel_dir.replace("\\", "/").strip()
        if not norm:
            return
        entry = norm.rstrip("/") + "/"
        gitignore_path = self.project_dir / ".gitignore"
        existing: set[str] = set()
        if gitignore_path.exists():
            try:
                existing = {line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()}
            except OSError:
                existing = set()

        if entry in existing:
            return

        gitignore_path.parent.mkdir(parents=True, exist_ok=True)
        with gitignore_path.open("a", encoding="utf-8") as f:
            if gitignore_path.stat().st_size > 0:
                f.write("\n")
            f.write(entry + "\n")

