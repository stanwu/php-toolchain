import pytest
from pathlib import Path
from datetime import datetime
import html

from core.models import ActionPlan, Action, ActionType, RiskLevel, AnalysisResult
from reporters.html_reporter import HTMLReporter

def make_plan_and_results():
    actions = [
        Action(ActionType.DELETE, "old.php", None, RiskLevel.LOW, "backup"),
        Action(ActionType.ADD_GITIGNORE, "vendor", None, RiskLevel.LOW, "vendor"),
        Action(ActionType.REPORT_ONLY, "saas/service.php", None, RiskLevel.HIGH, "complex"),
    ]
    plan = ActionPlan(actions=actions, project_dir="/project/my-php-project", created_at="2023-10-27")
    results = [
        AnalysisResult("complexity_analyzer", [actions[2]], {
            "top10": [{"file": "saas/service.php", "score": 115, "max_depth": 5, "total_branches": 100}]
        }),
        AnalysisResult("other_analyzer", [], {})
    ]
    return plan, results

def test_render_returns_string():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert isinstance(output, str)
    assert len(output) > 0

def test_render_is_valid_html_start():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert output.lstrip().startswith("<!DOCTYPE html>")

def test_render_contains_project_dir():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert html.escape(plan.project_dir) in output

def test_render_contains_generated_date():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    today_str = datetime.now().strftime('%Y-%m-%d')
    assert today_str in output

def test_summary_cards_counts():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert '<span class="count">3</span>' in output # Total
    assert '<span class="count">2</span>' in output # Low
    assert '<span class="count">0</span>' in output # Medium
    assert '<span class="count">1</span>' in output # High

def test_action_table_sources():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert "<td>old.php</td>" in output
    assert "<td>vendor</td>" in output
    assert "<td>saas/service.php</td>" in output

def test_action_table_data_risk_attrs():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert 'data-risk="low"' in output
    assert 'data-risk="high"' in output

def test_complexity_heatmap_present():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert "<h2>Complexity Hotspots</h2>" in output
    assert "saas/service.php" in output
    assert "rgba(220, 38, 38," in output

def test_filter_js_present():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert "function filterRisk(risk)" in output

def test_no_external_urls():
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    assert "http:" not in output
    assert "https:" not in output

def test_write_creates_file(tmp_path):
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output_file = tmp_path / "report.html"
    reporter.write(output_file)
    assert output_file.exists()
    assert output_file.stat().st_size > 0

def test_write_file_readable(tmp_path):
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    rendered_content = reporter.render()
    output_file = tmp_path / "report.html"
    reporter.write(output_file)
    read_content = output_file.read_text(encoding='utf-8')
    assert read_content == rendered_content

def test_xss_source_escaped():
    xss_action = Action(ActionType.DELETE, "<script>alert(1)</script>.php", None, RiskLevel.LOW, "xss")
    plan = ActionPlan(actions=[xss_action], project_dir="/project", created_at="2023-10-27")
    reporter = HTMLReporter(plan, [], plan.project_dir)
    output = reporter.render()
    assert "<td>&lt;script&gt;alert(1)&lt;/script&gt;.php</td>" in output
    assert "<script>alert(1)</script>" not in output

def test_xss_reason_escaped():
    xss_action = Action(ActionType.DELETE, "file.php", None, RiskLevel.LOW, reason='<img src=x onerror=alert(1)>')
    plan = ActionPlan(actions=[xss_action], project_dir="/project", created_at="2023-10-27")
    reporter = HTMLReporter(plan, [], plan.project_dir)
    output = reporter.render()
    assert "<td>&lt;img src=x onerror=alert(1)&gt;</td>" in output
    assert "<img src=x onerror=alert(1)>" not in output

def test_xss_heatmap_file_escaped():
    action = Action(ActionType.REPORT_ONLY, "saas/<script>.php", None, RiskLevel.HIGH, "complex")
    plan = ActionPlan(actions=[action], project_dir="/project", created_at="2023-10-27")
    results = [
        AnalysisResult("complexity_analyzer", [action], {
            "top10": [{"file": "saas/<script>.php", "score": 100, "max_depth": 5, "total_branches": 10}]
        })
    ]
    reporter = HTMLReporter(plan, results, plan.project_dir)
    output = reporter.render()
    escaped_file = html.escape("saas/<script>.php")
    assert f">{escaped_file}</td>" in output
    assert "saas/<script>.php" not in output
