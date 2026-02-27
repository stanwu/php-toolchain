from pathlib import Path
from core.models import Action
import logging
import shutil
import os
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class FileOps:
    def __init__(
        self,
        project_dir: Path,
        backup_dir: Path
    ) -> None:
        self.project_dir = project_dir.resolve()
        self.backup_dir = backup_dir.resolve()

    def _safe_resolve(self, relative: str) -> Path:
        """
        Resolve a relative path against project_dir and verify it stays
        within project_dir (prevents path traversal).
        Raises ValueError if the resolved path escapes project_dir.
        """
        resolved_path = (self.project_dir / relative).resolve()
        if not resolved_path.is_relative_to(self.project_dir):
            raise ValueError(
                f"Path traversal detected: '{relative}' resolves outside project_dir"
            )
        return resolved_path

    def delete(self, action: Action) -> Dict[str, Any]:
        """
        Deletes a file, backs it up, and cleans up empty parent directories.
        """
        try:
            source_path = self._safe_resolve(action.source)
            if not source_path.is_file():
                return {"status": "skipped", "reason": "not found or is a directory"}

            backup_path = self._backup_path_for(action.source)
            self._hard_link_or_copy(source_path, backup_path)

            os.remove(source_path)
            logger.info(f"Deleted file: {action.source}")

            parent_dir = source_path.parent
            if parent_dir.is_dir() and parent_dir != self.project_dir and not any(parent_dir.iterdir()):
                try:
                    os.rmdir(parent_dir)
                    logger.info(f"Removed empty directory: {parent_dir}")
                except OSError as e:
                    logger.warning(f"Could not remove directory {parent_dir}: {e}")

            return {"status": "ok", "backup_path": str(backup_path), "original_path": str(source_path)}

        except ValueError as e:
            logger.error(f"Delete failed for '{action.source}': {e}")
            return {"status": "error", "reason": "path traversal blocked"}
        except PermissionError:
            logger.error(f"Permission denied trying to delete '{action.source}'")
            return {"status": "error", "reason": "permission denied"}
        except OSError as e:
            logger.error(f"OS error deleting '{action.source}': {e}")
            return {"status": "error", "reason": str(e)}

    def move(self, action: Action) -> Dict[str, Any]:
        """
        Moves a file, backs it up, and creates destination directories.
        """
        if not action.destination:
            return {"status": "error", "reason": "destination not specified for move action"}

        try:
            src_path = self._safe_resolve(action.source)
            dst_path = self._safe_resolve(action.destination)

            if not src_path.is_file():
                return {"status": "skipped", "reason": "source not found or is a directory"}

            if dst_path.exists() and not src_path.samefile(dst_path):
                raise FileExistsError(f"Destination '{action.destination}' already exists.")

            backup_path = self._backup_path_for(action.source)
            self._hard_link_or_copy(src_path, backup_path)

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            logger.info(f"Moved file: {action.source} -> {action.destination}")

            return {"status": "ok", "backup_path": str(backup_path), "original_path": str(src_path), "new_path": str(dst_path)}

        except ValueError as e:
            logger.error(f"Move failed for '{action.source}' -> '{action.destination}': {e}")
            return {"status": "error", "reason": "path traversal blocked"}
        except FileExistsError as e:
            logger.error(f"Move failed: {e}")
            return {"status": "error", "reason": "destination exists"}
        except PermissionError:
            logger.error(f"Permission denied during move of '{action.source}'")
            return {"status": "error", "reason": "permission denied"}
        except OSError as e:
            logger.error(f"OS error moving '{action.source}': {e}")
            return {"status": "error", "reason": str(e)}

    def rollback(self, action_log: List[Dict[str, Any]]) -> int:
        """
        Restores files from backup by calculating the initial state before the transaction.
        """
        lineage = {}
        files_to_restore = {}

        for entry in action_log:
            if entry.get("status") != "ok":
                continue
            
            src = entry["original_path"]
            backup = entry["backup_path"]
            
            root = lineage.get(src, src)

            if root not in files_to_restore:
                files_to_restore[root] = backup

            if "new_path" in entry:
                dst = entry["new_path"]
                lineage[dst] = root

        all_paths = set()
        for entry in action_log:
            if entry.get("status") != "ok":
                continue
            all_paths.add(entry["original_path"])
            if "new_path" in entry:
                all_paths.add(entry["new_path"])

        for path_str in all_paths:
            p = Path(path_str)
            if p.is_file():
                try:
                    os.remove(p)
                except OSError as e:
                    logger.warning(f"Could not remove file during rollback cleanup: {p}, {e}")

        for root_path, backup_path in files_to_restore.items():
            try:
                dest = Path(root_path)
                backup = Path(backup_path)
                if not backup.exists():
                    logger.error(f"Backup file not found, cannot restore: {backup_path}")
                    continue
                
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, dest)
                logger.info(f"Restored '{dest}' from '{backup}'")
            except Exception as e:
                logger.error(f"Failed to perform final restore for {root_path}: {e}")
        
        return len(files_to_restore)

    def _backup_path_for(self, source: str) -> Path:
        """
        Return the path where the backup copy should live.
        """
        clean_source = source.lstrip('/\\')
        return self.backup_dir / clean_source

    def _hard_link_or_copy(self, src: Path, dst: Path) -> None:
        """
        Try hard link first; fall back to shutil.copy2 if cross-device.
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            if dst.exists():
                os.remove(dst)
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)