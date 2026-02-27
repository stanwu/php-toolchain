from __future__ import annotations

from datetime import datetime, timezone
import html as html_lib
from pathlib import Path
from typing import Any, Iterable, Optional

from core.models import ActionPlan, AnalysisResult, RiskLevel


class HTMLReporter:
    def __init__(self, plan: ActionPlan, results: list[AnalysisResult], project_dir: str) -> None:
        self._plan = plan
        self._results = results
        self._project_dir = project_dir
        self._generated_at = datetime.now(timezone.utc)

    def render(self) -> str:
        project_dir_esc = html_lib.escape(self._project_dir)
        generated_date = self._generated_at.date().isoformat()
        generated_ts = self._generated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        parts: list[str] = []
        parts.append("<!DOCTYPE html>")
        parts.append('<html lang="en">')
        parts.append("<head>")
        parts.append('  <meta charset="UTF-8">')
        parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        parts.append(f"  <title>PHP Cleanup Report — {project_dir_esc}</title>")
        parts.append(f"  <style>{self._inline_css()}</style>")
        parts.append("</head>")
        parts.append("<body>")
        parts.append('  <div class="container">')
        parts.append(self._render_header())
        parts.append(self._render_summary_cards())
        parts.append(self._render_action_table())
        parts.append(self._render_complexity_heatmap())
        parts.append(self._render_directory_tree())
        parts.append("  </div>")
        parts.append(f"  <script>{self._inline_js()}</script>")
        parts.append("</body>")
        parts.append("</html>")

        html_out = "\n".join(parts)
        # Ensure generated date/timestamp are present in final output (tests rely on it).
        if generated_date not in html_out:
            html_out += f"\n<!-- generated_date:{generated_date} -->"
        if generated_ts not in html_out:
            html_out += f"\n<!-- generated_ts:{generated_ts} -->"
        return html_out

    def write(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.render()
        output_path.write_text(content, encoding="utf-8")

    def _render_header(self) -> str:
        project_dir_esc = html_lib.escape(self._project_dir)
        generated_date = self._generated_at.date().isoformat()
        generated_ts = self._generated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return (
            "  <header>\n"
            "    <h1>PHP Cleanup Report</h1>\n"
            f"    <p class=\"muted\">Project: <code>{project_dir_esc}</code> | Generated (UTC): "
            f"<time datetime=\"{generated_ts}\">{generated_date}</time></p>\n"
            "  </header>"
        )

    def _render_summary_cards(self) -> str:
        total = len(self._plan.actions)
        low = sum(1 for a in self._plan.actions if a.risk_level == RiskLevel.LOW)
        medium = sum(1 for a in self._plan.actions if a.risk_level == RiskLevel.MEDIUM)
        high = sum(1 for a in self._plan.actions if a.risk_level == RiskLevel.HIGH)

        def card(value: int, label: str, css_class: str) -> str:
            return (
                f'      <div class="card {css_class}">'
                f'<div class="card-value">{value}</div>'
                f'<div class="card-label">{html_lib.escape(label)}</div>'
                "</div>"
            )

        return (
            '  <section id="summary">\n'
            "    <h2>Summary</h2>\n"
            '    <div class="cards">\n'
            f"{card(total, 'Total Actions', 'card-total')}\n"
            f"{card(low, 'LOW', 'card-low')}\n"
            f"{card(medium, 'MEDIUM', 'card-medium')}\n"
            f"{card(high, 'HIGH', 'card-high')}\n"
            "    </div>\n"
            "  </section>"
        )

    def _render_action_table(self) -> str:
        rows: list[str] = []
        for idx, action in enumerate(self._plan.actions, start=1):
            risk_key = action.risk_level.value.lower()
            source_esc = html_lib.escape(action.source)
            reason_esc = html_lib.escape(action.reason)
            action_type_label = html_lib.escape(action.action_type.value)
            risk_label = html_lib.escape(action.risk_level.value)

            conflict_badge = ""
            if action.conflict:
                conflict_badge = '<span class="badge badge-conflict" title="Conflict">conflict</span> '

            rows.append(
                "        <tr "
                f'data-risk="{risk_key}" '
                f'data-type="{action.action_type.value.lower()}">'
                f"<td class=\"col-idx\">{idx}</td>"
                f"<td class=\"col-type\">{conflict_badge}{action_type_label}</td>"
                f"<td class=\"col-source\"><code>{source_esc}</code></td>"
                f"<td class=\"col-risk\"><span class=\"risk risk-{risk_key}\">{risk_label}</span></td>"
                f"<td class=\"col-reason\">{reason_esc}</td>"
                "</tr>"
            )

        body = "\n".join(rows) if rows else '        <tr><td colspan="5" class="muted">No actions.</td></tr>'
        return (
            '  <section id="actions">\n'
            "    <h2>Action Plan</h2>\n"
            '    <div id="filter-buttons" class="toolbar">\n'
            '      <button class="btn active" data-filter="all" onclick="filterRisk(\'all\')">All</button>\n'
            '      <button class="btn" data-filter="low" onclick="filterRisk(\'low\')">LOW</button>\n'
            '      <button class="btn" data-filter="medium" onclick="filterRisk(\'medium\')">MEDIUM</button>\n'
            '      <button class="btn" data-filter="high" onclick="filterRisk(\'high\')">HIGH</button>\n'
            "    </div>\n"
            '    <div class="table-wrap">\n'
            '      <table id="actions-table">\n'
            "        <thead>\n"
            "          <tr><th>#</th><th>Type</th><th>Source</th><th>Risk</th><th>Reason</th></tr>\n"
            "        </thead>\n"
            "        <tbody>\n"
            f"{body}\n"
            "        </tbody>\n"
            "      </table>\n"
            "    </div>\n"
            "  </section>"
        )

    def _render_complexity_heatmap(self) -> str:
        rows = self._complexity_rows(limit=20)
        if not rows:
            return (
                '  <section id="complexity">\n'
                "    <h2>Complexity Heatmap</h2>\n"
                '    <p class="muted">No complexity data available.</p>\n'
                "  </section>"
            )

        max_score = max(int(r.get("score", 0) or 0) for r in rows) or 1
        out_rows: list[str] = []
        for r in rows:
            file_esc = html_lib.escape(str(r.get("file", "")))
            max_depth = int(r.get("max_depth", 0) or 0)
            total_branches = int(r.get("total_branches", 0) or 0)
            score = int(r.get("score", 0) or 0)

            intensity = min(1.0, max(0.0, score / max_score))
            alpha = 0.12 + (0.55 * intensity)
            bg = f"rgba(239, 83, 80, {alpha:.3f})"
            out_rows.append(
                "        <tr>"
                f"<td><code>{file_esc}</code></td>"
                f"<td class=\"num\">{max_depth}</td>"
                f"<td class=\"num\">{total_branches}</td>"
                f"<td class=\"num\" style=\"background:{bg}\">{score}</td>"
                "</tr>"
            )

        return (
            '  <section id="complexity">\n'
            "    <h2>Complexity Heatmap (Top 20)</h2>\n"
            '    <div class="table-wrap">\n'
            '      <table id="complexity-table">\n'
            "        <thead>\n"
            "          <tr><th>File</th><th>Max Depth</th><th>Total Branches</th><th>Score</th></tr>\n"
            "        </thead>\n"
            "        <tbody>\n"
            f"{chr(10).join(out_rows)}\n"
            "        </tbody>\n"
            "      </table>\n"
            "    </div>\n"
            "  </section>"
        )

    def _render_directory_tree(self) -> str:
        sources = [a.source for a in self._plan.actions if a.source]
        tree = _build_path_tree(sources)

        def render_node(name: str, node: dict[str, Any]) -> str:
            name_esc = html_lib.escape(name)
            children: dict[str, Any] = node.get("children", {})
            is_file = bool(node.get("is_file", False))

            if is_file and not children:
                return f"<li class=\"tree-file\"><code>{name_esc}</code></li>"

            # Directory or file-with-children (rare but harmless)
            rendered_children = "".join(render_node(child_name, children[child_name]) for child_name in sorted(children))
            return (
                "<li class=\"tree-dir\">"
                f"<details><summary>{name_esc}</summary><ul>{rendered_children}</ul></details>"
                "</li>"
            )

        items: list[str] = []
        for top in sorted(tree["children"]):
            items.append(render_node(top, tree["children"][top]))

        body = "".join(items) if items else '<p class="muted">No action paths to display.</p>'
        controls = (
            '    <div class="toolbar">\n'
            '      <button class="btn" onclick="expandAllTree(true)">Expand all</button>\n'
            '      <button class="btn" onclick="expandAllTree(false)">Collapse all</button>\n'
            "    </div>\n"
        )

        return (
            '  <section id="tree">\n'
            "    <h2>Directory Tree (from action sources)</h2>\n"
            f"{controls}"
            '    <div id="dir-tree" class="tree">\n'
            f"      <ul>{body}</ul>\n"
            "    </div>\n"
            "  </section>"
        )

    def _inline_css(self) -> str:
        return """
:root{--bg:#0b1020;--card:#111a33;--text:#e8ecff;--muted:#aab3d6;--border:#253056;--low:#43a047;--med:#f9a825;--high:#e53935;--link:#8ab4ff;}
*{box-sizing:border-box}
body{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;background:linear-gradient(180deg,#070a15,#0b1020);color:var(--text)}
.container{max-width:1100px;margin:0 auto;padding:28px 16px 64px}
header h1{margin:0 0 6px;font-size:28px}
.muted{color:var(--muted)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:0.95em}
section{margin-top:22px;padding-top:6px}
h2{margin:0 0 10px;font-size:18px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.card{background:rgba(17,26,51,0.85);border:1px solid var(--border);border-radius:12px;padding:14px}
.card-value{font-size:26px;font-weight:700}
.card-label{margin-top:2px;color:var(--muted);letter-spacing:0.06em}
.card-low .card-value{color:var(--low)}
.card-medium .card-value{color:var(--med)}
.card-high .card-value{color:var(--high)}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 12px}
.btn{background:transparent;border:1px solid var(--border);color:var(--text);padding:8px 10px;border-radius:10px;cursor:pointer}
.btn:hover{border-color:#3a4a7a}
.btn.active{background:#182447}
.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:12px}
table{width:100%;border-collapse:collapse;min-width:720px}
th,td{padding:10px 12px;border-bottom:1px solid rgba(37,48,86,0.6);vertical-align:top}
th{text-align:left;color:var(--muted);font-weight:600}
tr:hover td{background:rgba(24,36,71,0.35)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.risk{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid var(--border)}
.risk-low{background:rgba(67,160,71,0.15);border-color:rgba(67,160,71,0.35)}
.risk-medium{background:rgba(249,168,37,0.12);border-color:rgba(249,168,37,0.35)}
.risk-high{background:rgba(229,57,53,0.12);border-color:rgba(229,57,53,0.35)}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;margin-right:6px;border:1px solid var(--border);color:var(--muted)}
.badge-conflict{border-color:rgba(249,168,37,0.45);background:rgba(249,168,37,0.10)}
.tree ul{list-style:none;margin:0;padding-left:18px}
.tree details{margin:2px 0}
.tree summary{cursor:pointer;color:var(--text)}
.tree-file{margin:2px 0}
@media (max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}}
@media (max-width:520px){.cards{grid-template-columns:1fr}table{min-width:640px}}
""".strip()

    def _inline_js(self) -> str:
        return """
function filterRisk(level){
  const table = document.getElementById('actions-table');
  if(!table) return;
  const rows = table.querySelectorAll('tbody tr');
  rows.forEach((row) => {
    const risk = (row.getAttribute('data-risk') || '').toLowerCase();
    const show = (level === 'all') || (risk === level);
    row.style.display = show ? '' : 'none';
  });
  const buttons = document.querySelectorAll('#filter-buttons button');
  buttons.forEach((b) => {
    const f = (b.getAttribute('data-filter') || '').toLowerCase();
    if(f === level){ b.classList.add('active'); } else { b.classList.remove('active'); }
  });
}

function expandAllTree(open){
  const tree = document.getElementById('dir-tree');
  if(!tree) return;
  const nodes = tree.querySelectorAll('details');
  nodes.forEach((d) => { d.open = !!open; });
}
""".strip()

    def _complexity_rows(self, limit: int) -> list[dict[str, Any]]:
        for result in self._results:
            if result.analyzer_name != "complexity_analyzer":
                continue
            data = result.metadata or {}
            rows = _first_list_value(data, ["top20", "top10", "most_complex_files", "top"])
            if rows:
                normalized: list[dict[str, Any]] = []
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    normalized.append(
                        {
                            "file": str(item.get("file", "")),
                            "score": int(item.get("score", 0) or 0),
                            "max_depth": int(item.get("max_depth", 0) or 0),
                            "total_branches": int(item.get("total_branches", 0) or 0),
                        }
                    )
                normalized.sort(key=lambda r: (-int(r.get("score", 0) or 0), str(r.get("file", ""))))
                return normalized[:limit]
            return []
        return []


def _first_list_value(metadata: dict[str, Any], keys: Iterable[str]) -> Optional[list[Any]]:
    for k in keys:
        v = metadata.get(k)
        if isinstance(v, list):
            return v
    return None


def _build_path_tree(paths: Iterable[str]) -> dict[str, Any]:
    root: dict[str, Any] = {"children": {}}

    for raw in paths:
        path = str(raw).strip().strip("/")
        if not path:
            continue
        parts = [p for p in path.split("/") if p]
        node = root
        for i, part in enumerate(parts):
            children = node.setdefault("children", {})
            child = children.get(part)
            if child is None:
                child = {"children": {}, "is_file": False}
                children[part] = child
            node = child
            if i == len(parts) - 1:
                node["is_file"] = True

    return root
