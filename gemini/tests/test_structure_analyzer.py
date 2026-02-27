"""
Tests for the StructureAnalyzer module.
"""
import pytest
from core.models import FileRecord, AnalysisResult, ActionType, RiskLevel
from analyzers.structure_analyzer import StructureAnalyzer

@pytest.fixture
def base_records() -> dict[str, FileRecord]:
    """
    Fixture with three directories, where 'a' and 'b' have a Jaccard
    similarity of 0.6, which is below the default threshold.
    Jaccard(a, b) = |{foo,bar,baz}| / |{foo,bar,baz,qux,zzz}| = 3/5 = 0.6
    """
    return {
        # dir "a/" — 4 files
        "a/foo.php":   FileRecord(path="a/foo.php",   max_depth=0, total_branches=0),
        "a/bar.php":   FileRecord(path="a/bar.php",   max_depth=0, total_branches=0),
        "a/baz.php":   FileRecord(path="a/baz.php",   max_depth=0, total_branches=0),
        "a/qux.php":   FileRecord(path="a/qux.php",   max_depth=0, total_branches=0),
        # dir "b/" — 3 of the same basenames + 1 different
        "b/foo.php":   FileRecord(path="b/foo.php",   max_depth=0, total_branches=0),
        "b/bar.php":   FileRecord(path="b/bar.php",   max_depth=0, total_branches=0),
        "b/baz.php":   FileRecord(path="b/baz.php",   max_depth=0, total_branches=0),
        "b/zzz.php":   FileRecord(path="b/zzz.php",   max_depth=0, total_branches=0),
        # dir "c/" — completely different
        "c/alpha.php": FileRecord(path="c/alpha.php", max_depth=0, total_branches=0),
        "c/beta.php":  FileRecord(path="c/beta.php",  max_depth=0, total_branches=0),
        # root-level file
        "index.php":   FileRecord(path="index.php",   max_depth=0, total_branches=0),
    }

@pytest.fixture
def medium_similarity_records() -> dict[str, FileRecord]:
    """
    Fixture where 'api' and 'api_v2' have 80% similarity.
    Jaccard = |4 common| / |5 total| = 0.8
    """
    return {
        "api/users.php": FileRecord(path="api/users.php", max_depth=0, total_branches=0),
        "api/products.php": FileRecord(path="api/products.php", max_depth=0, total_branches=0),
        "api/orders.php": FileRecord(path="api/orders.php", max_depth=0, total_branches=0),
        "api/common.php": FileRecord(path="api/common.php", max_depth=0, total_branches=0),
        "api/legacy.php": FileRecord(path="api/legacy.php", max_depth=0, total_branches=0),

        "api_v2/users.php": FileRecord(path="api_v2/users.php", max_depth=0, total_branches=0),
        "api_v2/products.php": FileRecord(path="api_v2/products.php", max_depth=0, total_branches=0),
        "api_v2/orders.php": FileRecord(path="api_v2/orders.php", max_depth=0, total_branches=0),
        "api_v2/common.php": FileRecord(path="api_v2/common.php", max_depth=0, total_branches=0),
    }

@pytest.fixture
def high_similarity_records() -> dict[str, FileRecord]:
    """
    Fixture where 'services' and 'services_old' have > 90% similarity.
    Jaccard = |9 common| / |10 total| = 0.9
    """
    records = {}
    for i in range(10):
        records[f"services/file_{i}.php"] = FileRecord(path=f"services/file_{i}.php", max_depth=0, total_branches=0)
    for i in range(9):
        records[f"services_old/file_{i}.php"] = FileRecord(path=f"services_old/file_{i}.php", max_depth=0, total_branches=0)
    return records


def test_returns_analysis_result(base_records):
    analyzer = StructureAnalyzer(base_records)
    result = analyzer.analyze()
    assert isinstance(result, AnalysisResult)

def test_analyzer_name(base_records):
    analyzer = StructureAnalyzer(base_records)
    result = analyzer.analyze()
    assert result.analyzer_name == "structure_analyzer"

def test_jaccard_identical():
    analyzer = StructureAnalyzer({})
    set_a = {"a", "b"}
    assert analyzer._jaccard(set_a, set_a) == 1.0

def test_jaccard_disjoint():
    analyzer = StructureAnalyzer({})
    set_a = {"a"}
    set_b = {"b"}
    assert analyzer._jaccard(set_a, set_b) == 0.0

def test_jaccard_partial():
    analyzer = StructureAnalyzer({})
    set_a = {"a", "b", "c"}
    set_b = {"a", "b", "d"}
    # Intersection = {"a", "b"} (size 2)
    # Union = {"a", "b", "c", "d"} (size 4)
    # Jaccard = 2 / 4 = 0.5
    assert analyzer._jaccard(set_a, set_b) == pytest.approx(0.5)

def test_jaccard_empty():
    analyzer = StructureAnalyzer({})
    assert analyzer._jaccard(set(), set()) == 0.0

def test_no_similar_pairs_below_threshold(base_records):
    analyzer = StructureAnalyzer(base_records)
    result = analyzer.analyze()
    assert len(result.actions) == 0
    assert len(result.metadata["similar_pairs"]) == 0

def test_detects_similar_pair(high_similarity_records):
    analyzer = StructureAnalyzer(high_similarity_records)
    result = analyzer.analyze()
    assert len(result.actions) == 1
    assert len(result.metadata["similar_pairs"]) == 1

def test_no_duplicate_pairs(high_similarity_records):
    # The analyzer should report ('services', 'services_old') but not also
    # ('services_old', 'services'). The implementation uses itertools.combinations
    # which prevents this automatically.
    analyzer = StructureAnalyzer(high_similarity_records)
    result = analyzer.analyze()
    assert len(result.actions) == 1
    pair = result.metadata["similar_pairs"][0]
    # Check for canonical ordering
    assert pair["dir_a"] < pair["dir_b"]

def test_high_risk_above_90(high_similarity_records):
    analyzer = StructureAnalyzer(high_similarity_records)
    result = analyzer.analyze()
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.risk_level == RiskLevel.HIGH
    assert "Jaccard=0.90" in action.reason

def test_medium_risk_above_70(medium_similarity_records):
    analyzer = StructureAnalyzer(medium_similarity_records)
    result = analyzer.analyze()
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.risk_level == RiskLevel.MEDIUM
    assert "Jaccard=0.80" in action.reason
    assert action.source == "api"
    assert action.destination == "api_v2"

def test_metadata_similar_pairs(medium_similarity_records):
    analyzer = StructureAnalyzer(medium_similarity_records)
    result = analyzer.analyze()
    assert "similar_pairs" in result.metadata
    pairs = result.metadata["similar_pairs"]
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["dir_a"] == "api"
    assert pair["dir_b"] == "api_v2"
    assert pair["similarity"] == pytest.approx(0.8)
    assert pair["common_files"] == ["common.php", "orders.php", "products.php", "users.php"]
    assert pair["only_in_a"] == ["legacy.php"]
    assert pair["only_in_b"] == []

def test_metadata_total_directories(base_records):
    analyzer = StructureAnalyzer(base_records)
    result = analyzer.analyze()
    # Directories are "", "a", "b", "c"
    assert result.metadata["total_directories"] == 4
