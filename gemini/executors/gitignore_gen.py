from pathlib import Path
from core.models import Action, ActionType
import difflib
import logging
from datetime import datetime, timezone

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
            # Use splitlines with keepends to preserve original line endings
            return self.gitignore_path.read_text().splitlines(keepends=True)
        except Exception as e:
            logger.error(f"Error reading {self.gitignore_path}: {e}")
            return []

    def generate_new_entries(self, actions: list[Action]) -> list[str]:
        """
        From actions of type ADD_GITIGNORE, extract source paths.
        Return a list of new .gitignore lines to add:
        - Each entry is: /{source}/\n  (rooted, trailing slash for dirs)
        - Skip entries that already exist in the current .gitignore
        - Sort entries alphabetically
        """
        existing_lines = self.read_existing()
        # Create a set of stripped lines for efficient lookup
        existing_entries = {line.strip() for line in existing_lines}

        new_entries: set[str] = set()
        gitignore_actions = [a for a in actions if a.action_type == ActionType.ADD_GITIGNORE]

        for action in gitignore_actions:
            # Format as a rooted path, which is good practice for project-level ignores
            entry = f"/{action.source}/"
            if entry not in existing_entries:
                new_entries.add(f"{entry}\n")

        return sorted(list(new_entries))

    def build_updated_content(self, new_entries: list[str]) -> str:
        """
        Append new entries to existing content.
        If existing file is non-empty and doesn't end with newline, add one.
        Prepend a comment block before the new entries:
          # Added by php-cleanup-toolkit {timestamp}
        Return the full updated file content as a string.
        """
        if not new_entries:
            return "".join(self.read_existing())

        existing_content = "".join(self.read_existing())
        
        content_parts = []
        if existing_content:
            content_parts.append(existing_content)
            if not existing_content.endswith('\n'):
                content_parts.append('\n')
            # Add a blank line for better separation of old and new content
            content_parts.append('\n')

        timestamp = datetime.now(timezone.utc).isoformat()
        content_parts.append(f"# Added by php-cleanup-toolkit {timestamp}\n")
        content_parts.extend(new_entries)

        return "".join(content_parts)

    def diff(self, new_content: str) -> str:
        """
        Generate unified diff between existing and new content.
        Use difflib.unified_diff with:
          fromfile=".gitignore (current)"
          tofile=".gitignore (proposed)"
        Return the diff as a string (empty string if no changes).
        """
        existing_lines = self.read_existing()
        
        # Avoid generating a diff if there are no actual changes
        if "".join(existing_lines) == new_content:
            return ""

        diff_lines = difflib.unified_diff(
            existing_lines,
            new_content.splitlines(keepends=True),
            fromfile=".gitignore (current)",
            tofile=".gitignore (proposed)",
        )
        return "".join(diff_lines)

    def write(self, new_content: str) -> None:
        """Write new_content to .gitignore. Log path at INFO level."""
        try:
            self.gitignore_path.write_text(new_content)
            logger.info(f"Updated .gitignore at {self.gitignore_path}")
        except Exception as e:
            logger.error(f"Failed to write to {self.gitignore_path}: {e}")

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
        if not gitignore_actions:
            return ""

        new_entries = self.generate_new_entries(gitignore_actions)
        if not new_entries:
            return ""
            
        updated_content = self.build_updated_content(new_entries)
        diff_str = self.diff(updated_content)

        if not dry_run:
            self.write(updated_content)
            
        return diff_str
