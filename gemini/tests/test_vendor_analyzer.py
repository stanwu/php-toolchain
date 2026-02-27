import pytest
import os
from pathlib import Path
from core.models import FileRecord, AnalysisResult, ActionType, RiskLevel
from analyzers.vendor_analyzer import VendorAnalyzer

# Test fixture records
@pytest.fixture
def sample_records():
    return {
        "index.php": FileRecord("index.php", 1, 2),
        "vendor/autoload.php": FileRecord("vendor/autoload.php", 0, 0),
        "vendor/lib/a.php": FileRecord("vendor/lib/a.php", 1, 2),
        "vendor/lib/b.php": FileRecord("vendor/lib/b.php", 0, 0),
        "node_modules/react/index.js": FileRecord("node_modules/react/index.js", 0, 0),
        "app/service.php": FileRecord("app/service.php", 2, 5),
    }

@pytest.fixture
def nested_vendor_records():
    return {
        "index.php": FileRecord("index.php", 1, 2),
        f"project{os.sep}vendor{os.sep}lib{os.sep}tool.php": FileRecord(f"project{os.sep}vendor{os.sep}lib{os.sep}tool.php", 0, 0),
        f"project{os.sep}vendor{os.sep}lib{os.sep}another.php": FileRecord(f"project{os.sep}vendor{os.sep}lib{os.sep}another.php", 1, 1),
    }

@pytest.fixture
def no_vendor_records():
    return {
        "index.php": FileRecord("index.php", 1, 2),
        "app/service.php": FileRecord("app/service.php", 2, 5),
    }

# Initialize analyzer with sample records
@pytest.fixture
def analyzer(sample_records):
    return VendorAnalyzer(records=sample_records, project_dir=Path("/fake/project"))

# Test cases
def test_returns_analysis_result(analyzer):
    """test_returns_analysis_result: `analyze()` returns `AnalysisResult`"""
    result = analyzer.analyze()
    assert isinstance(result, AnalysisResult)

def test_analyzer_name(analyzer):
    """test_analyzer_name: `result.analyzer_name == "vendor_analyzer"`"""
    result = analyzer.analyze()
    assert result.analyzer_name == "vendor_analyzer"

def test_detects_vendor_root(analyzer):
    """test_detects_vendor_root: `"vendor/"` appears in `metadata["vendor_roots"]`"""
    result = analyzer.analyze()
    assert "vendor/" in result.metadata["vendor_roots"]

def test_detects_node_modules(analyzer):
    """test_detects_node_modules: `"node_modules/"` appears in `metadata["vendor_roots"]`"""
    result = analyzer.analyze()
    assert "node_modules/" in result.metadata["vendor_roots"]

def test_vendor_file_count(analyzer):
    """test_vendor_file_count: `vendor` root has `file_count == 3`"""
    result = analyzer.analyze()
    assert result.metadata["vendor_roots"]["vendor/"]["file_count"] == 3

def test_non_vendor_not_detected(analyzer):
    """test_non_vendor_not_detected: `"app"` is NOT in `metadata["vendor_roots"]`"""
    result = analyzer.analyze()
    assert not any(key.startswith("app") for key in result.metadata["vendor_roots"])

def test_one_action_per_vendor_root(analyzer):
    """test_one_action_per_vendor_root: 2 actions generated (vendor + node_modules)"""
    result = analyzer.analyze()
    assert len(result.actions) == 2

def test_action_type_is_gitignore(analyzer):
    """test_action_type_is_gitignore: All actions have `ActionType.ADD_GITIGNORE`"""
    result = analyzer.analyze()
    assert all(action.action_type == ActionType.ADD_GITIGNORE for action in result.actions)

def test_action_risk_is_low(analyzer):
    """test_action_risk_is_low: All actions have `RiskLevel.LOW`"""
    result = analyzer.analyze()
    assert all(action.risk_level == RiskLevel.LOW for action in result.actions)

def test_action_reason_contains_count(analyzer):
    """test_action_reason_contains_count: `reason` contains the file count"""
    result = analyzer.analyze()
    vendor_action = next(a for a in result.actions if a.source == "vendor")
    node_action = next(a for a in result.actions if a.source == "node_modules")
    assert "contains 3 files" in vendor_action.reason
    assert "contains 1 files" in node_action.reason

def test_no_vendor_no_actions(no_vendor_records):
    """test_no_vendor_no_actions: Records with no vendor paths -> 0 actions"""
    analyzer = VendorAnalyzer(records=no_vendor_records, project_dir=Path("/fake/project"))
    result = analyzer.analyze()
    assert len(result.actions) == 0
    assert result.metadata["total_vendor_files"] == 0

def test_nested_vendor(nested_vendor_records):
    """test_nested_vendor: `"test/vendor/x.php"` detected as vendor under `"project/vendor"`"""
    analyzer = VendorAnalyzer(records=nested_vendor_records, project_dir=Path("/fake/project"))
    result = analyzer.analyze()
    
    expected_root = os.path.join("project", "vendor")
    expected_metadata_key = "project/vendor/"

    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.source == expected_root
    assert expected_metadata_key in result.metadata["vendor_roots"]
    assert result.metadata["vendor_roots"][expected_metadata_key]["file_count"] == 2
    assert "contains 2 files" in action.reason

def test_is_vendor_path_logic(analyzer):
    """Test the internal _is_vendor_path logic with various inputs."""
    assert analyzer._is_vendor_path("vendor/lib/x.php") == (True, "vendor")
    assert analyzer._is_vendor_path(f"test{os.sep}vendor{os.sep}y.php") == (True, os.path.join("test", "vendor"))
    assert analyzer._is_vendor_path("node_modules/react/index.js") == (True, "node_modules")
    assert analyzer._is_vendor_path("src/app.js") == (False, "")
    assert analyzer._is_vendor_path("not_vendor/file.php") == (False, "")
