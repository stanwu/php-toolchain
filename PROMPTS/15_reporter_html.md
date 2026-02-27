# Prompt 15 — reporters/html_reporter.py
> Paste `00_MASTER_CONTEXT.md` first, then this prompt.
> **Requires:** core/ (01–03)

---

## Task

Implement `reporters/html_reporter.py` — generates a **self-contained static HTML report**
(no external CDN dependencies, all CSS/JS inlined) with:
- Summary cards
- Complexity heatmap table
- Interactive directory tree
- Full action plan table with filtering

---

## Implementation Requirements

```python
from pathlib import Path
from core.models import ActionPlan, AnalysisResult, RiskLevel, ActionType
from datetime import datetime, timezone
import html as html_lib   # for html_lib.escape() — used on ALL user-derived strings

class HTMLReporter:
    def __init__(
        self,
        plan: ActionPlan,
        results: list[AnalysisResult],
        project_dir: str
    ) -> None: ...

    def render(self) -> str:
        """
        Render the complete HTML as a string.
        Structure:
          <head> with inlined CSS
          <body>
            _render_header()
            _render_summary_cards()
            _render_action_table()
            _render_complexity_heatmap()
            _render_directory_tree()
          <script> with inlined JS
        """

    def write(self, output_path: Path) -> None:
        """Write render() output to output_path."""

    def _render_header(self) -> str:
        """<h1> with project dir, report date."""

    def _render_summary_cards(self) -> str:
        """
        4 cards: Total Actions | LOW | MEDIUM | HIGH
        Each card has a count and a label.
        """

    def _render_action_table(self) -> str:
        """
        HTML <table> with all actions.
        Each row has data-risk attribute (low/medium/high) for JS filtering.
        Columns: # | Type | Source | Risk | Reason
        SECURITY: apply html_lib.escape() to action.source and action.reason
        before embedding in HTML to prevent XSS.
        """

    def _render_complexity_heatmap(self) -> str:
        """
        Table of top-20 most complex files from complexity_analyzer results.
        Columns: File | Max Depth | Total Branches | Score
        Background colour intensity proportional to score.
        (Use inline style with rgba for colour.)
        SECURITY: apply html_lib.escape() to the file path before embedding.
        """

    def _render_directory_tree(self) -> str:
        """
        Collapsible <details>/<summary> tree built from action sources.
        Group by top-level directory.
        SECURITY: apply html_lib.escape() to all path segments before embedding.
        """

    def _inline_css(self) -> str:
        """Return CSS string (minimal, no external dependencies)."""

    def _inline_js(self) -> str:
        """
        Return JS string with:
        - Filter buttons by risk level (show/hide rows by data-risk attribute)
        - Collapsible directory tree toggle
        """
```

### HTML structure overview

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PHP Cleanup Report — {project_dir}</title>
  <style>/* inlined CSS */</style>
</head>
<body>
  <h1>PHP Cleanup Report</h1>
  <p>Project: {project_dir} | Generated: {timestamp}</p>

  <section id="summary"><!-- 4 cards --></section>
  <section id="actions">
    <h2>Action Plan</h2>
    <div id="filter-buttons">
      <button onclick="filterRisk('all')">All</button>
      <button onclick="filterRisk('low')">LOW</button>
      <button onclick="filterRisk('medium')">MEDIUM</button>
      <button onclick="filterRisk('high')">HIGH</button>
    </div>
    <table><!-- actions --></table>
  </section>
  <section id="complexity"><!-- heatmap --></section>
  <section id="tree"><!-- directory tree --></section>

  <script>/* inlined JS */</script>
</body>
</html>
```

---

## Tests — tests/test_html_reporter.py

No browser needed — just parse the rendered string.

```python
from core.models import ActionPlan, Action, ActionType, RiskLevel, AnalysisResult

def make_plan_and_results():
    actions = [
        Action(ActionType.DELETE, "old.php", None, RiskLevel.LOW, "backup"),
        Action(ActionType.ADD_GITIGNORE, "vendor", None, RiskLevel.LOW, "vendor"),
        Action(ActionType.REPORT_ONLY, "saas/service.php", None, RiskLevel.HIGH, "complex"),
    ]
    plan = ActionPlan(actions=actions, project_dir="/project/my-php-project")
    results = [
        AnalysisResult("complexity_analyzer", [actions[2]], {
            "top10": [{"file": "saas/service.php", "score": 115, "max_depth": 5, "total_branches": 100}]
        })
    ]
    return plan, results
```

| Test name | What it checks |
|-----------|----------------|
| `test_render_returns_string` | `render()` returns a non-empty `str` |
| `test_render_is_valid_html_start` | Starts with `<!DOCTYPE html>` |
| `test_render_contains_project_dir` | Project dir string in output |
| `test_render_contains_generated_date` | Today's date in output |
| `test_summary_cards_counts` | Total action count (3) appears |
| `test_action_table_sources` | `old.php`, `vendor` in table |
| `test_action_table_data_risk_attrs` | `data-risk="low"` in output |
| `test_complexity_heatmap_present` | `saas/service.php` in heatmap section |
| `test_filter_js_present` | `filterRisk` function in `<script>` |
| `test_no_external_urls` | `http` not in output (fully self-contained) |
| `test_write_creates_file` | `write(tmp_path/"report.html")` creates the file |
| `test_write_file_readable` | Written file matches `render()` output |
| `test_xss_source_escaped` | Action with `source="<script>alert(1)</script>.php"` → `&lt;script&gt;` in output, no raw `<script>` tag |
| `test_xss_reason_escaped` | Action with `reason='<img src=x onerror=alert(1)>'` → HTML-escaped in output |
| `test_xss_heatmap_file_escaped` | Heatmap file path with `<>` characters → HTML-escaped |

---

## Deliverables

1. `reporters/html_reporter.py`
2. `tests/test_html_reporter.py`

**Verify:** `pytest tests/test_html_reporter.py -v` must pass with 0 failures.
