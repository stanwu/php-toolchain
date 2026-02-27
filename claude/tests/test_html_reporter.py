from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.models import Action, ActionPlan, ActionType, AnalysisResult, RiskLevel
from reporters.html_reporter import HTMLReporter


def make_plan_and_results():
    actions = [
        Action(ActionType.DELETE, "old.php", None, RiskLevel.LOW, "backup"),
        Action(ActionType.ADD_GITIGNORE, "vendor", None, RiskLevel.LOW, "vendor"),
        Action(ActionType.REPORT_ONLY, "saas/service.php", None, RiskLevel.HIGH, "complex"),
    ]
    plan = ActionPlan(actions=actions, project_dir="/project/my-php-project")
    results = [
        AnalysisResult("complexity_analyzer", [actions[2]], {
            "top10": [
                {
                    "file": "saas/service.php",
                    "score": 115,
                    "max_depth": 5,
                    "total_branches": 100,
                }
            ]
        })
    ]
    return plan, results


@pytest.fixture
def reporter():
    plan, results = make_plan_and_results()
    return HTMLReporter(plan, results, "/project/my-php-project")


@pytest.fixture
def rendered(reporter):
    return reporter.render()


def test_render_returns_string(rendered):
    assert isinstance(rendered, str)
    assert len(rendered) > 0


def test_render_is_valid_html_start(rendered):
    assert rendered.strip().startswith("<!DOCTYPE html>")


def test_render_contains_project_dir(rendered):
    assert "/project/my-php-project" in rendered


def test_render_contains_generated_date(rendered):
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    assert today in rendered


def test_summary_cards_counts(rendered):
    # Total action count is 3; the number 3 should appear in the cards section
    assert ">3<" in rendered


def test_action_table_sources(rendered):
    assert "old.php" in rendered
    assert "vendor" in rendered


def test_action_table_data_risk_attrs(rendered):
    assert 'data-risk="low"' in rendered


def test_complexity_heatmap_present(rendered):
    assert "saas/service.php" in rendered
    # Ensure it appears inside the complexity section
    complexity_start = rendered.find('id="complexity"')
    assert complexity_start != -1
    assert "saas/service.php" in rendered[complexity_start:]


def test_filter_js_present(rendered):
    assert "filterRisk" in rendered
    assert "<script>" in rendered


def test_no_external_urls(rendered):
    # Must be fully self-contained — no http links
    assert "http" not in rendered


def test_write_creates_file(tmp_path, reporter):
    out = tmp_path / "report.html"
    reporter.write(out)
    assert out.exists()


def test_write_file_readable(tmp_path, reporter):
    out = tmp_path / "report.html"
    reporter.write(out)
    assert out.read_text(encoding="utf-8") == reporter.render()


def test_xss_source_escaped(tmp_path):
    """Action source containing raw HTML must be escaped."""
    xss_source = "<script>alert(1)</script>.php"
    actions = [Action(ActionType.DELETE, xss_source, None, RiskLevel.LOW, "test")]
    plan = ActionPlan(actions=actions, project_dir="/proj")
    r = HTMLReporter(plan, [], "/proj")
    output = r.render()
    assert "&lt;script&gt;" in output
    # The raw tag must not appear outside of the already-escaped form
    # Split on the escaped version first, then check no raw tag remains
    assert "<script>alert(1)</script>.php" not in output


def test_xss_reason_escaped():
    """Action reason containing raw HTML must be escaped."""
    xss_reason = '<img src=x onerror=alert(1)>'
    actions = [Action(ActionType.DELETE, "file.php", None, RiskLevel.LOW, xss_reason)]
    plan = ActionPlan(actions=actions, project_dir="/proj")
    r = HTMLReporter(plan, [], "/proj")
    output = r.render()
    assert "&lt;img" in output
    assert xss_reason not in output


def test_xss_heatmap_file_escaped():
    """Heatmap file path with <> characters must be HTML-escaped."""
    xss_file = "<evil>path.php"
    actions = []
    plan = ActionPlan(actions=actions, project_dir="/proj")
    results = [
        AnalysisResult("complexity_analyzer", [], {
            "top10": [{"file": xss_file, "score": 50, "max_depth": 3, "total_branches": 10}]
        })
    ]
    r = HTMLReporter(plan, results, "/proj")
    output = r.render()
    assert "&lt;evil&gt;" in output
    assert "<evil>" not in output
