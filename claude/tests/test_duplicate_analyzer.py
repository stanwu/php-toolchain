"""Tests for analyzers/duplicate_analyzer.py"""
import pytest
from pathlib import Path

from analyzers.duplicate_analyzer import DuplicateAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel


CONTENT_HELPER = b"<?php function helper(){}"
CONTENT_SERVICE = b"<?php class Service{}"
CONTENT_UNIQUE = b"<?php echo 1;"


def make_records(tmp_path: Path, names: list[str]) -> dict[str, FileRecord]:
    return {
        name: FileRecord(path=name, max_depth=1, total_branches=1, exists_on_disk=True)
        for name in names
    }


@pytest.fixture
def dup_setup(tmp_path: Path):
    files = {
        "utils.php": CONTENT_HELPER,
        "utils_copy.php": CONTENT_HELPER,
        "service.php": CONTENT_SERVICE,
        "service_old.php": CONTENT_SERVICE,
        "unique.php": CONTENT_UNIQUE,
    }
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)

    records = make_records(tmp_path, list(files.keys()))
    analyzer = DuplicateAnalyzer(records=records, project_dir=tmp_path)
    return analyzer, tmp_path


# ---------------------------------------------------------------------------
# Basic return type & name
# ---------------------------------------------------------------------------

def test_returns_analysis_result(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    assert isinstance(result, AnalysisResult)


def test_analyzer_name(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    assert result.analyzer_name == "duplicate_analyzer"


# ---------------------------------------------------------------------------
# Group detection
# ---------------------------------------------------------------------------

def test_finds_two_groups(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    groups = result.metadata["groups"]
    assert len(groups) == 2


def test_unique_file_not_in_groups(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    all_group_files = [f for g in result.metadata["groups"] for f in g["files"]]
    assert "unique.php" not in all_group_files


# ---------------------------------------------------------------------------
# Canonical inference
# ---------------------------------------------------------------------------

def test_canonical_inference_copy_suffix(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    # Find the group containing utils.php
    group = next(
        g for g in result.metadata["groups"] if "utils.php" in g["files"]
    )
    assert group["canonical"] == "utils.php"
    assert "utils_copy.php" in group["copies"]


def test_canonical_inference_old_suffix(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    group = next(
        g for g in result.metadata["groups"] if "service.php" in g["files"]
    )
    assert group["canonical"] == "service.php"
    assert "service_old.php" in group["copies"]


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def test_delete_action_for_copy(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    sources = {a.source for a in result.actions}
    assert "utils_copy.php" in sources
    assert "service_old.php" in sources
    for action in result.actions:
        assert action.action_type == ActionType.DELETE
        assert action.destination is None


def test_medium_risk_clear_canonical(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    # utils_copy.php and service_old.php both have clear canonicals → MEDIUM
    copy_actions = [
        a for a in result.actions
        if a.source in ("utils_copy.php", "service_old.php")
    ]
    assert len(copy_actions) == 2
    for action in copy_actions:
        assert action.risk_level == RiskLevel.MEDIUM


def test_high_risk_ambiguous(tmp_path: Path):
    """Two files with no copy/old/etc suffixes → equal scores → HIGH risk."""
    content = b"<?php echo 'same';"
    (tmp_path / "alpha.php").write_bytes(content)
    (tmp_path / "beta.php").write_bytes(content)

    records = {
        "alpha.php": FileRecord(path="alpha.php", max_depth=0, total_branches=0),
        "beta.php": FileRecord(path="beta.php", max_depth=0, total_branches=0),
    }
    analyzer = DuplicateAnalyzer(records=records, project_dir=tmp_path)
    result = analyzer.analyze()

    assert len(result.actions) > 0
    for action in result.actions:
        assert action.risk_level == RiskLevel.HIGH


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_skips_nonexistent_files(tmp_path: Path):
    content = b"<?php echo 'hi';"
    (tmp_path / "real.php").write_bytes(content)

    records = {
        "real.php": FileRecord(path="real.php", max_depth=0, total_branches=0, exists_on_disk=True),
        "ghost.php": FileRecord(path="ghost.php", max_depth=0, total_branches=0, exists_on_disk=False),
    }
    analyzer = DuplicateAnalyzer(records=records, project_dir=tmp_path)
    result = analyzer.analyze()
    # ghost.php has exists_on_disk=False, so no duplicate group
    all_group_files = [f for g in result.metadata["groups"] for f in g["files"]]
    assert "ghost.php" not in all_group_files
    assert len(result.actions) == 0


def test_hash_uses_sha256(tmp_path: Path):
    """_hash_file() must return a 64-character hex string (SHA-256, not 32-char MD5)."""
    f = tmp_path / "file.php"
    f.write_bytes(b"<?php echo 1;")
    records = {"file.php": FileRecord(path="file.php", max_depth=0, total_branches=0)}
    analyzer = DuplicateAnalyzer(records=records, project_dir=tmp_path)
    digest = analyzer._hash_file(f)
    assert digest is not None
    assert len(digest) == 64


def test_metadata_total_wasted_bytes(dup_setup):
    analyzer, _ = dup_setup
    result = analyzer.analyze()
    assert result.metadata["total_wasted_bytes"] > 0


def test_no_duplicates_no_actions(tmp_path: Path):
    (tmp_path / "a.php").write_bytes(b"<?php echo 1;")
    (tmp_path / "b.php").write_bytes(b"<?php echo 2;")
    (tmp_path / "c.php").write_bytes(b"<?php echo 3;")

    records = {
        "a.php": FileRecord(path="a.php", max_depth=0, total_branches=0),
        "b.php": FileRecord(path="b.php", max_depth=0, total_branches=0),
        "c.php": FileRecord(path="c.php", max_depth=0, total_branches=0),
    }
    analyzer = DuplicateAnalyzer(records=records, project_dir=tmp_path)
    result = analyzer.analyze()
    assert len(result.actions) == 0
    assert len(result.metadata["groups"]) == 0
