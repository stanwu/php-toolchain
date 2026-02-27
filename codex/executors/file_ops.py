from __future__ import annotations

import errno
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

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
        Example: "../../../etc/passwd" → raises ValueError.
        """
        norm = str(relative).replace("\\", "/")
        resolved = (self.project_dir / norm).resolve()
        project_resolved = self.project_dir.resolve()
        if not resolved.is_relative_to(project_resolved):
            raise ValueError(f"Path traversal detected: '{relative}' resolves outside project_dir")
        return resolved

    def delete(self, action: Action) -> dict[str, Any]:
        try:
            src_path = self._safe_resolve(action.source)
        except ValueError as e:
            logger.warning("Blocked delete due to traversal: %s", e)
            return {"status": "error", "reason": "path traversal blocked"}

        try:
            if not src_path.exists():
                return {"status": "skipped", "reason": "not found"}
            if src_path.is_dir():
                return {"status": "error", "reason": "source is a directory"}

            backup_path = self._backup_path_for(action.source)
            self._hard_link_or_copy(src_path, backup_path)

            src_path.unlink()

            parent = src_path.parent
            if parent != self.project_dir and parent.exists():
                try:
                    if not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    # Best-effort; directory may not be empty or may be in use.
                    pass

            logger.info("DELETE %s", action.source)
            return {"status": "ok", "backup_path": str(backup_path)}
        except PermissionError:
            return {"status": "error", "reason": "permission denied"}
        except OSError as e:
            return {"status": "error", "reason": str(e)}

    def move(self, action: Action) -> dict[str, Any]:
        if not action.destination:
            return {"status": "error", "reason": "missing destination"}

        try:
            src_path = self._safe_resolve(action.source)
        except ValueError as e:
            logger.warning("Blocked move source due to traversal: %s", e)
            return {"status": "error", "reason": "path traversal blocked"}

        try:
            dst_path = self._safe_resolve(action.destination)
        except ValueError as e:
            logger.warning("Blocked move destination due to traversal: %s", e)
            return {"status": "error", "reason": "path traversal blocked"}

        try:
            if not src_path.exists():
                return {"status": "skipped", "reason": "not found"}
            if src_path.is_dir():
                return {"status": "error", "reason": "source is a directory"}

            if src_path.resolve() != dst_path.resolve() and dst_path.exists():
                return {"status": "error", "reason": "destination exists"}

            backup_path = self._backup_path_for(action.source)
            self._hard_link_or_copy(src_path, backup_path)

            if src_path.resolve() == dst_path.resolve():
                logger.info("MOVE %s -> %s (noop)", action.source, action.destination)
                return {"status": "ok", "backup_path": str(backup_path)}

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))

            logger.info("MOVE %s -> %s", action.source, action.destination)
            return {"status": "ok", "backup_path": str(backup_path)}
        except FileExistsError:
            return {"status": "error", "reason": "destination exists"}
        except PermissionError:
            return {"status": "error", "reason": "permission denied"}
        except OSError as e:
            return {"status": "error", "reason": str(e)}

    def rollback(self, backup_dir: Path, action_log: list[dict[str, Any]]) -> int:
        restored = 0
        for entry in reversed(action_log):
            try:
                if entry.get("status") != "ok":
                    continue
                backup_path_raw = entry.get("backup_path")
                if not backup_path_raw:
                    continue

                action = entry.get("action")
                source_rel = self._source_from_log_action(action) or entry.get("source")
                if not source_rel:
                    continue

                try:
                    original_path = self._safe_resolve(str(source_rel))
                except ValueError as e:
                    logger.warning("Blocked rollback due to traversal: %s", e)
                    continue

                backup_path = Path(str(backup_path_raw))
                if not backup_path.is_absolute():
                    backup_path = backup_dir / backup_path
                if not backup_path.exists():
                    continue

                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, original_path, follow_symlinks=False)
                restored += 1
            except OSError as e:
                logger.warning("Rollback failed for entry %s: %s", entry, e)
                continue

        return restored

    def _backup_path_for(self, source: str) -> Path:
        return self.backup_dir / str(source).replace("\\", "/").lstrip("/")

    def _hard_link_or_copy(self, src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            shutil.copy2(src, dst, follow_symlinks=False)
            return
        try:
            os.link(src, dst)
        except OSError as e:
            if e.errno == errno.EXDEV:
                shutil.copy2(src, dst, follow_symlinks=False)
                return
            raise

    def _source_from_log_action(self, action: Any) -> Optional[str]:
        if action is None:
            return None
        if isinstance(action, Action):
            return action.source
        if isinstance(action, dict):
            src = action.get("source")
            return None if src is None else str(src)
        return None

