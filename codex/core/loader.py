from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Iterator, Optional

try:
    import ijson  # type: ignore[import-not-found]
    from ijson.common import IncompleteJSONError, JSONError  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    ijson = None

    class JSONError(Exception):
        pass

    class IncompleteJSONError(Exception):
        pass

from core.models import FileRecord

logger = logging.getLogger(__name__)


def _ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"JSON report not found: {path}")


def _reject_path_traversal(relative_path: str) -> None:
    # Treat both '/' and '\' as separators so a tampered report can't sneak in
    # Windows-style traversal payloads.
    parts = [p for p in relative_path.replace("\\", "/").split("/") if p != ""]
    if any(part == ".." for part in parts):
        raise ValueError(f"Invalid path (path traversal detected): {relative_path}")


def _parse_nonneg_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


class ReportLoader:
    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path

    def load_summary(self) -> dict:
        """
        Parse only the top-level "summary" block.
        Returns the raw dict (small, safe to load fully).
        """
        _ensure_exists(self.json_path)
        if ijson is None:
            logger.warning("ijson not installed; falling back to full JSON load for summary")
            try:
                data = json.loads(self.json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed JSON while parsing summary: {self.json_path}") from e
            summary = data.get("summary")
            return {} if summary is None else dict(summary)
        try:
            with self.json_path.open("rb") as f:
                summary_iter = ijson.items(f, "summary")
                summary = next(summary_iter, None)
                return {} if summary is None else dict(summary)
        except (JSONError, IncompleteJSONError) as e:
            raise ValueError(f"Malformed JSON while parsing summary: {self.json_path}") from e

    def iter_files(self) -> Iterator[tuple[str, FileRecord]]:
        """
        Stream-parse the "files" object using ijson.
        Yields (relative_path: str, FileRecord) one at a time.
        Only reads max_depth and total_branches per entry —
        branch/function details are intentionally skipped here.
        Logs progress every 1000 files at DEBUG level.
        """
        _ensure_exists(self.json_path)
        if ijson is None:
            logger.warning("ijson not installed; falling back to full JSON load for files")
            try:
                data = json.loads(self.json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed JSON while parsing files: {self.json_path}") from e
            files_obj = data.get("files") or {}
            if not isinstance(files_obj, dict):
                return
            for rel_path, info in files_obj.items():
                rel_path_str = str(rel_path)
                _reject_path_traversal(rel_path_str)
                md = info.get("max_depth", 0) if isinstance(info, dict) else 0
                tb = info.get("total_branches", 0) if isinstance(info, dict) else 0
                try:
                    md_i = int(md)
                except Exception:
                    md_i = 0
                try:
                    tb_i = int(tb)
                except Exception:
                    tb_i = 0
                yield rel_path_str, FileRecord(path=rel_path_str, max_depth=max(0, md_i), total_branches=max(0, tb_i))
            return

        count = 0
        global_depth = 0

        pending_files_start = False
        in_files_map = False
        files_container_depth: Optional[int] = None

        pending_entry_start = False
        in_entry = False
        entry_container_depth: Optional[int] = None

        current_path: Optional[str] = None
        current_field_key: Optional[str] = None
        max_depth_val: Optional[int] = None
        total_branches_val: Optional[int] = None
        max_depth_seen = False
        total_branches_seen = False

        def finalize_current() -> tuple[str, FileRecord]:
            nonlocal current_path, max_depth_val, total_branches_val, max_depth_seen, total_branches_seen

            assert current_path is not None
            if not max_depth_seen:
                logger.warning('File entry "%s" missing max_depth; defaulting to 0', current_path)
            if not total_branches_seen:
                logger.warning(
                    'File entry "%s" missing total_branches; defaulting to 0', current_path
                )

            md = 0 if max_depth_val is None else max_depth_val
            tb = 0 if total_branches_val is None else total_branches_val

            record = FileRecord(path=current_path, max_depth=md, total_branches=tb)
            path_out = current_path

            current_path = None
            max_depth_val = None
            total_branches_val = None
            max_depth_seen = False
            total_branches_seen = False

            return path_out, record

        try:
            with self.json_path.open("rb") as f:
                for prefix, event, value in ijson.parse(f):
                    # Detect "files" at the root (depth==1 => inside top-level map).
                    if global_depth == 1 and event == "map_key" and value == "files":
                        pending_files_start = True

                    if pending_files_start and event == "start_map":
                        pending_files_start = False
                        in_files_map = True
                        files_container_depth = global_depth + 1

                    # Within the files map, keys at depth==files_container_depth are file paths.
                    if (
                        in_files_map
                        and files_container_depth is not None
                        and global_depth == files_container_depth
                        and event == "map_key"
                    ):
                        current_path = str(value)
                        _reject_path_traversal(current_path)

                        pending_entry_start = True
                        in_entry = False
                        entry_container_depth = None
                        current_field_key = None
                        max_depth_val = None
                        total_branches_val = None
                        max_depth_seen = False
                        total_branches_seen = False

                    if pending_entry_start:
                        if event == "start_map":
                            pending_entry_start = False
                            in_entry = True
                            entry_container_depth = global_depth + 1
                        elif event in {"null", "string", "number", "boolean"}:
                            # Unexpected scalar; treat as empty entry.
                            pending_entry_start = False
                            in_entry = False
                            if current_path is not None:
                                yield finalize_current()
                                count += 1
                                if count % 1000 == 0:
                                    logger.debug("Loaded %d file records", count)

                    if (
                        in_entry
                        and entry_container_depth is not None
                        and global_depth == entry_container_depth
                        and event == "map_key"
                    ):
                        current_field_key = str(value)

                    if (
                        in_entry
                        and entry_container_depth is not None
                        and global_depth == entry_container_depth
                        and current_field_key in {"max_depth", "total_branches"}
                        and event in {"null", "string", "number", "boolean"}
                    ):
                        parsed = _parse_nonneg_int(value)
                        if current_field_key == "max_depth":
                            max_depth_seen = True
                            if parsed is None:
                                logger.warning(
                                    'File entry "%s" has invalid max_depth; defaulting to 0',
                                    current_path,
                                )
                                max_depth_val = 0
                            else:
                                max_depth_val = parsed
                        else:
                            total_branches_seen = True
                            if parsed is None:
                                logger.warning(
                                    'File entry "%s" has invalid total_branches; defaulting to 0',
                                    current_path,
                                )
                                total_branches_val = 0
                            else:
                                total_branches_val = parsed
                        current_field_key = None

                    if (
                        in_entry
                        and entry_container_depth is not None
                        and global_depth == entry_container_depth
                        and current_field_key in {"max_depth", "total_branches"}
                        and event in {"start_map", "start_array"}
                    ):
                        # Value is a container, which is invalid for these numeric fields.
                        if current_field_key == "max_depth":
                            max_depth_seen = True
                            max_depth_val = 0
                            logger.warning(
                                'File entry "%s" has invalid max_depth; defaulting to 0',
                                current_path,
                            )
                        else:
                            total_branches_seen = True
                            total_branches_val = 0
                            logger.warning(
                                'File entry "%s" has invalid total_branches; defaulting to 0',
                                current_path,
                            )
                        current_field_key = None

                    # Entry ends when its map closes.
                    if (
                        in_entry
                        and entry_container_depth is not None
                        and global_depth == entry_container_depth
                        and event == "end_map"
                    ):
                        in_entry = False
                        entry_container_depth = None
                        current_field_key = None
                        if current_path is not None:
                            yield finalize_current()
                            count += 1
                            if count % 1000 == 0:
                                logger.debug("Loaded %d file records", count)

                    # Leave files map.
                    if (
                        in_files_map
                        and files_container_depth is not None
                        and global_depth == files_container_depth
                        and event == "end_map"
                    ):
                        in_files_map = False
                        files_container_depth = None

                    # Update global depth after processing this event.
                    if event in {"start_map", "start_array"}:
                        global_depth += 1
                    elif event in {"end_map", "end_array"}:
                        global_depth -= 1
        except (JSONError, IncompleteJSONError) as e:
            raise ValueError(f"Malformed JSON while parsing files: {self.json_path}") from e

    def load_all(self) -> dict[str, FileRecord]:
        """
        Convenience wrapper: collect iter_files() into a dict.
        Use only for small JSONs or tests.
        """
        records: dict[str, FileRecord] = {}
        for path, record in self.iter_files():
            records[path] = record
        logger.info("Loaded %d file records", len(records))
        return records

    def get_file(self, path: str) -> Optional[FileRecord]:
        """
        Linear scan via iter_files() to find a single record.
        Returns None if not found. Intended for testing only.
        """
        for rel_path, record in self.iter_files():
            if rel_path == path:
                return record
        return None
