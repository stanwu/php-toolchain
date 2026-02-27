import logging
import os
import shutil
from pathlib import Path

from core.models import Action, ActionType

logger = logging.getLogger(__name__)


class FileOps:
    def __init__(self, project_dir: Path, backup_dir: Path) -> None:
        self.project_dir = project_dir
        self.backup_dir = backup_dir

    def _safe_resolve(self, relative: str) -> Path:
        """
        Resolve a relative path against project_dir and verify it stays
        within project_dir (prevents path traversal).
        Raises ValueError if the resolved path escapes project_dir.
        """
        resolved = (self.project_dir / relative).resolve()
        if not resolved.is_relative_to(self.project_dir.resolve()):
            raise ValueError(
                f"Path traversal detected: '{relative}' resolves outside project_dir"
            )
        return resolved

    def delete(self, action: Action) -> dict:
        """
        1. _safe_resolve(action.source) — raises ValueError on traversal
        2. Verify file exists; if not, return {status: "skipped", reason: "not found"}
        3. Hard-link the file to backup_dir / action.source
        4. Delete the original file
        5. If the parent directory is now empty, remove it
        6. Return {status: "ok", backup_path: str}
        """
        try:
            src = self._safe_resolve(action.source)
        except ValueError:
            return {"status": "error", "reason": "path traversal blocked"}

        if not src.exists():
            return {"status": "skipped", "reason": "not found"}

        try:
            backup = self._backup_path_for(action.source)
            self._hard_link_or_copy(src, backup)
            src.unlink()
            parent = src.parent
            if parent != self.project_dir.resolve() and not any(parent.iterdir()):
                parent.rmdir()
            logger.info("Deleted %s (backup: %s)", action.source, backup)
            return {"status": "ok", "backup_path": str(backup)}
        except PermissionError:
            return {"status": "error", "reason": "permission denied"}
        except OSError as e:
            return {"status": "error", "reason": str(e)}

    def move(self, action: Action) -> dict:
        """
        1. _safe_resolve(action.source) for src
        2. _safe_resolve(action.destination) for dst
        3. Verify src exists
        4. Hard-link src to backup_dir (before move)
        5. Create dst parent directories if needed
        6. Move src → dst (fail if dst already exists unless dst == src)
        7. Return {status: "ok", backup_path: str}
        """
        try:
            src = self._safe_resolve(action.source)
        except ValueError:
            return {"status": "error", "reason": "path traversal blocked"}

        if action.destination is None:
            return {"status": "error", "reason": "no destination specified"}

        try:
            dst = self._safe_resolve(action.destination)
        except ValueError:
            return {"status": "error", "reason": "path traversal blocked"}

        if not src.exists():
            return {"status": "skipped", "reason": "not found"}

        try:
            if dst.exists() and dst != src:
                raise FileExistsError(f"Destination already exists: {dst}")
            backup = self._backup_path_for(action.source)
            self._hard_link_or_copy(src, backup)
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            logger.info(
                "Moved %s → %s (backup: %s)", action.source, action.destination, backup
            )
            return {"status": "ok", "backup_path": str(backup)}
        except FileExistsError:
            return {"status": "error", "reason": "destination exists"}
        except PermissionError:
            return {"status": "error", "reason": "permission denied"}
        except OSError as e:
            return {"status": "error", "reason": str(e)}

    def rollback(self, backup_dir: Path, action_log: list[dict]) -> int:
        """
        Restore files from backup using action_log in REVERSE order.
        For each log entry where status == "ok":
          - Copy backup_path back to original location
        Return count of files restored.
        """
        count = 0
        for entry in reversed(action_log):
            if entry.get("status") not in ("ok", "executed"):
                continue
            backup_path_str = entry.get("backup_path")
            if not backup_path_str:
                continue
            backup = Path(backup_path_str)
            if not backup.exists():
                logger.warning("Backup file not found for rollback: %s", backup_path_str)
                continue
            try:
                original_rel = backup.relative_to(backup_dir)
                original = self.project_dir / original_rel
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, original)
                logger.info("Rolled back: restored %s from %s", original, backup)
                count += 1
            except OSError as e:
                logger.error("Rollback failed for %s: %s", backup_path_str, e)
        return count

    def _backup_path_for(self, source: str) -> Path:
        """
        Return the path where the backup copy should live:
        backup_dir / source  (preserving directory structure)
        """
        return self.backup_dir / source

    def _hard_link_or_copy(self, src: Path, dst: Path) -> None:
        """
        Try hard link first; fall back to shutil.copy2 if cross-device.
        Create parent dirs for dst if needed.
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
