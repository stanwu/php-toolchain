from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from core.models import FileRecord

logger = logging.getLogger(__name__)


def _normalize_relpath(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


@dataclass(slots=True)
class ScanResult:
    matched: dict[str, FileRecord]
    ghost: list[str]
    new_files: list[str]


class DirectoryScanner:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir

    def scan(self) -> set[str]:
        """
        Recursively walk project_dir.
        Return a set of relative path strings (forward-slash separated,
        relative to project_dir) for every file found.
        Skips hidden directories (starting with '.') and symlinks.
        """
        root = self.project_dir.resolve()
        results: set[str] = set()

        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            base = Path(dirpath)

            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".") and not (base / d).is_symlink()
            ]

            for name in filenames:
                p = base / name
                if p.is_symlink():
                    continue
                rel = p.relative_to(root).as_posix()
                rel = _normalize_relpath(rel)
                if rel == "":
                    continue
                results.add(rel)

        return results

    def cross_validate(self, json_records: dict[str, FileRecord]) -> ScanResult:
        """
        Compare disk files (from scan()) against json_records.
        - Sets FileRecord.exists_on_disk = True for matched files.
        - Builds ghost and new_files lists.
        Returns a ScanResult.
        """
        disk_files = { _normalize_relpath(p) for p in self.scan() }
        json_paths = { _normalize_relpath(p) for p in json_records.keys() }

        matched_paths = disk_files & json_paths
        ghost_paths = sorted(json_paths - disk_files)
        new_files = sorted(disk_files - json_paths)

        matched: dict[str, FileRecord] = {}

        for raw_path, record in json_records.items():
            normalized = _normalize_relpath(raw_path)
            if normalized in matched_paths:
                record.exists_on_disk = True
                matched[normalized] = record
            else:
                record.exists_on_disk = False

        logger.info(
            "Scan cross-validation: matched=%d ghost=%d new=%d",
            len(matched),
            len(ghost_paths),
            len(new_files),
        )
        if ghost_paths:
            logger.warning("Ghost files in JSON missing on disk: %d", len(ghost_paths))

        return ScanResult(matched=matched, ghost=ghost_paths, new_files=new_files)

