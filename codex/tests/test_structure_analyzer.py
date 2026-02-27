from __future__ import annotations

import pytest

from analyzers.structure_analyzer import SIMILARITY_THRESHOLD, StructureAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel


def _records_below_threshold() -> dict[str, FileRecord]:
    records = {
        # dir "a/" — 4 files
        "a/foo.php": FileRecord("a/foo.php", 0, 0),
        "a/bar.php": FileRecord("a/bar.php", 0, 0),
        "a/baz.php": FileRecord("a/baz.php", 0, 0),
        "a/qux.php": FileRecord("a/qux.php", 0, 0),
        # dir "b/" — 3 of same basenames + 1 different (Jaccard=3/5=0.6)
        "b/foo.php": FileRecord("b/foo.php", 0, 0),
        "b/bar.php": FileRecord("b/bar.php", 0, 0),
        "b/baz.php": FileRecord("b/baz.php", 0, 0),
        "b/zzz.php": FileRecord("b/zzz.php", 0, 0),
        # dir "c/" — completely different
        "c/alpha.php": FileRecord("c/alpha.php", 0, 0),
        "c/beta.php": FileRecord("c/beta.php", 0, 0),
    }
    return records


def _records_high_overlap() -> dict[str, FileRecord]:
    # Two different dirs with identical basenames (Jaccard=1.0)
    records: dict[str, FileRecord] = {}
    for name in ["a.php", "b.php", "c.php", "d.php", "e.php", "f.php", "g.php", "h.php", "i.php", "j.php"]:
        records[f"src/{name}"] = FileRecord(f"src/{name}", 0, 0)
        records[f"src_old/{name}"] = FileRecord(f"src_old/{name}", 0, 0)
    records["other/x.php"] = FileRecord("other/x.php", 0, 0)
    return records


def _records_medium_overlap() -> dict[str, FileRecord]:
    # Jaccard=7/9=0.777... → MEDIUM risk
    records: dict[str, FileRecord] = {}
    set_a = ["a.php", "b.php", "c.php", "d.php", "e.php", "f.php", "g.php", "h.php"]
    set_b = ["a.php", "b.php", "c.php", "d.php", "e.php", "f.php", "g.php", "x.php"]
    for name in set_a:
        records[f"a/{name}"] = FileRecord(f"a/{name}", 0, 0)
    for name in set_b:
        records[f"b/{name}"] = FileRecord(f"b/{name}", 0, 0)
    return records


def test_returns_analysis_result() -> None:
    result = StructureAnalyzer(_records_below_threshold()).analyze()
    assert isinstance(result, AnalysisResult)


def test_analyzer_name() -> None:
    result = StructureAnalyzer(_records_below_threshold()).analyze()
    assert result.analyzer_name == "structure_analyzer"


def test_jaccard_identical() -> None:
    analyzer = StructureAnalyzer({})
    assert analyzer._jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint() -> None:
    analyzer = StructureAnalyzer({})
    assert analyzer._jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial() -> None:
    analyzer = StructureAnalyzer({})
    assert analyzer._jaccard({"a", "b", "c"}, {"a", "b", "d"}) == pytest.approx(0.5)


def test_jaccard_empty() -> None:
    analyzer = StructureAnalyzer({})
    assert analyzer._jaccard(set(), set()) == 0.0


def test_no_similar_pairs_below_threshold() -> None:
    result = StructureAnalyzer(_records_below_threshold()).analyze()
    assert result.actions == []
    assert result.metadata["similar_pairs"] == []


def test_detects_similar_pair() -> None:
    result = StructureAnalyzer(_records_high_overlap()).analyze()
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.action_type == ActionType.REPORT_ONLY
    assert action.source == "src"
    assert action.destination == "src_old"
    assert "Jaccard=" in action.reason


def test_no_duplicate_pairs() -> None:
    result = StructureAnalyzer(_records_high_overlap()).analyze()
    pairs = {(a.source, a.destination) for a in result.actions}
    reversed_pairs = {(b, a) for a, b in pairs}
    assert pairs.isdisjoint(reversed_pairs)


def test_high_risk_above_90() -> None:
    result = StructureAnalyzer(_records_high_overlap()).analyze()
    assert result.actions[0].risk_level == RiskLevel.HIGH


def test_medium_risk_above_70() -> None:
    assert SIMILARITY_THRESHOLD <= 0.7
    result = StructureAnalyzer(_records_medium_overlap()).analyze()
    assert len(result.actions) == 1
    assert result.actions[0].risk_level == RiskLevel.MEDIUM


def test_metadata_similar_pairs() -> None:
    result = StructureAnalyzer(_records_high_overlap()).analyze()
    pairs = result.metadata["similar_pairs"]
    assert len(pairs) == 1
    entry = pairs[0]
    assert entry["dir_a"] == "src"
    assert entry["dir_b"] == "src_old"
    assert entry["similarity"] == pytest.approx(1.0)
    assert entry["common_files"] == sorted(
        ["a.php", "b.php", "c.php", "d.php", "e.php", "f.php", "g.php", "h.php", "i.php", "j.php"]
    )
    assert entry["only_in_a"] == []
    assert entry["only_in_b"] == []


def test_metadata_total_directories() -> None:
    records = {
        "root1.php": FileRecord("root1.php", 0, 0),
        "root2.php": FileRecord("root2.php", 0, 0),
        "a/x.php": FileRecord("a/x.php", 0, 0),
    }
    result = StructureAnalyzer(records).analyze()
    assert result.metadata["total_directories"] == 2

