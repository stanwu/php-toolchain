import ijson
import logging
from pathlib import Path
from typing import Iterator, Optional, Dict
from core.models import FileRecord

logger = logging.getLogger(__name__)

class ReportLoader:
    def __init__(self, json_path: Path) -> None:
        if not json_path.exists():
            raise FileNotFoundError(f"JSON report not found at: {json_path}")
        self.json_path = json_path

    def load_summary(self) -> dict:
        """
        Parse only the top-level "summary" block.
        Returns the raw dict (small, safe to load fully).
        """
        try:
            with self.json_path.open('rb') as f:
                summaries = ijson.items(f, 'summary')
                for summary in summaries:
                    return summary
            return {}
        except ijson.JSONError as e:
            raise ValueError(f"Malformed JSON in summary of {self.json_path}: {e}") from e

    def iter_files(self) -> Iterator[tuple[str, FileRecord]]:
        """
        Stream-parse the "files" object using ijson.
        Yields (relative_path: str, FileRecord) one at a time.
        Only reads max_depth and total_branches per entry —
        branch/function details are intentionally skipped here.
        Logs progress every 1000 files at DEBUG level.
        """
        count = 0
        try:
            with self.json_path.open('rb') as f:
                file_entries = ijson.kvitems(f, 'files')
                for path, file_data in file_entries:
                    if ".." in path.split('/'):
                        raise ValueError(f"Path traversal attempt detected in file path: {path}")

                    max_depth = file_data.get('max_depth')
                    total_branches = file_data.get('total_branches')

                    if not isinstance(max_depth, int) or max_depth < 0:
                        logger.warning(f"Invalid or missing 'max_depth' for {path}. Defaulting to 0.")
                        max_depth = 0
                    
                    if not isinstance(total_branches, int) or total_branches < 0:
                        logger.warning(f"Invalid or missing 'total_branches' for {path}. Defaulting to 0.")
                        total_branches = 0

                    record = FileRecord(
                        path=path,
                        max_depth=max_depth,
                        total_branches=total_branches
                    )
                    yield path, record
                    
                    count += 1
                    if count % 1000 == 0:
                        logger.debug(f"Loaded {count} file records...")

        except ijson.JSONError as e:
            raise ValueError(f"Malformed JSON in files section of {self.json_path}: {e}") from e

    def load_all(self) -> Dict[str, FileRecord]:
        """
        Convenience wrapper: collect iter_files() into a dict.
        Use only for small JSONs or tests.
        """
        all_files = dict(self.iter_files())
        logger.info(f"Loaded {len(all_files)} total file records from {self.json_path}.")
        return all_files

    def get_file(self, path: str) -> Optional[FileRecord]:
        """
        Linear scan via iter_files() to find a single record.
        Returns None if not found. Intended for testing only.
        """
        for file_path, record in self.iter_files():
            if file_path == path:
                return record
        return None
