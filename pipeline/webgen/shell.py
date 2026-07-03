"""Shared HTML page shell for the docs/*.html generators (Stages 6-8).

Wraps a page's body content with the common <head>/<html>/<body> skeleton
(doctype, meta tags, favicon, stylesheet links, closing script tags) so
each generator only needs to supply its own body markup.
"""
from __future__ import annotations

from pathlib import Path
from string import Template

_SHELL = Template("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="$favicon_href">
  <title>$title</title>$stylesheet_tags
</head>
<body>
$body$script_tags
</body>
</html>""")


def render_shell(
    *,
    title: str,
    favicon_href: str,
    stylesheets: list[str],
    body: str,
    scripts: list[str] | None = None,
) -> str:
    """Wrap `body` HTML in the shared page skeleton.

    `stylesheets` and `scripts` are href/src paths, rendered in order.
    Each tag is emitted on its own leading-newline line, so an empty list
    contributes nothing rather than leaving a blank line behind.
    """
    stylesheet_tags = "".join(f'\n  <link rel="stylesheet" href="{href}">' for href in stylesheets)
    script_tags = "".join(f'\n<script src="{src}"></script>' for src in (scripts or []))
    return _SHELL.substitute(
        favicon_href=favicon_href,
        title=title,
        stylesheet_tags=stylesheet_tags,
        body=body,
        script_tags=script_tags,
    )


def render_template(path: Path, **kwargs: str) -> str:
    """Read a body template file and substitute its $placeholders."""
    return Template(path.read_text(encoding="utf-8")).substitute(**kwargs)
