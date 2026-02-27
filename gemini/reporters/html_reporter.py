from pathlib import Path
from core.models import ActionPlan, AnalysisResult, RiskLevel, ActionType
from datetime import datetime, timezone
import html as html_lib
from collections import defaultdict

class HTMLReporter:
    def __init__(
        self,
        plan: ActionPlan,
        results: list[AnalysisResult],
        project_dir: str
    ) -> None:
        self.plan = plan
        self.results = results
        self.project_dir = project_dir
        self.timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')

    def render(self) -> str:
        """
        Render the complete HTML as a string.
        """
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>PHP Cleanup Report — {html_lib.escape(self.project_dir)}</title>
  <style>{self._inline_css()}</style>
</head>
<body>
  {self._render_header()}
  <main>
    <section id="summary">{self._render_summary_cards()}</section>
    <section id="actions">
      <h2>Action Plan</h2>
      <div id="filter-buttons">
        <button onclick="filterRisk('all')" class="active">All</button>
        <button onclick="filterRisk('low')">LOW</button>
        <button onclick="filterRisk('medium')">MEDIUM</button>
        <button onclick="filterRisk('high')">HIGH</button>
      </div>
      {self._render_action_table()}
    </section>
    {self._render_complexity_heatmap()}
    {self._render_directory_tree()}
  </main>
  <script>{self._inline_js()}</script>
</body>
</html>
"""

    def write(self, output_path: Path) -> None:
        """Write render() output to output_path."""
        output_path.write_text(self.render(), encoding='utf-8')

    def _render_header(self) -> str:
        """<h1> with project dir, report date."""
        return f"""
<header>
  <h1>PHP Cleanup Report</h1>
  <p><strong>Project:</strong> {html_lib.escape(self.project_dir)} | <strong>Generated:</strong> {self.timestamp}</p>
</header>
"""

    def _render_summary_cards(self) -> str:
        """
        4 cards: Total Actions | LOW | MEDIUM | HIGH
        Each card has a count and a label.
        """
        total_actions = len(self.plan.actions)
        low_count = sum(1 for a in self.plan.actions if a.risk_level == RiskLevel.LOW)
        medium_count = sum(1 for a in self.plan.actions if a.risk_level == RiskLevel.MEDIUM)
        high_count = sum(1 for a in self.plan.actions if a.risk_level == RiskLevel.HIGH)

        return f"""
<div class="summary-cards">
  <div class="card">
    <span class="count">{total_actions}</span>
    <span class="label">Total Actions</span>
  </div>
  <div class="card risk-low">
    <span class="count">{low_count}</span>
    <span class="label">Low Risk</span>
  </div>
  <div class="card risk-medium">
    <span class="count">{medium_count}</span>
    <span class="label">Medium Risk</span>
  </div>
  <div class="card risk-high">
    <span class="count">{high_count}</span>
    <span class="label">High Risk</span>
  </div>
</div>
"""

    def _render_action_table(self) -> str:
        """
        HTML <table> with all actions.
        """
        rows = []
        for i, action in enumerate(self.plan.actions):
            risk_class = action.risk_level.name.lower()
            rows.append(f"""
<tr data-risk="{risk_class}">
  <td>{i + 1}</td>
  <td><span class="badge type-{action.action_type.value.lower()}">{action.action_type.value}</span></td>
  <td>{html_lib.escape(action.source)}</td>
  <td><span class="badge risk-{risk_class}">{action.risk_level.name}</span></td>
  <td>{html_lib.escape(action.reason)}</td>
</tr>
""")
        if not rows:
            rows.append('<tr><td colspan="5">No actions planned.</td></tr>')

        return f"""
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Type</th>
      <th>Source</th>
      <th>Risk</th>
      <th>Reason</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
"""

    def _render_complexity_heatmap(self) -> str:
        """
        Table of top-20 most complex files from complexity_analyzer results.
        """
        complexity_result = next((r for r in self.results if r.analyzer_name == "complexity_analyzer"), None)
        if not complexity_result or "top10" not in complexity_result.metadata:
            return ""

        top_files = complexity_result.metadata.get("top10", [])
        if not top_files:
            return ""
            
        max_score = max(f.get('score', 0) for f in top_files) if top_files else 1

        rows = []
        for f in top_files:
            score = f.get('score', 0)
            # Normalize score for color intensity (0 to 1)
            intensity = score / max_score if max_score > 0 else 0
            # Red color, varying alpha
            color = f"rgba(220, 38, 38, {intensity * 0.7 + 0.1})"
            rows.append(f"""
