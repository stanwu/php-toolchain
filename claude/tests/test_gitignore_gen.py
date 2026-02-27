import pytest
from pathlib import Path

from core.models import Action, ActionType, RiskLevel
from executors.gitignore_gen import GitignoreGen


def make_gitignore_action(source: str) -> Action:
    return Action(ActionType.ADD_GITIGNORE, source, None, RiskLevel.LOW, "test")


def make_delete_action(source: str) -> Action:
    return Action(ActionType.DELETE, source, None, RiskLevel.LOW, "test")


# ---------------------------------------------------------------------------
# read_existing
# ---------------------------------------------------------------------------

def test_read_existing_returns_lines(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".env\n*.log\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)
    lines = gen.read_existing()
    assert ".env\n" in lines
    assert "*.log\n" in lines


def test_read_existing_no_file_returns_empty(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)
    assert gen.read_existing() == []


# ---------------------------------------------------------------------------
# generate_new_entries
# ---------------------------------------------------------------------------

def test_generate_new_entries_format(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)
    entries = gen.generate_new_entries([make_gitignore_action("vendor")])
    assert "/vendor/\n" in entries


def test_generate_skips_existing_entries(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("/vendor/\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)
    entries = gen.generate_new_entries([make_gitignore_action("vendor")])
    assert "/vendor/\n" not in entries


def test_generate_sorted(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)
    actions = [
        make_gitignore_action("vendor"),
        make_gitignore_action("node_modules"),
        make_gitignore_action("cache"),
    ]
    entries = gen.generate_new_entries(actions)
    assert entries == sorted(entries)


def test_generate_only_gitignore_actions(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)
    actions = [
        make_gitignore_action("vendor"),
        make_delete_action("old.php"),
    ]
    entries = gen.generate_new_entries(actions)
    assert len(entries) == 1
    assert "/vendor/\n" in entries


# ---------------------------------------------------------------------------
# build_updated_content
# ---------------------------------------------------------------------------

def test_build_adds_comment(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)
    content = gen.build_updated_content(["/vendor/\n"])
    assert "# Added by php-cleanup-toolkit" in content


def test_build_preserves_existing(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".env\n*.log\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)
    content = gen.build_updated_content(["/vendor/\n"])
    assert ".env\n" in content
    assert "*.log\n" in content


def test_build_newline_before_additions(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".env\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)
    content = gen.build_updated_content(["/vendor/\n"])
    # A blank line separates old content from the new comment/entries block.
    assert "\n\n" in content


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

def test_diff_shows_added_lines(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".env\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)
    new_content = gen.build_updated_content(["/vendor/\n"])
    diff = gen.diff(new_content)
    assert "+/vendor/" in diff


def test_diff_empty_if_no_changes(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".env\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)
    # No new entries → content is identical to existing
    new_content = gen.build_updated_content([])
    diff = gen.diff(new_content)
    assert diff == ""


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def test_apply_dry_run_no_write(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    original = ".env\n"
    gitignore.write_text(original, encoding="utf-8")
    gen = GitignoreGen(tmp_path)
    gen.apply([make_gitignore_action("vendor")], dry_run=True)
    assert gitignore.read_text(encoding="utf-8") == original


def test_apply_writes_file(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)
    gen.apply([make_gitignore_action("vendor")], dry_run=False)
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "/vendor/" in content


def test_apply_returns_diff_string(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)
    result = gen.apply([make_gitignore_action("vendor")], dry_run=True)
    assert isinstance(result, str)
