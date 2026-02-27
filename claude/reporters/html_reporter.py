import html as html_lib
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from core.models import ActionPlan, ActionType, AnalysisResult, RiskLevel

logger = logging.getLogger(__name__)


class HTMLReporter:
    def __init__(
        self,
        plan: ActionPlan,
        results: list[AnalysisResult],
        project_dir: str,
    ) -> None:
        self._plan = plan
        self._results = results
        self._project_dir = project_dir

    def render(self) -> str:
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        parts = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="UTF-8">',
            f"<title>PHP Cleanup Report — {html_lib.escape(self._project_dir)}</title>",
            f"<style>{self._inline_css()}</style>",
            "</head>",
            "<body>",
            self._render_header(timestamp),
            self._render_summary_cards(),
            self._render_action_table(),
            self._render_complexity_heatmap(),
            self._render_directory_tree(),
            f"<script>{self._inline_js()}</script>",
            "</body>",
            "</html>",
        ]
        return "\n".join(parts)

    def write(self, output_path: Path) -> None:
        output_path.write_text(self.render(), encoding="utf-8")
        logger.info("HTML report written to %s", output_path)

    def _render_header(self, timestamp: str) -> str:
        escaped_dir = html_lib.escape(self._project_dir)
        return (
            "<h1>PHP Cleanup Report</h1>\n"
            f"<p>Project: {escaped_dir} | Generated: {html_lib.escape(timestamp)}</p>"
        )

    def _render_summary_cards(self) -> str:
        actions = self._plan.actions
        total = len(actions)
        low = sum(1 for a in actions if a.risk_level == RiskLevel.LOW)
        medium = sum(1 for a in actions if a.risk_level == RiskLevel.MEDIUM)
        high = sum(1 for a in actions if a.risk_level == RiskLevel.HIGH)

        def card(label: str, count: int, css_class: str) -> str:
            return (
                f'<div class="card {css_class}">'
                f'<div class="card-count">{count}</div>'
                f'<div class="card-label">{label}</div>'
                f"</div>"
            )

        cards = (
            card("Total Actions", total, "card-total")
            + card("LOW", low, "card-low")
            + card("MEDIUM", medium, "card-medium")
            + card("HIGH", high, "card-high")
        )
        return f'<section id="summary">\n<div class="cards">{cards}</div>\n</section>'

    def _render_action_table(self) -> str:
        rows = []
        for i, action in enumerate(self._plan.actions, start=1):
            risk_str = action.risk_level.value.lower()
            escaped_source = html_lib.escape(action.source)
            escaped_reason = html_lib.escape(action.reason)
            conflict_marker = " ⚠" if action.conflict else ""
            rows.append(
                f'<tr data-risk="{risk_str}">'
                f"<td>{i}</td>"
                f"<td>{html_lib.escape(action.action_type.value)}</td>"
                f"<td>{escaped_source}</td>"
                f'<td class="risk-{risk_str}">{action.risk_level.value}{conflict_marker}</td>'
                f"<td>{escaped_reason}</td>"
                "</tr>"
            )

        header = (
            "<thead><tr>"
            "<th>#</th><th>Type</th><th>Source</th><th>Risk</th><th>Reason</th>"
            "</tr></thead>"
        )
        body = "<tbody>" + "".join(rows) + "</tbody>"
        filter_buttons = (
            '<div id="filter-buttons">'
            '<button onclick="filterRisk(\'all\')">All</button>'
            '<button onclick="filterRisk(\'low\')">LOW</button>'
            '<button onclick="filterRisk(\'medium\')">MEDIUM</button>'
            '<button onclick="filterRisk(\'high\')">HIGH</button>'
            "</div>"
        )
        return (
            '<section id="actions">\n'
            "<h2>Action Plan</h2>\n"
            f"{filter_buttons}\n"
            f"<table>{header}{body}</table>\n"
            "</section>"
        )

    def _render_complexity_heatmap(self) -> str:
        # Collect top files from complexity_analyzer metadata
        top_files: list[dict] = []
        for result in self._results:
            if result.analyzer_name == "complexity_analyzer":
                top_files = result.metadata.get("top10", [])
                break

        if not top_files:
            return '<section id="complexity"><h2>Complexity Heatmap</h2><p>No data.</p></section>'

        # Cap at top 20
        top_files = top_files[:20]
        max_score = max((f.get("score", 0) for f in top_files), default=1) or 1

        rows = []
        for entry in top_files:
            file_path = html_lib.escape(str(entry.get("file", "")))
            score = entry.get("score", 0)
            max_depth = entry.get("max_depth", 0)
            total_branches = entry.get("total_branches", 0)
            intensity = min(score / max_score, 1.0)
            bg_color = f"rgba(220, 53, 69, {intensity:.2f})"
            rows.append(
                f'<tr style="background-color:{bg_color}">'
                f"<td>{file_path}</td>"
                f"<td>{max_depth}</td>"
                f"<td>{total_branches}</td>"
                f"<td>{score}</td>"
                "</tr>"
            )

        header = (
            "<thead><tr>"
            "<th>File</th><th>Max Depth</th><th>Total Branches</th><th>Score</th>"
            "</tr></thead>"
        )
        body = "<tbody>" + "".join(rows) + "</tbody>"
        return (
            '<section id="complexity">\n'
            "<h2>Complexity Heatmap</h2>\n"
            f"<table>{header}{body}</table>\n"
            "</section>"
        )

    def _render_directory_tree(self) -> str:
        # Group sources by top-level directory
        by_dir: dict[str, list[str]] = defaultdict(list)
        for action in self._plan.actions:
            parts = Path(action.source).parts
            if len(parts) > 1:
                top_dir = parts[0]
                rest = "/".join(parts[1:])
            else:
                top_dir = "(root)"
                rest = parts[0] if parts else action.source
            by_dir[top_dir].append(rest)

        sections = []
        for top_dir in sorted(by_dir.keys()):
            escaped_dir = html_lib.escape(top_dir)
            items = "".join(
                f"<li>{html_lib.escape(f)}</li>" for f in sorted(by_dir[top_dir])
            )
            sections.append(
                f"<details><summary>{escaped_dir}/</summary><ul>{items}</ul></details>"
            )

        tree_html = "\n".join(sections)
        return (
            '<section id="tree">\n'
            "<h2>Directory Tree</h2>\n"
            f"{tree_html}\n"
            "</section>"
        )

    def _inline_css(self) -> str:
        return """
body { font-family: sans-serif; margin: 2rem; color: #212529; background: #f8f9fa; }
h1 { color: #343a40; }
h2 { color: #495057; border-bottom: 2px solid #dee2e6; padding-bottom: .3rem; }
.cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.card { border-radius: 8px; padding: 1rem 1.5rem; min-width: 120px; text-align: center; color: #fff; }
.card-count { font-size: 2rem; font-weight: bold; }
.card-label { font-size: .85rem; text-transform: uppercase; letter-spacing: .05em; }
.card-total { background: #6c757d; }
.card-low { background: #28a745; }
.card-medium { background: #fd7e14; }
.card-high { background: #dc3545; }
table { border-collapse: collapse; width: 100%; margin-top: 1rem; background: #fff; }
th, td { border: 1px solid #dee2e6; padding: .5rem .75rem; text-align: left; }
th { background: #e9ecef; font-weight: 600; }
tr:hover { background: #f1f3f5; }
.risk-low { color: #155724; font-weight: 600; }
.risk-medium { color: #7d4e00; font-weight: 600; }
.risk-high { color: #721c24; font-weight: 600; }
#filter-buttons { margin: .75rem 0; }
#filter-buttons button {
  margin-right: .4rem; padding: .35rem .75rem; border: none;
  border-radius: 4px; cursor: pointer; background: #6c757d; color: #fff;
}
#filter-buttons button:hover { opacity: .85; }
details { margin: .5rem 0; }
summary { cursor: pointer; font-weight: 600; padding: .3rem; }
ul { margin: .25rem 0 .25rem 1.5rem; }
section { margin-bottom: 2.5rem; }
"""

    def _inline_js(self) -> str:
        return """
function filterRisk(level) {
  var rows = document.querySelectorAll('#actions table tbody tr');
  rows.forEach(function(row) {
    if (level === 'all' || row.getAttribute('data-risk') === level) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}
"""
