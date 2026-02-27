from __future__ import annotations

from pathlib import Path

from core.models import Action, ActionType, RiskLevel
from executors.gitignore_gen import GitignoreGen


def make_gitignore_action(source: str) -> Action:
    return Action(ActionType.ADD_GITIGNORE, source, None, RiskLevel.LOW, "test")


def make_delete_action(source: str) -> Action:
    return Action(ActionType.DELETE, source, None, RiskLevel.LOW, "test")


def test_read_existing_returns_lines(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n*.log\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    lines = gen.read_existing()

    assert lines == [".env\n", "*.log\n"]


def test_read_existing_no_file_returns_empty(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)

    assert gen.read_existing() == []


def test_generate_new_entries_format(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)

    new_entries = gen.generate_new_entries([make_gitignore_action("vendor")])

    assert "/vendor/\n" in new_entries


def test_generate_skips_existing_entries(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("/vendor/\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    new_entries = gen.generate_new_entries([make_gitignore_action("vendor")])

    assert "/vendor/\n" not in new_entries
    assert new_entries == []


def test_generate_sorted(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)

    new_entries = gen.generate_new_entries(
        [
            make_gitignore_action("node_modules"),
            make_gitignore_action("vendor"),
        ]
    )

    assert new_entries == ["/node_modules/\n", "/vendor/\n"]


def test_generate_only_gitignore_actions(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)

    new_entries = gen.generate_new_entries([make_delete_action("vendor"), make_gitignore_action("vendor")])

    assert new_entries == ["/vendor/\n"]


def test_build_adds_comment(tmp_path: Path) -> None:
    gen = GitignoreGen(tmp_path)

    content = gen.build_updated_content(["/vendor/\n"])

    assert "# Added by php-cleanup-toolkit" in content


def test_build_preserves_existing(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n*.log\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    content = gen.build_updated_content(["/vendor/\n"])

    assert ".env\n" in content
    assert "*.log\n" in content


def test_build_newline_before_additions(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n*.log\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    content = gen.build_updated_content(["/vendor/\n"])

    assert "\n\n# Added by php-cleanup-toolkit" in content


def test_diff_shows_added_lines(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    new_content = gen.build_updated_content(["/vendor/\n"])
    diff_str = gen.diff(new_content)

    assert "+/vendor/" in diff_str


def test_diff_empty_if_no_changes(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    diff_str = gen.diff(".env\n")

    assert diff_str == ""


def test_apply_dry_run_no_write(tmp_path: Path) -> None:
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text(".env\n", encoding="utf-8")
    original = gitignore_path.read_text(encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    diff_str = gen.apply([make_gitignore_action("vendor")], dry_run=True)

    assert isinstance(diff_str, str)
    assert gitignore_path.read_text(encoding="utf-8") == original


def test_apply_writes_file(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    gen.apply([make_gitignore_action("vendor")], dry_run=False)

    assert "/vendor/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_apply_returns_diff_string(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    gen = GitignoreGen(tmp_path)

    diff_str = gen.apply([make_gitignore_action("vendor")], dry_run=False)

    assert isinstance(diff_str, str)

