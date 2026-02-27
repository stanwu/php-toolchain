import ijson
import logging
from pathlib import Path
from typing import Iterator, Optional

from core.models import FileRecord

logger = logging.getLogger(__name__)


class ReportLoader:
    def __init__(self, json_path: Path) -> None:
        self._path = json_path

    def load_summary(self) -> dict:
        """Parse only the top-level "summary" block."""
        if not self._path.exists():
            raise FileNotFoundError(f"Report file not found: {self._path}")
        try:
            with self._path.open("rb") as f:
                # Collect all items under the "summary" prefix
                summary: dict = {}
                for prefix, event, value in ijson.parse(f):
                    if prefix == "summary" and event == "start_map":
                        # Now read the summary map fully
                        pass
                    elif prefix.startswith("summary.") or prefix == "summary":
                        pass

                # Simpler approach: use ijson.items to get the summary object
            with self._path.open("rb") as f:
                for obj in ijson.items(f, "summary"):
                    return obj
            return {}
        except ijson.JSONError as exc:
            raise ValueError(f"Malformed JSON in {self._path}: {exc}") from exc

    def iter_files(self) -> Iterator[tuple[str, FileRecord]]:
        """Stream-parse the "files" object, yielding (path, FileRecord) one at a time."""
        if not self._path.exists():
            raise FileNotFoundError(f"Report file not found: {self._path}")
        try:
            count = 0
            with self._path.open("rb") as f:
                # Each item under "files" is a file-entry dict keyed by relative path
                for rel_path, entry in ijson.kvitems(f, "files"):
                    # Security: reject path traversal
                    if ".." in Path(rel_path).parts:
                        raise ValueError(
                            f"Path traversal detected in report key: {rel_path!r}"
                        )

                    # Validate and sanitize numeric fields
                    raw_depth = entry.get("max_depth")
                    raw_branches = entry.get("total_branches")

                    if raw_depth is None or not isinstance(raw_depth, int) or raw_depth < 0:
                        if raw_depth is not None:
                            logger.warning(
                                "File %r has invalid max_depth=%r; defaulting to 0",
                                rel_path,
                                raw_depth,
                            )
                        else:
                            logger.warning(
                                "File %r is missing max_depth; defaulting to 0", rel_path
                            )
                        max_depth = 0
                    else:
                        max_depth = raw_depth

                    if (
                        raw_branches is None
                        or not isinstance(raw_branches, int)
                        or raw_branches < 0
                    ):
                        if raw_branches is not None:
                            logger.warning(
                                "File %r has invalid total_branches=%r; defaulting to 0",
                                rel_path,
                                raw_branches,
                            )
                        else:
                            logger.warning(
                                "File %r is missing total_branches; defaulting to 0",
                                rel_path,
                            )
                        total_branches = 0
                    else:
                        total_branches = raw_branches

                    record = FileRecord(
                        path=rel_path,
                        max_depth=max_depth,
                        total_branches=total_branches,
                    )
                    count += 1
                    if count % 1000 == 0:
                        logger.debug("Loaded %d file records so far", count)
                    yield rel_path, record
        except ijson.JSONError as exc:
            raise ValueError(f"Malformed JSON in {self._path}: {exc}") from exc

    def load_all(self) -> dict[str, FileRecord]:
        """Collect iter_files() into a dict. Use only for small JSONs or tests."""
        result = {path: record for path, record in self.iter_files()}
        logger.info("Loaded %d file records from %s", len(result), self._path)
        return result

    def get_file(self, path: str) -> Optional[FileRecord]:
        """Linear scan via iter_files() to find a single record. Returns None if not found."""
        for rel_path, record in self.iter_files():
            if rel_path == path:
                return record
        return None
