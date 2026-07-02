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

ROOT     = Path(__file__).resolve().parent.parent
SOURCES  = ROOT / "config" / "sources.json"
OUT_DIR  = ROOT / "docs" / "sources"
OUT_FILE = OUT_DIR / "index.html"

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

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="../favicon.ico">
  <title>Intelligence Sources — Scottish Venture News</title>
  <link rel="stylesheet" href="../assets/style.css">
  <style>
    body {{ font-size: 13px; line-height: 1.5; }}
    a {{ color: var(--navy); text-decoration: none; }}
    a:hover {{ color: var(--blue); text-decoration: underline; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 28px 20px 48px; }}

    .stats-bar {{ margin-bottom: 28px; }}
    .stat {{ min-width: 90px; }}

    .src-group {{ margin-bottom: 36px; }}
    .group-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }}
    .group-header h2 {{ font-size: 14px; font-weight: 700; color: var(--navy); }}
    .group-count {{
      font-size: 11px; font-weight: 600; color: var(--slate);
      background: var(--light-grey); border-radius: 10px; padding: 1px 7px;
    }}
    .group-desc {{ font-size: 12px; color: var(--grey); margin-bottom: 10px; }}

    thead th {{ padding: 8px 12px; background: #F0F1F2; }}
    .src-name {{ width: 260px; font-weight: 500; white-space: nowrap; }}
    .src-name a {{ color: var(--navy); }}
    .src-name a:hover {{ color: var(--blue); }}
    .src-notes {{ font-size: 12px; color: var(--slate); line-height: 1.5; }}

    .badge {{
      display: inline-block; font-size: 9px; font-weight: 700;
      padding: 1px 5px; border-radius: 3px; vertical-align: middle;
      margin-left: 5px; letter-spacing: 0.04em; text-transform: uppercase;
    }}
    .badge-rss {{ background: #E8F2EB; color: #4a8a6a; }}
    .badge-be  {{ background: #FFF4E0; color: #a07820; }}

    footer {{ margin-top: 24px; }}
  </style>
</head>
<body>
<div class="container">

  <a class="back-link" href="../">← Scottish Venture News</a>

  <header>
    <h1>Intelligence Sources</h1>
    <p>Every source monitored by the automated pipeline. Regenerated each run. &nbsp;·&nbsp; Last updated {_esc(today)}</p>
  </header>

  <div class="stats-bar">
    {stats_html}
  </div>

{groups_html}

  <footer>Scottish Venture News &nbsp;·&nbsp; Data sourced from public news coverage only &nbsp;·&nbsp; Not investment advice</footer>

</div>
</body>
</html>"""


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
