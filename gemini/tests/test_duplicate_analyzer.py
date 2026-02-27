import hashlib
import pytest
from pathlib import Path
from typing import Dict

from core.models import FileRecord, RiskLevel, ActionType, Action
from analyzers.duplicate_analyzer import DuplicateAnalyzer

@pytest.fixture
def project_with_duplicates(tmp_path: Path) -> Dict:
    """Creates a temporary project with duplicate files and returns analyzer and records."""
    project_dir = tmp_path
    (project_dir / "subdir").mkdir()

    files_content = {
        "utils.php": "<?php function helper(){}",
        "utils_copy.php": "<?php function helper(){}",
        "service.php": "<?php class Service{}",
        "subdir/service_old.php": "<?php class Service{}",
        "unique.php": "<?php echo 1;",
        "ambiguous1.php": "ambiguous content",
        "ambiguous2.php": "ambiguous content",
        "nonexistent.php": "I am not real",
        "empty.php": ""
    }

    records = {}
    for name, content in files_content.items():
        path = project_dir / name
        if name != "nonexistent.php":
            path.write_text(content)
        
        records[name] = FileRecord(
            path=name,
            max_depth=1,
            total_branches=1,
            exists_on_disk=(name != "nonexistent.php")
        )

    analyzer = DuplicateAnalyzer(records=records, project_dir=project_dir)
    return {"analyzer": analyzer, "records": records, "project_dir": project_dir}


def test_returns_analysis_result(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    assert result.__class__.__name__ == "AnalysisResult"

def test_analyzer_name(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    assert result.analyzer_name == "duplicate_analyzer"

def test_finds_three_groups(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    # utils+utils_copy, service+service_old, ambiguous1+ambiguous2
    assert len(result.metadata["groups"]) == 3

def test_unique_file_not_in_groups(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    all_grouped_files = {file for group in result.metadata["groups"] for file in group["files"]}
    assert "unique.php" not in all_grouped_files
    assert "empty.php" not in all_grouped_files

def test_canonical_inference_copy_suffix(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    utils_group = next(g for g in result.metadata["groups"] if "utils.php" in g["files"])
    assert utils_group["canonical"] == "utils.php"
    assert "utils_copy.php" in utils_group["copies"]

def test_canonical_inference_old_suffix(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    service_group = next(g for g in result.metadata["groups"] if "service.php" in g["files"])
    assert service_group["canonical"] == "service.php"
    assert "subdir/service_old.php" in service_group["copies"]

def test_delete_action_for_copy(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    actions_sources = {a.source for a in result.actions}
    assert "utils_copy.php" in actions_sources
    assert "subdir/service_old.php" in actions_sources
    assert "utils.php" not in actions_sources
    assert "service.php" not in actions_sources

def test_medium_risk_clear_canonical(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    utils_action = next(a for a in result.actions if a.source == "utils_copy.php")
    service_action = next(a for a in result.actions if a.source == "subdir/service_old.php")
    assert utils_action.risk_level == RiskLevel.MEDIUM
    assert service_action.risk_level == RiskLevel.MEDIUM

def test_high_risk_ambiguous(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    ambiguous_actions = [a for a in result.actions if "ambiguous" in a.source]
    assert len(ambiguous_actions) == 2
    assert all(a.risk_level == RiskLevel.HIGH for a in ambiguous_actions)
    
    ambiguous_group = next(g for g in result.metadata["groups"] if "ambiguous1.php" in g["files"])
    assert ambiguous_group["canonical"] is None

def test_skips_nonexistent_files(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    result = analyzer.analyze()
    all_grouped_files = {file for group in result.metadata["groups"] for file in group["files"]}
    assert "nonexistent.php" not in all_grouped_files

def test_hash_uses_sha256(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    project_dir = project_with_duplicates["project_dir"]
    file_path = project_dir / "unique.php"
    file_hash = analyzer._hash_file(file_path)
    assert file_hash is not None
    assert len(file_hash) == 64
    
    content = file_path.read_bytes()
    expected_hash = hashlib.sha256(content).hexdigest()
    assert file_hash == expected_hash

def test_metadata_total_wasted_bytes(project_with_duplicates):
    analyzer = project_with_duplicates["analyzer"]
    project_dir = project_with_duplicates["project_dir"]
    result = analyzer.analyze()
    
    wasted_bytes = 0
    wasted_bytes += (project_dir / "utils_copy.php").stat().st_size
    wasted_bytes += (project_dir / "subdir/service_old.php").stat().st_size
    wasted_bytes += (project_dir / "ambiguous2.php").stat().st_size

    assert result.metadata["total_wasted_bytes"] == wasted_bytes
    assert result.metadata["total_wasted_bytes"] > 0

def test_no_duplicates_no_actions(tmp_path):
    project_dir = tmp_path
    files_content = {
        "file1.php": "content1",
        "file2.php": "content2",
        "file3.php": "content3",
    }
    records = {}
    for name, content in files_content.items():
        path = project_dir / name
        path.write_text(content)
        records[name] = FileRecord(path=name, max_depth=1, total_branches=1, exists_on_disk=True)

    analyzer = DuplicateAnalyzer(records=records, project_dir=project_dir)
    result = analyzer.analyze()

    assert len(result.actions) == 0
    assert len(result.metadata["groups"]) == 0
    assert result.metadata["total_duplicate_files"] == 0
    assert result.metadata["total_wasted_bytes"] == 0

def test_score_path_logic():
    analyzer = DuplicateAnalyzer({}, Path("."))
    
    assert analyzer._score_path("a/b/c.php") < analyzer._score_path("a/b/c_copy.php")
    assert analyzer._score_path("a/b/c.php") < analyzer._score_path("a/b/c_old.php")
    assert analyzer._score_path("a/b/c.php") < analyzer._score_path("a/b/c(1).php")
    assert analyzer._score_path("a/b/c.php") < analyzer._score_path("a/backup/c.php")
    
    assert analyzer._score_path("c.php") < analyzer._score_path("a/c.php") < analyzer._score_path("a/b/c.php")
