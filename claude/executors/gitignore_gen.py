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
        with self.gitignore_path.open("r", encoding="utf-8") as f:
            return f.readlines()

    def generate_new_entries(self, actions: list[Action]) -> list[str]:
        """
        From actions of type ADD_GITIGNORE, extract source paths.
        Return a sorted list of new .gitignore lines to add.
        Each entry is: /{source}/\n (rooted, trailing slash for dirs).
        Skip entries that already exist in the current .gitignore.
        """
        existing_stripped = {line.strip() for line in self.read_existing()}

        seen: set[str] = set()
        new_entries: list[str] = []
        for action in actions:
            if action.action_type != ActionType.ADD_GITIGNORE:
                continue
            entry = f"/{action.source}/\n"
            entry_stripped = entry.strip()
            if entry_stripped in existing_stripped or entry_stripped in seen:
                continue
            seen.add(entry_stripped)
            new_entries.append(entry)

        return sorted(new_entries)

    def build_updated_content(self, new_entries: list[str]) -> str:
        """
        Append new entries to existing content.
        If existing file is non-empty and doesn't end with newline, add one.
        Prepend a comment block before the new entries.
        Return the full updated file content as a string.
        """
        existing_lines = self.read_existing()
        existing_content = "".join(existing_lines)

        if not new_entries:
            return existing_content

        parts: list[str] = [existing_content]

        if existing_content and not existing_content.endswith("\n"):
            parts.append("\n")

        if existing_content:
            parts.append("\n")

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        parts.append(f"# Added by php-cleanup-toolkit {timestamp}\n")
        parts.extend(new_entries)

        return "".join(parts)

    def diff(self, new_content: str) -> str:
        """
        Generate unified diff between existing and new content.
        Returns the diff as a string (empty string if no changes).
        """
        existing_lines = self.read_existing()
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                existing_lines,
                new_lines,
                fromfile=".gitignore (current)",
                tofile=".gitignore (proposed)",
            )
        )
        return "".join(diff_lines)

    def write(self, new_content: str) -> None:
        """Write new_content to .gitignore. Log path at INFO level."""
        self.gitignore_path.write_text(new_content, encoding="utf-8")
        logger.info("Written: %s", self.gitignore_path)

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

        if not dry_run:
            self.write(new_content)

        return diff_str
