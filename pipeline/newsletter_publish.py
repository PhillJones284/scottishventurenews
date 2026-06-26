"""Publishes a weekly report as a draft on Buttondown and/or dev.to — manual step, not part of run.py.

Reads `data/reports/YYYY-MM-DD_vc-report.md`, uploads its two embedded chart
PNGs to ImgBB (neither target platform's API takes file attachments),
rewrites the local chart paths to the returned ImgBB URLs, then creates a
draft on each requested platform for manual review and publish/send.

Requires IMGBB_API_KEY plus the key(s) for whichever platform(s) are
targeted (BUTTONDOWN_API_KEY, DEVTO_API_KEY) in a .env file at the project
root (see pipeline/requirements.txt for python-dotenv).

Usage:
    python pipeline/newsletter_publish.py [--date YYYY-MM-DD] [--platform all|buttondown|devto]
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
DEVTO_ARTICLES_URL = "https://dev.to/api/articles"

IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\((charts/[^)]+\.png)\)")

PLATFORMS = ("buttondown", "devto")


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


def _publish_to_buttondown(subject, body, api_key):
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


def _publish_to_devto(subject, body, api_key):
    response = httpx.post(
        DEVTO_ARTICLES_URL,
        headers={"api-key": api_key},
        json={"article": {"title": subject, "body_markdown": body, "published": False}},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"dev.to draft creation failed ({response.status_code}): {response.text}")
    return response.json()


_PUBLISHERS = {
    "buttondown": (_publish_to_buttondown, "BUTTONDOWN_API_KEY"),
    "devto": (_publish_to_devto, "DEVTO_API_KEY"),
}


def run(date_str=None, platforms=PLATFORMS):
    load_dotenv()
    imgbb_key = os.environ.get("IMGBB_API_KEY")
    if not imgbb_key:
        raise RuntimeError("IMGBB_API_KEY must be set in .env")

    platform_keys = {}
    for platform in platforms:
        env_var = _PUBLISHERS[platform][1]
        key = os.environ.get(env_var)
        if not key:
            raise RuntimeError(f"{env_var} must be set in .env to publish to {platform}")
        platform_keys[platform] = key

    run_date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"{run_date_str}_vc-report.md"
    if not report_path.exists():
        raise FileNotFoundError(f"No report found at {report_path}")

    report_text = report_path.read_text()
    subject = _extract_subject(report_text)
    body = _rewrite_chart_links(report_text, report_path.parent, imgbb_key)

    results = {}
    for platform in platforms:
        publish_fn, _ = _PUBLISHERS[platform]
        results[platform] = publish_fn(subject, body, platform_keys[platform])

    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="Run date in YYYY-MM-DD format (default: today)")
    ap.add_argument("--platform", default="all", choices=["all", *PLATFORMS], help="Which platform(s) to publish to")
    args = ap.parse_args()
    platforms = PLATFORMS if args.platform == "all" else (args.platform,)

    try:
        results = run(date_str=args.date, platforms=platforms)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if "buttondown" in results:
        draft_id = results["buttondown"].get("id")
        print(f"Draft created on Buttondown (id: {draft_id}). Review and send from the Buttondown dashboard.")
    if "devto" in results:
        article = results["devto"]
        print(f"Draft created on dev.to (id: {article.get('id')}, url: {article.get('url')}). Review and publish from the dev.to dashboard.")


if __name__ == "__main__":
    main()
