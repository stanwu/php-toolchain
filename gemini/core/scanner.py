import logging
from pathlib import Path
from dataclasses import dataclass, field
from core.models import FileRecord

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    matched: dict[str, FileRecord] = field(default_factory=dict)
    ghost: list[str] = field(default_factory=list)
    new_files: list[str] = field(default_factory=list)


class DirectoryScanner:
    def __init__(self, project_dir: Path) -> None:
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")
        self.project_dir = project_dir.resolve()

    def scan(self) -> set[str]:
        """
        Recursively walk project_dir.
        Return a set of relative path strings (forward-slash separated,
        relative to project_dir) for every file found.
        Skips hidden directories (starting with '.') and symlinks.
        """
        found_files: set[str] = set()
        for path in self.project_dir.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue

            try:
                relative_path = path.relative_to(self.project_dir)
            except ValueError:
                continue

            if any(part.startswith('.') for part in relative_path.parts):
                continue

            found_files.add(relative_path.as_posix())

        return found_files

    def cross_validate(
        self,
        json_records: dict[str, FileRecord]
    ) -> ScanResult:
        """
        Compare disk files (from scan()) against json_records.
        - Sets FileRecord.exists_on_disk = True for matched files.
        - Builds ghost and new_files lists.
        Returns a ScanResult.
        """
        disk_files = self.scan()
        json_files = set(json_records.keys())

        matched_paths = disk_files.intersection(json_files)
        ghost_paths = sorted(list(json_files - disk_files))
        new_file_paths = sorted(list(disk_files - json_files))

        matched_records = {}
        for path in matched_paths:
            record = json_records[path]
            record.exists_on_disk = True
            matched_records[path] = record

        result = ScanResult(
            matched=matched_records,
            ghost=ghost_paths,
            new_files=new_file_paths,
        )

        logger.info(
            f"Cross-validation complete: "
            f"{len(result.matched)} matched, "
            f"{len(result.ghost)} ghost, "
            f"{len(result.new_files)} new files."
        )

        if result.ghost:
            logger.warning(
                f"{len(result.ghost)} ghost files found (in JSON but not on disk)."
            )

        return result
