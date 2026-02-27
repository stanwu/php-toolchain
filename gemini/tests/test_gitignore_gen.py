import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Ensure the project root is in the Python path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import Action, ActionType, RiskLevel
from executors.gitignore_gen import GitignoreGen

def make_gitignore_action(source: str) -> Action:
    """Helper to create an ADD_GITIGNORE action."""
    return Action(
        action_type=ActionType.ADD_GITIGNORE,
        source=source,
        destination=None,
        risk_level=RiskLevel.LOW,
        reason="test"
    )

@pytest.fixture
def gitignore_gen(tmp_path: Path) -> GitignoreGen:
    """Fixture to provide a GitignoreGen instance operating in a temporary directory."""
    return GitignoreGen(tmp_path)

def test_read_existing_returns_lines(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Checks if read_existing correctly reads all lines from a .gitignore file."""
    gitignore_file = tmp_path / ".gitignore"
    content = ".env\n*.log\n\n# a comment\n"
    gitignore_file.write_text(content)
    
    lines = gitignore_gen.read_existing()
    assert lines == [".env\n", "*.log\n", "\n", "# a comment\n"]

def test_read_existing_no_file_returns_empty(gitignore_gen: GitignoreGen):
    """Checks if read_existing returns an empty list when .gitignore doesn't exist."""
    assert gitignore_gen.read_existing() == []

def test_generate_new_entries_format(gitignore_gen: GitignoreGen):
    """Ensures new entries are formatted as '/source/'."""
    actions = [make_gitignore_action("vendor")]
    new_entries = gitignore_gen.generate_new_entries(actions)
    assert new_entries == ["/vendor/\n"]

def test_generate_skips_existing_entries(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures generate_new_entries does not add entries that already exist."""
    (tmp_path / ".gitignore").write_text("/vendor/\n")
    actions = [make_gitignore_action("vendor")]
    new_entries = gitignore_gen.generate_new_entries(actions)
    assert new_entries == []

def test_generate_skips_existing_entries_with_whitespace(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures existing entries are skipped even with surrounding whitespace."""
    (tmp_path / ".gitignore").write_text("  /vendor/  \n")
    actions = [make_gitignore_action("vendor")]
    new_entries = gitignore_gen.generate_new_entries(actions)
    assert not new_entries

def test_generate_sorted(gitignore_gen: GitignoreGen):
    """Ensures new entries are sorted alphabetically."""
    actions = [
        make_gitignore_action("node_modules"),
        make_gitignore_action("vendor"),
        make_gitignore_action("build"),
    ]
    new_entries = gitignore_gen.generate_new_entries(actions)
    assert new_entries == ["/build/\n", "/node_modules/\n", "/vendor/\n"]

def test_generate_only_gitignore_actions(gitignore_gen: GitignoreGen):
    """Ensures only ADD_GITIGNORE actions are processed."""
    actions = [
        make_gitignore_action("vendor"),
        Action(ActionType.DELETE, "some/file.php", None, RiskLevel.LOW, "test"),
    ]
    new_entries = gitignore_gen.generate_new_entries(actions)
    assert new_entries == ["/vendor/\n"]

@patch('executors.gitignore_gen.datetime')
def test_build_adds_comment(mock_dt: MagicMock, gitignore_gen: GitignoreGen):
    """Ensures the generated content includes the timestamped comment header."""
    mock_dt.now.return_value.isoformat.return_value = "2026-02-26T10:00:00Z"
    new_entries = ["/vendor/\n"]
    content = gitignore_gen.build_updated_content(new_entries)
    assert "# Added by php-cleanup-toolkit 2026-02-26T10:00:00Z" in content

def test_build_preserves_existing(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures existing .gitignore content is preserved."""
    existing_content = ".env\n# comment\n"
    (tmp_path / ".gitignore").write_text(existing_content)
    
    with patch('executors.gitignore_gen.datetime') as mock_dt:
        mock_dt.now.return_value.isoformat.return_value = "FAKE_TIMESTAMP"
        content = gitignore_gen.build_updated_content(["/vendor/\n"])
    
    assert content.startswith(existing_content)

def test_build_newline_before_additions(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures a blank line separates old and new content."""
    (tmp_path / ".gitignore").write_text(".env")  # No trailing newline
    
    with patch('executors.gitignore_gen.datetime') as mock_dt:
        mock_dt.now.return_value.isoformat.return_value = "FAKE_TIMESTAMP"
        content = gitignore_gen.build_updated_content(["/vendor/\n"])
    
    expected = ".env\n\n# Added by php-cleanup-toolkit FAKE_TIMESTAMP\n/vendor/\n"
    assert content == expected

def test_diff_shows_added_lines(gitignore_gen: GitignoreGen):
    """Ensures the diff correctly shows added lines."""
    new_content = "/vendor/\n"
    diff = gitignore_gen.diff(new_content)
    assert "+/vendor/" in diff
    assert "--- .gitignore (current)" in diff
    assert "+++ .gitignore (proposed)" in diff

def test_diff_empty_if_no_changes(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures the diff is an empty string if there are no changes."""
    content = "/vendor/\n"
    (tmp_path / ".gitignore").write_text(content)
    diff = gitignore_gen.diff(content)
    assert diff == ""

def test_apply_dry_run_no_write(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures apply() does not write to disk when dry_run is True."""
    gitignore_file = tmp_path / ".gitignore"
    assert not gitignore_file.exists()
    
    actions = [make_gitignore_action("vendor")]
    gitignore_gen.apply(actions, dry_run=True)
    
    assert not gitignore_file.exists()

def test_apply_writes_file(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures apply() writes the file to disk when dry_run is False."""
    gitignore_file = tmp_path / ".gitignore"
    actions = [make_gitignore_action("vendor")]
    
    with patch('executors.gitignore_gen.datetime') as mock_dt:
        mock_dt.now.return_value.isoformat.return_value = "FAKE_TIMESTAMP"
        gitignore_gen.apply(actions, dry_run=False)
    
    assert gitignore_file.exists()
    content = gitignore_file.read_text()
    assert "/vendor/" in content
    assert "FAKE_TIMESTAMP" in content

def test_apply_returns_diff_string(gitignore_gen: GitignoreGen):
    """Ensures apply() always returns a diff string."""
    actions = [make_gitignore_action("vendor")]
    
    diff_dry = gitignore_gen.apply(actions, dry_run=True)
    assert isinstance(diff_dry, str)
    assert "+/vendor/" in diff_dry
    
    diff_wet = gitignore_gen.apply(actions, dry_run=False)
    assert isinstance(diff_wet, str)
    assert "+/vendor/" in diff_wet

def test_apply_returns_empty_string_if_no_actions(gitignore_gen: GitignoreGen):
    """Ensures apply() returns an empty string if no relevant actions are provided."""
    actions = [Action(ActionType.DELETE, "file", None, RiskLevel.LOW, "test")]
    diff = gitignore_gen.apply(actions)
    assert diff == ""

def test_apply_returns_empty_string_if_no_new_entries(gitignore_gen: GitignoreGen, tmp_path: Path):
    """Ensures apply() returns an empty string if all entries already exist."""
    (tmp_path / ".gitignore").write_text("/vendor/\n")
    actions = [make_gitignore_action("vendor")]
    diff = gitignore_gen.apply(actions)
    assert diff == ""