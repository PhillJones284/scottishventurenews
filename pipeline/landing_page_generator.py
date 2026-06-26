#!/usr/bin/env python3
"""Stage 8 — Landing Page Generator.

Reads the latest weekly report from data/reports/, copies its chart PNGs to
docs/charts/, converts the report markdown to HTML, and writes docs/index.html.
No external dependencies beyond the standard library.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
CHARTS_SRC  = REPORTS_DIR / "charts"
DOCS_DIR    = ROOT / "docs"
CHARTS_DST  = DOCS_DIR / "charts"
OUT         = DOCS_DIR / "index.html"

BUTTONDOWN_URL = "https://buttondown.com/scottish-vc-tracker"
ARCHIVE_URL    = f"{BUTTONDOWN_URL}/archive"
DEALS_URL      = "deals/"
INVESTORS_URL  = "investors/"


# ── markdown → html ──────────────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    """Convert the report's markdown subset to HTML.

    Handles: h1/h2/h3, bold, italic, links, images, bullet lists, paragraphs.
    The report's H1 (issue title) is returned separately as `issue_title`.
    """
    lines = text.split("\n")
    parts: list[str] = []
    in_ul = False
    issue_title: str = ""

    def flush_ul() -> None:
        nonlocal in_ul
        if in_ul:
            parts.append("</ul>")
            in_ul = False

    def inline(s: str) -> str:
        # images before links so the alt text isn't double-processed
        s = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',
                   r'<img src="\2" alt="\1" class="report-img">', s)
        # markdown links
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                   r'<a href="\2">\1</a>', s)
        # bare URLs in parentheses (e.g. Source lines in the spotlight)
        s = re.sub(r'(?<!=")\((https?://[^\s<>")\]]+)\)',
                   r'(<a href="\1">\1</a>)', s)
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'\*([^*]+)\*',     r'<em>\1</em>', s)
        return s

    for line in lines:
        if line.startswith("# "):
            flush_ul()
            issue_title = line[2:].strip()
            # Don't emit H1 — we display it as the issue-date label
        elif line.startswith("### "):
            flush_ul()
            parts.append(f"<h3>{inline(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            flush_ul()
            parts.append(f"<h2>{inline(line[3:].strip())}</h2>")
        elif line.startswith("- "):
            if not in_ul:
                parts.append("<ul>")
                in_ul = True
            parts.append(f"<li>{inline(line[2:].strip())}</li>")
        elif line.strip() == "":
            flush_ul()
            parts.append("")
        else:
            flush_ul()
            parts.append(f"<p>{inline(line.strip())}</p>")

    flush_ul()
    return issue_title, "\n".join(p for p in parts if p != "" or parts.index(p) == 0)


# ── charts ───────────────────────────────────────────────────────────────────

def _copy_charts(date_str: str) -> None:
    CHARTS_DST.mkdir(parents=True, exist_ok=True)
    for suffix in ("_stage.png", "_sector.png"):
        src = CHARTS_SRC / f"{date_str}{suffix}"
        if src.exists():
            shutil.copy2(src, CHARTS_DST / src.name)


# ── html template ────────────────────────────────────────────────────────────

def _build_html(issue_title: str, report_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scottish VC Tracker</title>
  <style>
    :root {{
      --navy:       #1F3B57;
      --slate:      #7C93A8;
      --grey:       #9AA0A6;
      --light-grey: #D8DCE0;
      --blue:       #7B9EB9;
      --green:      #6BA58A;
      --gold:       #C49A5A;
      --ink:        #222222;
      --bg:         #F7F7F6;
      --white:      #FFFFFF;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 14px;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.6;
    }}
    a {{ color: var(--navy); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .container {{ max-width: 760px; margin: 0 auto; padding: 40px 20px 64px; }}

    /* ── header ── */
    .site-header {{ margin-bottom: 32px; }}
    .site-header h1 {{
      font-size: 24px; font-weight: 700; color: var(--navy);
      letter-spacing: -0.02em; margin-bottom: 8px;
    }}
    .site-header p {{
      color: var(--slate); font-size: 13px; max-width: 600px; line-height: 1.5;
    }}

    /* ── nav cards ── */
    .nav-cards {{
      display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 28px;
    }}
    .nav-card {{
      flex: 1; min-width: 200px;
      background: var(--white); border: 1px solid var(--light-grey);
      border-radius: 6px; padding: 16px 18px;
      display: flex; flex-direction: column; gap: 4px;
      color: inherit;
    }}
    .nav-card:hover {{ border-color: var(--blue); text-decoration: none; }}
    .nav-card-label {{
      font-size: 10px; font-weight: 600; color: var(--slate);
      text-transform: uppercase; letter-spacing: 0.06em;
    }}
    .nav-card-title {{
      font-size: 14px; font-weight: 600; color: var(--navy);
    }}
    .nav-card-desc {{ font-size: 12px; color: var(--grey); }}

    /* ── subscribe bar ── */
    .subscribe-bar {{
      background: var(--navy); border-radius: 6px;
      padding: 18px 20px; margin-bottom: 40px;
      display: flex; align-items: center; justify-content: space-between;
      flex-wrap: wrap; gap: 12px;
    }}
    .subscribe-bar p {{
      color: #d4e0eb; font-size: 13px;
    }}
    .subscribe-bar strong {{ color: var(--white); }}
    .subscribe-links {{ display: flex; gap: 10px; align-items: center; flex-shrink: 0; }}
    .btn-subscribe {{
      background: var(--gold); color: var(--white);
      font-size: 13px; font-weight: 600;
      padding: 8px 16px; border-radius: 4px;
      white-space: nowrap;
    }}
    .btn-subscribe:hover {{ opacity: 0.9; text-decoration: none; }}
    .btn-archive {{
      color: #adc6db; font-size: 12px; white-space: nowrap;
    }}
    .btn-archive:hover {{ color: var(--white); text-decoration: none; }}

    /* ── issue divider ── */
    .issue-header {{
      display: flex; align-items: baseline; gap: 12px;
      margin-bottom: 20px;
    }}
    .issue-label {{
      font-size: 10px; font-weight: 600; color: var(--slate);
      text-transform: uppercase; letter-spacing: 0.08em;
    }}
    .issue-title {{ font-size: 13px; color: var(--grey); }}

    /* ── report body ── */
    .report-body h2 {{
      font-size: 15px; font-weight: 700; color: var(--navy);
      margin: 28px 0 8px; padding-top: 24px;
      border-top: 1px solid var(--light-grey);
    }}
    .report-body h2:first-child {{ margin-top: 0; padding-top: 0; border-top: none; }}
    .report-body h3 {{
      font-size: 13px; font-weight: 700; color: var(--ink);
      margin: 18px 0 6px;
    }}
    .report-body p {{ margin-bottom: 10px; font-size: 14px; }}
    .report-body ul {{
      margin: 6px 0 14px 18px;
    }}
    .report-body li {{ margin-bottom: 6px; font-size: 14px; }}
    .report-body em {{
      color: var(--slate); font-style: normal; font-size: 12px;
    }}
    .report-body strong {{ font-weight: 600; }}
    .report-body a {{ color: var(--blue); }}
    .report-body .report-img {{
      max-width: 100%; height: auto;
      border: 1px solid var(--light-grey); border-radius: 4px;
      margin: 8px 0 16px; display: block;
    }}
  </style>
</head>
<body>
<div class="container">

  <header class="site-header">
    <h1>Scottish VC Tracker</h1>
    <p>A weekly intelligence briefing monitoring public news coverage for venture capital investment
    activity in Scottish startups and scaleups — tracking who's investing, at what stages,
    in which sectors, and with what cadence.</p>
  </header>

  <div class="nav-cards">
    <a class="nav-card" href="{DEALS_URL}">
      <span class="nav-card-label">Resource</span>
      <span class="nav-card-title">Deal Table →</span>
      <span class="nav-card-desc">Searchable, filterable table of every deal tracked this quarter and year to date</span>
    </a>
    <a class="nav-card" href="{INVESTORS_URL}">
      <span class="nav-card-label">Resource</span>
      <span class="nav-card-title">Investor Directory →</span>
      <span class="nav-card-desc">Per-investor stats and profiles for every VC firm active in Scotland</span>
    </a>
  </div>

  <div class="subscribe-bar">
    <p><strong>Get it in your inbox.</strong> New issue each week, free.</p>
    <div class="subscribe-links">
      <a class="btn-subscribe" href="{BUTTONDOWN_URL}">Subscribe</a>
      <a class="btn-archive" href="{ARCHIVE_URL}">Past issues →</a>
    </div>
  </div>

  <div class="issue-header">
    <span class="issue-label">Latest issue</span>
    <span class="issue-title">{issue_title}</span>
  </div>

  <div class="report-body">
    {report_html}
  </div>

</div>
</body>
</html>"""


# ── main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    reports = sorted(REPORTS_DIR.glob("????-??-??_vc-report.md"))
    if not reports:
        raise FileNotFoundError("No report files found in data/reports/")

    latest = reports[-1]
    date_str = latest.name[:10]
    print(f"Using report: {latest.name}")

    _copy_charts(date_str)

    md = latest.read_text(encoding="utf-8")
    issue_title, report_html = _md_to_html(md)

    html = _build_html(issue_title, report_html)
    OUT.write_text(html, encoding="utf-8")
    print(f"Written: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    run()