<tr>
  <td style="background-color: {color};">{html_lib.escape(f.get('file', ''))}</td>
  <td>{f.get('max_depth', 0)}</td>
  <td>{f.get('total_branches', 0)}</td>
  <td>{score}</td>
</tr>
""")

        return f"""
<section id="complexity">
  <h2>Complexity Hotspots</h2>
  <table>
    <thead>
      <tr>
        <th>File</th>
        <th>Max Depth</th>
        <th>Total Branches</th>
        <th>Score</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</section>
"""

    def _render_directory_tree(self) -> str:
        """
        Collapsible <details>/<summary> tree built from action sources.
        """
        tree = defaultdict(list)
        all_paths = sorted(list(set(a.source for a in self.plan.actions)))

        for path_str in all_paths:
            p = Path(path_str)
            if len(p.parts) > 1:
                tree[p.parts[0]].append(str(p.relative_to(p.parts[0])))
            else:
                tree['.'].append(path_str)

        if not tree:
            return ""

        items = []
        for root, children in sorted(tree.items()):
            child_items = "".join(f"<li>{html_lib.escape(child)}</li>" for child in sorted(children))
            items.append(f"""
<details>
  <summary>{html_lib.escape(root)}</summary>
  <ul>{child_items}</ul>
</details>
""")
        return f"""
<section id="tree">
  <h2>Affected Directory Tree</h2>
  <div class="directory-tree">{''.join(items)}</div>
</section>
"""

    def _inline_css(self) -> str:
        """Return CSS string."""
        return """
:root {
    --bg-color: #f8f9fa; --text-color: #212529; --border-color: #dee2e6;
    --header-bg: #fff; --card-bg: #fff; --table-header-bg: #f1f3f5;
    --link-color: #007bff; --shadow: 0 2px 4px rgba(0,0,0,0.05);
    --risk-low: #28a745; --risk-medium: #ffc107; --risk-high: #dc3545;
    --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
body {
    font-family: var(--font-family); background-color: var(--bg-color);
    color: var(--text-color); margin: 0; padding: 2rem; line-height: 1.6;
}
header, section {
    background-color: var(--header-bg); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: var(--shadow);
}
h1, h2 { margin-top: 0; color: #343a40; }
h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem; }
.summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; }
.card {
    background-color: var(--card-bg); padding: 1.5rem; border-radius: 8px;
    text-align: center; border: 1px solid var(--border-color);
}
.card .count { font-size: 2.5rem; font-weight: bold; display: block; }
.card .label { color: #6c757d; }
.card.risk-low { border-left: 5px solid var(--risk-low); }
.card.risk-medium { border-left: 5px solid var(--risk-medium); }
.card.risk-high { border-left: 5px solid var(--risk-high); }
#filter-buttons { margin-bottom: 1rem; }
#filter-buttons button {
    background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 20px;
    padding: 0.5rem 1rem; cursor: pointer; margin-right: 0.5rem; font-weight: 500;
}
#filter-buttons button.active { background-color: #007bff; color: #fff; border-color: #007bff; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border-color); }
thead th { background-color: var(--table-header-bg); font-weight: 600; }
tbody tr:hover { background-color: #f1f3f5; }
.badge {
    display: inline-block; padding: 0.25em 0.6em; font-size: 75%; font-weight: 700;
    line-height: 1; text-align: center; white-space: nowrap; vertical-align: baseline;
    border-radius: 0.375rem; color: #fff;
}
.risk-low { background-color: var(--risk-low); }
.risk-medium { background-color: var(--risk-medium); color: #212529; }
.risk-high { background-color: var(--risk-high); }
.type-delete { background-color: #6c757d; }
.type-add_gitignore { background-color: #17a2b8; }
.type-report_only { background-color: #fd7e14; }
.directory-tree details { margin-bottom: 0.5rem; }
.directory-tree summary { cursor: pointer; font-weight: bold; }
.directory-tree ul { padding-left: 2rem; list-style-type: none; }
.directory-tree li { padding: 0.2rem 0; }
"""

    def _inline_js(self) -> str:
        """Return JS string."""
        return """
function filterRisk(risk) {
    const rows = document.querySelectorAll('#actions tbody tr');
    const buttons = document.querySelectorAll('#filter-buttons button');
    
    rows.forEach(row => {
        if (risk === 'all' || row.dataset.risk === risk) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });

    buttons.forEach(button => {
        button.classList.remove('active');
        if (button.textContent.toLowerCase() === risk || (risk === 'all' && button.textContent === 'All')) {
            button.classList.add('active');
        }
    });
}
document.addEventListener('DOMContentLoaded', () => {
    // Set initial active button
    const initialButton = document.querySelector('#filter-buttons button');
    if(initialButton) initialButton.classList.add('active');
});
"""
