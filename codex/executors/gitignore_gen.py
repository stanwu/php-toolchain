from __future__ import annotations

import difflib
import logging
from datetime import datetime, timezone
from pathlib import Path

from core.models import Action, ActionType

logger = logging.getLogger(__name__)


class GitignoreGen:
    def __init__(self, project_dir: Path) -> None:
        self.gitignore_path = project_dir / ".gitignore"

    def read_existing(self) -> list[str]:
        """
        Read existing .gitignore lines.
        Return [] if file does not exist.
        Preserve exact content (including blank lines and comments).
        """
        if not self.gitignore_path.exists():
            return []
        try:
            return self.gitignore_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            logger.exception("Failed to read %s", self.gitignore_path)
            raise

    def generate_new_entries(self, actions: list[Action]) -> list[str]:
        """
        From actions of type ADD_GITIGNORE, extract source paths.
        Return a list of new .gitignore lines to add:
        - Each entry is: /{source}/\\n  (rooted, trailing slash for dirs)
        - Skip entries that already exist in the current .gitignore
        - Sort entries alphabetically
        """
        existing_lines = self.read_existing()
        existing_stripped = {line.rstrip("\n") for line in existing_lines}

        entries: set[str] = set()
        for action in actions:
            if action.action_type != ActionType.ADD_GITIGNORE:
                continue

            norm = str(action.source).replace("\\", "/").strip()
            if not norm:
                continue
            norm = norm.lstrip("/")
            norm = norm.rstrip("/")
            if not norm:
                continue

            entry = f"/{norm}/"
            if entry in existing_stripped:
                continue
            entries.add(entry + "\n")

        return sorted(entries)

    def build_updated_content(self, new_entries: list[str]) -> str:
        """
        Append new entries to existing content.
        If existing file is non-empty and doesn't end with newline, add one.
        Prepend a comment block before the new entries:
          # Added by php-cleanup-toolkit {timestamp}
        Return the full updated file content as a string.
        """
        existing_lines = self.read_existing()
        existing = "".join(existing_lines)

        if not new_entries:
            return existing

        content = existing
        if content and not content.endswith("\n"):
            content += "\n"
        if content and not content.endswith("\n\n"):
            content += "\n"

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        content += f"# Added by php-cleanup-toolkit {timestamp}\n"
        content += "".join(new_entries)
        return content

    def diff(self, new_content: str) -> str:
        """
        Generate unified diff between existing and new content.
        Use difflib.unified_diff with:
          fromfile=".gitignore (current)"
          tofile=".gitignore (proposed)"
        Return the diff as a string (empty string if no changes).
        """
        existing = "".join(self.read_existing())
        if existing == new_content:
            return ""

        diff_lines = difflib.unified_diff(
            existing.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=".gitignore (current)",
            tofile=".gitignore (proposed)",
        )
        return "".join(diff_lines)

    def write(self, new_content: str) -> None:
        """Write new_content to .gitignore. Log path at INFO level."""
        self.gitignore_path.parent.mkdir(parents=True, exist_ok=True)
        self.gitignore_path.write_text(new_content, encoding="utf-8")
        logger.info("Wrote %s", self.gitignore_path)

    def apply(self, actions: list[Action], dry_run: bool = True) -> str:
        """
        High-level method:
        1. Filter actions to ADD_GITIGNORE only.
        2. Generate new entries.
        3. Build updated content.
        4. If dry_run: return diff string, do not write.
        5. If not dry_run: write and return diff string.
        """
        gitignore_actions = [a for a in actions if a.action_type == ActionType.ADD_GITIGNORE]
        new_entries = self.generate_new_entries(gitignore_actions)
        new_content = self.build_updated_content(new_entries)
        diff_str = self.diff(new_content)

        if dry_run:
            return diff_str

        if diff_str:
            self.write(new_content)
        return diff_str

