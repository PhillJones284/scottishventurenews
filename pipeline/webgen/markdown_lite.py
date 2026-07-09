"""Minimal markdown → HTML conversion for the weekly report's markdown subset.

Handles: h1/h2/h3, bold, italic, links, images, bullet lists, paragraphs.
Not a general-purpose markdown parser — only what data/reports/*.md uses.
"""
from __future__ import annotations

import re

# Section whose "- **Deal** ... \n  *Source: ...*" bullets render as plain,
# unbulleted deal blocks on the landing page instead of <ul><li> — the report
# markdown itself (and the newsletter, which renders it separately) is untouched.
_DEAL_BLOCK_SECTION = "what we found this week"


def to_html(text: str) -> tuple[str, str]:
    """Convert report markdown to HTML.

    Returns (issue_title, html). The report's H1 (issue title) is returned
    separately rather than rendered — the landing page displays it as the
    issue-date label instead.
    """
    lines = text.split("\n")
    parts: list[str] = []
    in_ul = False
    in_deal_block = False
    current_section = ""
    issue_title: str = ""

    def flush_ul() -> None:
        nonlocal in_ul
        if in_ul:
            parts.append("</ul>")
            in_ul = False

    def close_deal_block() -> None:
        nonlocal in_deal_block
        if in_deal_block:
            parts.append("</div>")
            in_deal_block = False

    def in_deals_section() -> bool:
        return _DEAL_BLOCK_SECTION in current_section.lower()

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
            close_deal_block()
            issue_title = line[2:].strip()
            # Don't emit H1 — we display it as the issue-date label
        elif line.startswith("### "):
            flush_ul()
            close_deal_block()
            parts.append(f"<h3>{inline(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            flush_ul()
            close_deal_block()
            current_section = line[3:].strip()
            parts.append(f"<h2>{inline(current_section)}</h2>")
        elif line.startswith("- "):
            if in_deals_section():
                close_deal_block()
                parts.append('<div class="deal-block">')
                in_deal_block = True
                parts.append(f"<p>{inline(line[2:].strip())}</p>")
            else:
                if not in_ul:
                    parts.append("<ul>")
                    in_ul = True
                parts.append(f"<li>{inline(line[2:].strip())}</li>")
        elif line.strip() in ("", "---"):
            flush_ul()
            close_deal_block()
            parts.append("")
        else:
            flush_ul()
            stripped = line.strip()
            if in_deal_block and stripped.startswith("*Source:"):
                parts.append(f'<p class="deal-source">{inline(stripped)}</p>')
            else:
                close_deal_block()
                parts.append(f"<p>{inline(stripped)}</p>")

    flush_ul()
    close_deal_block()
    return issue_title, "\n".join(p for p in parts if p)
