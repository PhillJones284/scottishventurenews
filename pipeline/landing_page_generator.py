#!/usr/bin/env python3
"""Stage 8 — Landing Page Generator.

Reads the latest report from data/reports/, copies its embedded local images
(the two Stage 3.6 charts, plus any image an editorial note embeds) to
docs/, converts the report markdown to HTML, and writes docs/index.html.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from PIL import Image

from webgen import markdown_lite
from webgen.shell import render_shell, render_template

ROOT          = Path(__file__).resolve().parent.parent
REPORTS_DIR   = ROOT / "data" / "reports"
EDITORIAL_DIR = ROOT / "data" / "editorial"
CHARTS_SRC    = REPORTS_DIR / "charts"
DOCS_DIR      = ROOT / "docs"
CHARTS_DST  = DOCS_DIR / "charts"
OUT         = DOCS_DIR / "index.html"
TEMPLATE    = ROOT / "pipeline" / "webgen" / "templates" / "landing.html"

# Buttondown flags any embedded image wider or taller than this as a
# deliverability risk (discovered 2026-10-05: an editorial image at native
# 2048x1293 triggered an "attached image might be too large to fit" warning).
# Any local image the report embeds — not just the two charts, which are
# already generated within this bound — is downsized to fit before being
# published, so the same issue can't resurface via a future editorial image.
MAX_IMAGE_DIMENSION = 1200

LOCAL_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(((?!https?://)[^)]+\.(?:png|jpe?g|gif|webp))\)")

BUTTONDOWN_URL = "https://buttondown.com/scottishventurenews"
ARCHIVE_URL    = f"{BUTTONDOWN_URL}/archive"
DEALS_URL      = "deals/"
INVESTORS_URL  = "investors/"
SOURCES_URL    = "sources/"


# ── embedded images ──────────────────────────────────────────────────────────

def _copy_charts(date_str: str) -> None:
    CHARTS_DST.mkdir(parents=True, exist_ok=True)
    for suffix in ("_stage.png", "_sector.png"):
        src = CHARTS_SRC / f"{date_str}{suffix}"
        if src.exists():
            shutil.copy2(src, CHARTS_DST / src.name)


def _copy_embedded_images(report_text: str) -> None:
    """Copy every local image the report markdown embeds into docs/ at the
    same relative path, downsizing anything over MAX_IMAGE_DIMENSION first.

    Charts are already copied (and already within bounds) by _copy_charts
    above; this additionally picks up anything else a report embeds, chiefly
    an editorial image (see CLAUDE.md's "Adding an editorial" section). The
    reporter agent leaves such a reference's filename exactly as Phill wrote
    it in data/editorial/pending.md — it has no Bash tool to copy the binary
    file into data/reports/ itself — so the source is resolved against
    data/reports/ first (matching the literal relative path, for anything
    actually placed there) and data/editorial/ second (where an editorial
    image actually lives).
    """
    for match in LOCAL_IMAGE_RE.finditer(report_text):
        rel_path = match.group(1)
        src = REPORTS_DIR / rel_path
        if not src.exists():
            src = EDITORIAL_DIR / Path(rel_path).name
        if not src.exists():
            continue
        dst = DOCS_DIR / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            if im.width > MAX_IMAGE_DIMENSION or im.height > MAX_IMAGE_DIMENSION:
                im = im.copy()
                im.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
                im.save(dst)
                continue
        shutil.copy2(src, dst)


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
    _copy_embedded_images(md)
    issue_title, report_html = markdown_lite.to_html(md)

    html = _build_html(issue_title, report_html)
    OUT.write_text(html, encoding="utf-8")
    print(f"Written: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    run()
