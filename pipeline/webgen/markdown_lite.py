"""Minimal markdown → HTML conversion for the weekly report's markdown subset.

Handles: h1/h2/h3, bold, italic, links, images, bullet lists, paragraphs.
Not a general-purpose markdown parser — only what data/reports/*.md uses.
"""
from __future__ import annotations

import re


def to_html(text: str) -> tuple[str, str]:
    """Convert report markdown to HTML.

    Returns (issue_title, html). The report's H1 (issue title) is returned
    separately rather than rendered — the landing page displays it as the
    issue-date label instead.
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
        elif line.strip() in ("", "---"):
            flush_ul()
            parts.append("")
        else:
            flush_ul()
            parts.append(f"<p>{inline(line.strip())}</p>")

    flush_ul()
    return issue_title, "\n".join(p for p in parts if p)
