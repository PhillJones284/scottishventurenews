"""Publishes a weekly report as a Buttondown draft — manual step, not part of run.py.

Reads `data/reports/YYYY-MM-DD_vc-report.md`, uploads its two embedded chart
PNGs to ImgBB (Buttondown's email API takes a body string, not file
attachments), rewrites the local chart paths to the returned ImgBB URLs, then
POSTs the result to Buttondown as a draft email for manual review and send.

Requires BUTTONDOWN_API_KEY and IMGBB_API_KEY in a .env file at the project
root (see pipeline/requirements.txt for python-dotenv).

Usage:
    python pipeline/newsletter_publish.py [--date YYYY-MM-DD]
"""
import argparse
import base64
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
REPORTS_DIR = ROOT / "data" / "reports"

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
BUTTONDOWN_EMAILS_URL = "https://api.buttondown.com/v1/emails"

IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\((charts/[^)]+\.png)\)")


def _upload_chart_to_imgbb(image_path, api_key):
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    response = httpx.post(
        IMGBB_UPLOAD_URL,
        data={"key": api_key, "image": image_b64},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"ImgBB upload failed for {image_path.name}: {payload}")
    return payload["data"]["url"]


def _rewrite_chart_links(report_text, report_dir, imgbb_key):
    def replace(match):
        alt_text, relative_path = match.group(1), match.group(2)
        image_path = report_dir / relative_path
        if not image_path.exists():
            raise FileNotFoundError(f"Chart referenced in report but not found on disk: {image_path}")
        url = _upload_chart_to_imgbb(image_path, imgbb_key)
        return f"![{alt_text}]({url})"

    return IMAGE_LINK_RE.sub(replace, report_text)


def _extract_subject(report_text):
    for line in report_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError("Report has no top-level heading to use as a subject line")


def run(date_str=None):
    load_dotenv()
    buttondown_key = os.environ.get("BUTTONDOWN_API_KEY")
    imgbb_key = os.environ.get("IMGBB_API_KEY")
    if not buttondown_key or not imgbb_key:
        raise RuntimeError("BUTTONDOWN_API_KEY and IMGBB_API_KEY must both be set in .env")

    run_date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"{run_date_str}_vc-report.md"
    if not report_path.exists():
        raise FileNotFoundError(f"No report found at {report_path}")

    report_text = report_path.read_text()
    subject = _extract_subject(report_text)
    body = _rewrite_chart_links(report_text, report_path.parent, imgbb_key)

    response = httpx.post(
        BUTTONDOWN_EMAILS_URL,
        headers={"Authorization": f"Token {buttondown_key}"},
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="Run date in YYYY-MM-DD format (default: today)")
    args = ap.parse_args()
    try:
        result = run(date_str=args.date)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    draft_id = result.get("data", {}).get("id") or result.get("id")
    print(f"Draft created in Buttondown (id: {draft_id}). Review and send from the Buttondown dashboard.")


if __name__ == "__main__":
    main()
