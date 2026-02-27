from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.models import Action, ActionPlan, ActionType, AnalysisResult, RiskLevel
from reporters.html_reporter import HTMLReporter


def make_plan_and_results() -> tuple[ActionPlan, list[AnalysisResult]]:
    actions = [
        Action(ActionType.DELETE, "old.php", None, RiskLevel.LOW, "backup"),
        Action(ActionType.ADD_GITIGNORE, "vendor", None, RiskLevel.LOW, "vendor"),
        Action(ActionType.REPORT_ONLY, "saas/service.php", None, RiskLevel.HIGH, "complex"),
    ]
    plan = ActionPlan(actions=actions, project_dir="/project/my-php-project")
    results = [
        AnalysisResult(
            "complexity_analyzer",
            [actions[2]],
            {"top10": [{"file": "saas/service.php", "score": 115, "max_depth": 5, "total_branches": 100}]},
        )
    ]
    return plan, results


def test_render_returns_string() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert isinstance(html, str)
    assert html.strip()


def test_render_is_valid_html_start() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert html.startswith("<!DOCTYPE html>")


def test_render_contains_project_dir() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert plan.project_dir in html


def test_render_contains_generated_date() -> None:
    plan, results = make_plan_and_results()
    today = datetime.now(timezone.utc).date().isoformat()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert today in html


def test_summary_cards_counts() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert "Total Actions" in html
    assert ">3<" in html


def test_action_table_sources() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert "old.php" in html
    assert "vendor" in html


def test_action_table_data_risk_attrs() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert 'data-risk="low"' in html
    assert 'data-risk="high"' in html


def test_complexity_heatmap_present() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert 'id="complexity"' in html
    assert "saas/service.php" in html


def test_filter_js_present() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert "function filterRisk" in html
    assert "<script>" in html


def test_no_external_urls() -> None:
    plan, results = make_plan_and_results()
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert "http" not in html.lower()


def test_write_creates_file(tmp_path: Path) -> None:
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    out = tmp_path / "report.html"
    reporter.write(out)
    assert out.exists()


def test_write_file_readable(tmp_path: Path) -> None:
    plan, results = make_plan_and_results()
    reporter = HTMLReporter(plan, results, plan.project_dir)
    out = tmp_path / "report.html"
    expected = reporter.render()
    reporter.write(out)
    assert out.read_text(encoding="utf-8") == expected


def test_xss_source_escaped() -> None:
    actions = [
        Action(ActionType.DELETE, "<script>alert(1)</script>.php", None, RiskLevel.LOW, "backup"),
    ]
    plan = ActionPlan(actions=actions, project_dir="/project/xss")
    html = HTMLReporter(plan, [], plan.project_dir).render()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;.php" in html
    assert "<script>alert(1)</script>.php" not in html


def test_xss_reason_escaped() -> None:
    actions = [
        Action(ActionType.DELETE, "ok.php", None, RiskLevel.LOW, '<img src=x onerror=alert(1)>'),
    ]
    plan = ActionPlan(actions=actions, project_dir="/project/xss")
    html = HTMLReporter(plan, [], plan.project_dir).render()
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert '<img src=x onerror=alert(1)>' not in html


def test_xss_heatmap_file_escaped() -> None:
    actions = [Action(ActionType.REPORT_ONLY, "safe.php", None, RiskLevel.LOW, "ok")]
    plan = ActionPlan(actions=actions, project_dir="/project/xss")
    results = [
        AnalysisResult(
            "complexity_analyzer",
            actions,
            {
                "top10": [
                    {
                        "file": "bad<>.php",
                        "score": 50,
                        "max_depth": 5,
                        "total_branches": 10,
                    }
                ]
            },
        )
    ]
    html = HTMLReporter(plan, results, plan.project_dir).render()
    assert "bad&lt;&gt;.php" in html
    assert "bad<>.php" not in html

