from __future__ import annotations

from pathlib import Path

import pytest

from analyzers.duplicate_analyzer import DuplicateAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel


def _write(tmp_path: Path, rel: str, content: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _fixture_records_all_exist() -> dict[str, FileRecord]:
    return {
        "utils.php": FileRecord("utils.php", 0, 0, exists_on_disk=True),
        "utils_copy.php": FileRecord("utils_copy.php", 0, 0, exists_on_disk=True),
        "service.php": FileRecord("service.php", 0, 0, exists_on_disk=True),
        "service_old.php": FileRecord("service_old.php", 0, 0, exists_on_disk=True),
        "unique.php": FileRecord("unique.php", 0, 0, exists_on_disk=True),
    }


@pytest.fixture
def project_with_duplicates(tmp_path: Path) -> tuple[Path, dict[str, FileRecord]]:
    _write(tmp_path, "utils.php", "<?php function helper(){}")
    _write(tmp_path, "utils_copy.php", "<?php function helper(){}")
    _write(tmp_path, "service.php", "<?php class Service{}")
    _write(tmp_path, "service_old.php", "<?php class Service{}")
    _write(tmp_path, "unique.php", "<?php echo 1;")
    return tmp_path, _fixture_records_all_exist()


def test_returns_analysis_result(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    assert isinstance(result, AnalysisResult)


def test_analyzer_name(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    assert result.analyzer_name == "duplicate_analyzer"


def test_finds_two_groups(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    groups = result.metadata["groups"]
    assert len(groups) == 2


def test_unique_file_not_in_groups(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    groups = result.metadata["groups"]
    all_group_files = {p for g in groups for p in g["files"]}
    assert "unique.php" not in all_group_files


def test_canonical_inference_copy_suffix(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    group = next(g for g in result.metadata["groups"] if "utils.php" in g["files"])
    assert group["canonical"] == "utils.php"
    assert "utils_copy.php" in group["copies"]


def test_canonical_inference_old_suffix(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    group = next(g for g in result.metadata["groups"] if "service.php" in g["files"])
    assert group["canonical"] == "service.php"
    assert "service_old.php" in group["copies"]


def test_delete_action_for_copy(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    delete_sources = {a.source for a in result.actions if a.action_type == ActionType.DELETE}
    assert delete_sources == {"utils_copy.php", "service_old.php"}


def test_medium_risk_clear_canonical(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    assert all(a.risk_level == RiskLevel.MEDIUM for a in result.actions)


def test_high_risk_ambiguous(tmp_path: Path) -> None:
    _write(tmp_path, "a.php", "<?php echo 'x';")
    _write(tmp_path, "b.php", "<?php echo 'x';")
    records = {
        "a.php": FileRecord("a.php", 0, 0, exists_on_disk=True),
        "b.php": FileRecord("b.php", 0, 0, exists_on_disk=True),
    }
    result = DuplicateAnalyzer(records, tmp_path).analyze()
    assert len(result.actions) == 1
    assert result.actions[0].risk_level == RiskLevel.HIGH


def test_skips_nonexistent_files(tmp_path: Path) -> None:
    _write(tmp_path, "real.php", "<?php echo 'x';")
    records = {
        "real.php": FileRecord("real.php", 0, 0, exists_on_disk=True),
        "ghost.php": FileRecord("ghost.php", 0, 0, exists_on_disk=False),
    }
    result = DuplicateAnalyzer(records, tmp_path).analyze()
    assert result.metadata["groups"] == []
    assert result.actions == []


def test_hash_uses_sha256(tmp_path: Path) -> None:
    _write(tmp_path, "x.php", "<?php echo 1;")
    analyzer = DuplicateAnalyzer({"x.php": FileRecord("x.php", 0, 0, exists_on_disk=True)}, tmp_path)
    digest = analyzer._hash_file(tmp_path / "x.php")
    assert digest is not None
    assert len(digest) == 64


def test_metadata_total_wasted_bytes(project_with_duplicates: tuple[Path, dict[str, FileRecord]]) -> None:
    project_dir, records = project_with_duplicates
    result = DuplicateAnalyzer(records, project_dir).analyze()
    assert result.metadata["total_wasted_bytes"] > 0


def test_no_duplicates_no_actions(tmp_path: Path) -> None:
    _write(tmp_path, "a.php", "<?php echo 1;")
    _write(tmp_path, "b.php", "<?php echo 2;")
    _write(tmp_path, "c.php", "<?php echo 3;")
    records = {
        "a.php": FileRecord("a.php", 0, 0, exists_on_disk=True),
        "b.php": FileRecord("b.php", 0, 0, exists_on_disk=True),
        "c.php": FileRecord("c.php", 0, 0, exists_on_disk=True),
    }
    result = DuplicateAnalyzer(records, tmp_path).analyze()
    assert result.metadata["groups"] == []
    assert result.actions == []

