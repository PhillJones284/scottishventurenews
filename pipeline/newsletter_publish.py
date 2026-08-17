"""Publishes the monthly report as a draft on Buttondown.

Reads `data/reports/YYYY-MM-DD_vc-report.md`, rewrites its two embedded chart
image links to point at the copies already published to GitHub Pages (Stage 8
copies them into `docs/charts/`, and Stage 9 pushes `docs/` before this stage
runs — Buttondown's API doesn't accept file attachments, so the charts need a
public URL to embed), then creates a draft on Buttondown for manual review and
send.

Charts were previously hosted via an ImgBB upload, but ImgBB began gating
hotlinked images in emails behind a paid Pro plan (discovered 2026-07-20 when
the 13 July issue's charts silently degraded to an "upgrade to Pro" placeholder
in the public archive) — GitHub Pages already hosts the identical files for
free, so linking there directly removes that failure mode entirely.

Writes `data/processed/publish_manifest_YYYY-MM-DD.json` with the Buttondown
draft ID so `pipeline/rollback.py` can undo the publish.

Requires BUTTONDOWN_API_KEY in a .env file at the project root.

Usage:
    python pipeline/newsletter_publish.py [--date YYYY-MM-DD]
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
REPORTS_DIR = ROOT / "data" / "reports"
PROCESSED_DIR = ROOT / "data" / "processed"
DOCS_CHARTS_DIR = ROOT / "docs" / "charts"

BUTTONDOWN_EMAILS_URL = "https://api.buttondown.com/v1/emails"

SITE_BASE = "https://philljones284.github.io/scottishventurenews"

EMAIL_FOOTER = f"""
---

**Browse the full dataset so far**

- [Deal Table]({SITE_BASE}/deals/) — searchable, filterable table of every deal tracked this quarter and year to date
- [Investor Directory]({SITE_BASE}/investors/) — per-investor stats and deal history for every VC firm active in Scotland
- [Intelligence Sources]({SITE_BASE}/sources/) — every news source, VC newsroom, and database monitored by the pipeline
"""

SUBSCRIBE_BLOCK = """
## If you were forwarded this email, why not subscribe?

{{ subscribe_form }}
"""

IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\((charts/[^)]+\.png)\)")


def _rewrite_chart_links(report_text: str) -> tuple[str, list[dict]]:
    """Replace local chart paths with their published GitHub Pages URLs.

    Returns (rewritten_text, images_metadata) — images_metadata is kept in the
    manifest for informational purposes only (there's no upload to undo on
    rollback, unlike the old ImgBB step).
    """
    images: list[dict] = []

    def replace(match):
        alt_text, relative_path = match.group(1), match.group(2)
        filename = Path(relative_path).name
        docs_path = DOCS_CHARTS_DIR / filename
        if not docs_path.exists():
            raise FileNotFoundError(
                f"Chart not found at {docs_path} — Stage 8/9 must run (and push docs/) "
                f"before Stage 10 links to it"
            )
        url = f"{SITE_BASE}/charts/{filename}"
        images.append({"filename": filename, "url": url})
        return f"![{alt_text}]({url})"

    rewritten = IMAGE_LINK_RE.sub(replace, report_text)
    return rewritten, images


def _extract_subject(report_text: str) -> str:
    for line in report_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError("Report has no top-level heading to use as subject line")


def _publish_to_buttondown(subject: str, body: str, api_key: str) -> dict:
    response = httpx.post(
        BUTTONDOWN_EMAILS_URL,
        headers={"Authorization": f"Token {api_key}"},
        json={
            "subject": subject,
            "body": "<!-- buttondown-editor-mode: plaintext -->\n\n" + body,
            "status": "draft",
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Buttondown draft creation failed ({response.status_code}): {response.text}")
    return response.json()


def run(date_str: str | None = None) -> dict:
    """Publish the report as a Buttondown draft. Returns the manifest dict."""
    load_dotenv()

    buttondown_key = os.environ.get("BUTTONDOWN_API_KEY")
    if not buttondown_key:
        raise RuntimeError("BUTTONDOWN_API_KEY must be set in .env")

    run_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"{run_date}_vc-report.md"
    if not report_path.exists():
        raise FileNotFoundError(f"No report found at {report_path}")

    report_text = report_path.read_text()
    subject = _extract_subject(report_text)
    # Strip the leading H1 — Buttondown renders the newsletter name + date as its
    # own header, so keeping the H1 in the body produces a triple title.
    body_text = re.sub(r"^#[^#][^\n]*\n+", "", report_text, count=1)
    body_text, n_inserted = re.subn(
        r"\n## The Numbers\n", SUBSCRIBE_BLOCK + "\n## The Numbers\n", body_text, count=1
    )
    if n_inserted == 0:
        raise ValueError("Could not find '## The Numbers' heading to insert the subscribe block before")
    body, images = _rewrite_chart_links(body_text + EMAIL_FOOTER)

    draft = _publish_to_buttondown(subject, body, buttondown_key)

    manifest = {
        "date": run_date,
        "buttondown_draft_id": draft.get("id"),
        "chart_images": images,
        "git_commit_hash": None,  # filled in by run.py after git commit
    }
    manifest_path = PROCESSED_DIR / f"publish_manifest_{run_date}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default: today)")
    args = ap.parse_args()

    try:
        manifest = run(date_str=args.date)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    draft_id = manifest["buttondown_draft_id"]
    print(f"Buttondown draft created (id: {draft_id}). Review and send from the Buttondown dashboard.")
    print(f"Manifest saved: data/processed/publish_manifest_{manifest['date']}.json")


if __name__ == "__main__":
    main()
