import pytest

from analyzers.structure_analyzer import SIMILARITY_THRESHOLD, StructureAnalyzer
from core.models import ActionType, AnalysisResult, FileRecord, RiskLevel


def _rec(path: str) -> FileRecord:
    return FileRecord(path, 0, 0)


# ---------- Fixtures ----------

@pytest.fixture
def default_records() -> dict[str, FileRecord]:
    """
    a/ vs b/: Jaccard = |{foo,bar,baz}| / |{foo,bar,baz,qux,zzz}| = 3/5 = 0.6
    All other pairs are disjoint.
    Nothing reaches the 0.7 threshold → 0 actions.
    """
    return {
        "a/foo.php":   _rec("a/foo.php"),
        "a/bar.php":   _rec("a/bar.php"),
        "a/baz.php":   _rec("a/baz.php"),
        "a/qux.php":   _rec("a/qux.php"),
        "b/foo.php":   _rec("b/foo.php"),
        "b/bar.php":   _rec("b/bar.php"),
        "b/baz.php":   _rec("b/baz.php"),
        "b/zzz.php":   _rec("b/zzz.php"),
        "c/alpha.php": _rec("c/alpha.php"),
        "c/beta.php":  _rec("c/beta.php"),
    }


@pytest.fixture
def high_overlap_records() -> dict[str, FileRecord]:
    """
    x/ and y/ share 10 files; y/ has 1 extra.
    Jaccard = 10/11 ≈ 0.909 → HIGH risk, above threshold.
    """
    shared = [f"f{i}.php" for i in range(1, 11)]
    records: dict[str, FileRecord] = {}
    for f in shared:
        records[f"x/{f}"] = _rec(f"x/{f}")
        records[f"y/{f}"] = _rec(f"y/{f}")
    records["y/extra.php"] = _rec("y/extra.php")
    return records


@pytest.fixture
def medium_overlap_records() -> dict[str, FileRecord]:
    """
    p/ and q/ share 7 files; each has 1 unique file.
    Jaccard = 7/9 ≈ 0.778 → MEDIUM risk.
    """
    shared = [f"f{i}.php" for i in range(1, 8)]
    records: dict[str, FileRecord] = {}
    for f in shared:
        records[f"p/{f}"] = _rec(f"p/{f}")
        records[f"q/{f}"] = _rec(f"q/{f}")
    records["p/only_p.php"] = _rec("p/only_p.php")
    records["q/only_q.php"] = _rec("q/only_q.php")
    return records


# ---------- Tests ----------

def test_returns_analysis_result(default_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(default_records).analyze()
    assert isinstance(result, AnalysisResult)


def test_analyzer_name(default_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(default_records).analyze()
    assert result.analyzer_name == "structure_analyzer"


def test_jaccard_identical() -> None:
    sa = StructureAnalyzer({})
    assert sa._jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint() -> None:
    sa = StructureAnalyzer({})
    assert sa._jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial() -> None:
    sa = StructureAnalyzer({})
    # intersection={a,b}=2, union={a,b,c,d}=4 → 0.5
    assert sa._jaccard({"a", "b", "c"}, {"a", "b", "d"}) == pytest.approx(0.5)


def test_jaccard_empty() -> None:
    sa = StructureAnalyzer({})
    assert sa._jaccard(set(), set()) == 0.0


def test_no_similar_pairs_below_threshold(default_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(default_records).analyze()
    assert len(result.actions) == 0


def test_detects_similar_pair(high_overlap_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(high_overlap_records).analyze()
    assert len(result.actions) == 1
    assert result.actions[0].action_type == ActionType.REPORT_ONLY


def test_no_duplicate_pairs(high_overlap_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(high_overlap_records).analyze()
    pairs = [(a.source, a.destination) for a in result.actions]
    for source, dest in pairs:
        assert (dest, source) not in pairs, (
            f"Both ({source},{dest}) and ({dest},{source}) reported"
        )


def test_high_risk_above_90(high_overlap_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(high_overlap_records).analyze()
    assert len(result.actions) == 1
    assert result.actions[0].risk_level == RiskLevel.HIGH


def test_medium_risk_above_70(medium_overlap_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(medium_overlap_records).analyze()
    assert len(result.actions) == 1
    assert result.actions[0].risk_level == RiskLevel.MEDIUM


def test_metadata_similar_pairs(high_overlap_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(high_overlap_records).analyze()
    pairs = result.metadata["similar_pairs"]
    assert len(pairs) == 1
    pair = pairs[0]
    for key in ("dir_a", "dir_b", "similarity", "common_files", "only_in_a", "only_in_b"):
        assert key in pair, f"Missing key '{key}' in similar_pairs entry"
    assert pair["similarity"] >= 0.9
    assert set(pair["common_files"]) == {f"f{i}.php" for i in range(1, 11)}
    assert "extra.php" in pair["only_in_b"] or "extra.php" in pair["only_in_a"]


def test_metadata_total_directories(default_records: dict[str, FileRecord]) -> None:
    result = StructureAnalyzer(default_records).analyze()
    # default fixture has dirs: "a", "b", "c"
    assert result.metadata["total_directories"] == 3
