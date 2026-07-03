#!/usr/bin/env python3
"""Sources page generator.

Reads config/sources.json and writes docs/sources/index.html — a grouped
reference page listing every intelligence source used by the pipeline.
"""
from __future__ import annotations

import html as html_module
import json
from datetime import date
from pathlib import Path

from webgen.shell import render_shell, render_template

ROOT     = Path(__file__).resolve().parent.parent
SOURCES  = ROOT / "config" / "sources.json"
OUT_DIR  = ROOT / "docs" / "sources"
OUT_FILE = OUT_DIR / "index.html"
TEMPLATE = ROOT / "pipeline" / "webgen" / "templates" / "sources.html"

TYPE_ORDER = ["news_site", "vc_newsrooms", "database", "search", "browser"]
TYPE_LABELS = {
    "news_site":    "News Sites",
    "vc_newsrooms": "VC Newsrooms",
    "database":     "Databases",
    "search":       "Search Engines",
    "browser":      "Browser (Authenticated)",
}
TYPE_DESCS = {
    "news_site":    "Scraped automatically each run via RSS feed or direct fetch.",
    "vc_newsrooms": "VC firm news pages scraped for deal announcements.",
    "database":     "Investment databases. Partially paywalled — free content extracted only.",
    "search":       "Web search queries run against public search engines.",
    "browser":      "Sources requiring an authenticated browser session (Stage 1c).",
}


def _esc(s: str) -> str:
    return html_module.escape(s or "")


def _build_group(group_type: str, sources: list[dict]) -> str:
    label = _esc(TYPE_LABELS.get(group_type, group_type))
    desc  = _esc(TYPE_DESCS.get(group_type, ""))
    rows  = []
    for s in sources:
        name     = _esc(s.get("name", ""))
        url      = _esc(s.get("url", ""))
        rss      = s.get("rss_url")
        notes    = _esc(s.get("notes", ""))
        best_eff = s.get("best_effort", False)

        badges = ""
        if rss:
            badges += '<span class="badge badge-rss">RSS</span>'
        if best_eff:
            badges += '<span class="badge badge-be">best‑effort</span>'

        rows.append(f"""      <tr>
        <td class="src-name"><a href="{url}" target="_blank" rel="noopener">{name}</a>{badges}</td>
        <td class="src-notes">{notes}</td>
      </tr>""")

    return f"""  <section class="src-group">
    <div class="group-header">
      <h2>{label}</h2><span class="group-count">{len(sources)}</span>
    </div>
    <p class="group-desc">{desc}</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Source</th><th>Description</th></tr></thead>
        <tbody>
{chr(10).join(rows)}
        </tbody>
      </table>
    </div>
  </section>"""


def build_page(sources: list[dict], today: str) -> str:
    by_type: dict[str, list] = {t: [] for t in TYPE_ORDER}
    for s in sources:
        t = s.get("type", "news_site")
        by_type.setdefault(t, []).append(s)

    total = len(sources)
    stat_items = [f'<div class="stat"><div class="stat-value">{total}</div><div class="stat-label">Total</div></div>']
    for t in TYPE_ORDER:
        grp = by_type.get(t, [])
        if grp:
            stat_items.append(
                f'<div class="stat"><div class="stat-value">{len(grp)}</div>'
                f'<div class="stat-label">{_esc(TYPE_LABELS.get(t, t))}</div></div>'
            )
    stats_html = "\n    ".join(stat_items)

    groups_html = "\n\n".join(
        _build_group(t, by_type[t]) for t in TYPE_ORDER if by_type.get(t)
    )

    body = render_template(
        TEMPLATE,
        today=_esc(today),
        stats_html=stats_html,
        groups_html=groups_html,
    )

    return render_shell(
        title="Intelligence Sources — Scottish Venture News",
        favicon_href="../favicon.ico",
        stylesheets=["../assets/style.css", "../assets/sources.css"],
        body=body,
    )


def run() -> None:
    data    = json.loads(SOURCES.read_text())
    sources = data["sources"]
    today   = date.today().isoformat()
    page    = build_page(sources, today)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(page, encoding="utf-8")
    print(f"Written: {OUT_FILE}  ({len(sources)} sources)")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
