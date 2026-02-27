import logging
from dataclasses import dataclass
from pathlib import Path

from core.models import FileRecord

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    matched: dict[str, FileRecord]   # path → FileRecord (exists_on_disk=True)
    ghost: list[str]                 # paths in JSON, not on disk
    new_files: list[str]             # paths on disk, not in JSON


class DirectoryScanner:
    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir

    def scan(self) -> set[str]:
        """
        Recursively walk project_dir.
        Return a set of relative path strings (forward-slash separated,
        relative to project_dir) for every file found.
        Skips hidden directories (starting with '.') and symlinks.
        """
        result: set[str] = set()
        self._walk(self._project_dir, result)
        return result

    def _walk(self, directory: Path, result: set[str]) -> None:
        try:
            entries = list(directory.iterdir())
        except PermissionError:
            logger.warning("Permission denied scanning directory: %s", directory)
            return

        for entry in entries:
            # Skip symlinks entirely
            if entry.is_symlink():
                continue
            if entry.is_dir():
                # Skip hidden directories
                if entry.name.startswith("."):
                    continue
                self._walk(entry, result)
            elif entry.is_file():
                rel = entry.relative_to(self._project_dir)
                # Normalize to forward slashes and strip any leading ./
                rel_str = rel.as_posix()
                result.add(rel_str)

    def cross_validate(
        self,
        json_records: dict[str, FileRecord],
    ) -> ScanResult:
        """
        Compare disk files (from scan()) against json_records.
        - Sets FileRecord.exists_on_disk = True for matched files.
        - Builds ghost and new_files lists.
        Returns a ScanResult.
        """
        disk_files = self.scan()

        matched: dict[str, FileRecord] = {}
        ghost: list[str] = []
        new_files: list[str] = []

        for path, record in json_records.items():
            # Normalize JSON path: strip leading ./ if present
            normalized = path.lstrip("./") if path.startswith("./") else path
            if normalized in disk_files:
                record.exists_on_disk = True
                matched[normalized] = record
            else:
                ghost.append(normalized)

        json_paths = {
            (p.lstrip("./") if p.startswith("./") else p)
            for p in json_records
        }
        for disk_path in disk_files:
            if disk_path not in json_paths:
                new_files.append(disk_path)

        logger.info(
            "Cross-validate complete: %d matched, %d ghost, %d new",
            len(matched),
            len(ghost),
            len(new_files),
        )
        if ghost:
            logger.warning(
                "%d file(s) in JSON report are missing from disk: %s",
                len(ghost),
                ghost,
            )

        return ScanResult(matched=matched, ghost=ghost, new_files=new_files)
