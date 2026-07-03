#!/usr/bin/env python3
"""Stage 8 — Landing Page Generator.

Reads the latest weekly report from data/reports/, copies its chart PNGs to
docs/charts/, converts the report markdown to HTML, and writes docs/index.html.
No external dependencies beyond the standard library.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from webgen import markdown_lite
from webgen.shell import render_shell, render_template

ROOT        = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
CHARTS_SRC  = REPORTS_DIR / "charts"
DOCS_DIR    = ROOT / "docs"
CHARTS_DST  = DOCS_DIR / "charts"
OUT         = DOCS_DIR / "index.html"
TEMPLATE    = ROOT / "pipeline" / "webgen" / "templates" / "landing.html"

BUTTONDOWN_URL = "https://buttondown.com/scottishventurenews"
ARCHIVE_URL    = f"{BUTTONDOWN_URL}/archive"
DEALS_URL      = "deals/"
INVESTORS_URL  = "investors/"
SOURCES_URL    = "sources/"


# ── charts ───────────────────────────────────────────────────────────────────

def _copy_charts(date_str: str) -> None:
    CHARTS_DST.mkdir(parents=True, exist_ok=True)
    for suffix in ("_stage.png", "_sector.png"):
        src = CHARTS_SRC / f"{date_str}{suffix}"
        if src.exists():
            shutil.copy2(src, CHARTS_DST / src.name)


# ── html template ────────────────────────────────────────────────────────────

def _build_html(issue_title: str, report_html: str) -> str:
    body = render_template(
        TEMPLATE,
        deals_url=DEALS_URL,
        investors_url=INVESTORS_URL,
        sources_url=SOURCES_URL,
        buttondown_url=BUTTONDOWN_URL,
        archive_url=ARCHIVE_URL,
        issue_title=issue_title,
        report_html=report_html,
    )
    return render_shell(
        title="Scottish Venture News",
        favicon_href="favicon.ico",
        stylesheets=["assets/style.css", "assets/landing.css"],
        body=body,
    )


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
    issue_title, report_html = markdown_lite.to_html(md)

    html = _build_html(issue_title, report_html)
    OUT.write_text(html, encoding="utf-8")
    print(f"Written: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    run()
