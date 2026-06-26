"""Publishes the weekly report as a draft on Buttondown.

Reads `data/reports/YYYY-MM-DD_vc-report.md`, uploads its two embedded chart
PNGs to ImgBB (Buttondown's API doesn't accept file attachments), rewrites the
local chart paths to the returned ImgBB URLs, then creates a draft on Buttondown
for manual review and send.

Writes `data/processed/publish_manifest_YYYY-MM-DD.json` with the Buttondown
draft ID and ImgBB delete URLs so `pipeline/rollback.py` can undo the publish.

Requires IMGBB_API_KEY and BUTTONDOWN_API_KEY in a .env file at the project root.

Usage:
    python pipeline/newsletter_publish.py [--date YYYY-MM-DD]
"""
import argparse
import base64
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

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
BUTTONDOWN_EMAILS_URL = "https://api.buttondown.com/v1/emails"

IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\((charts/[^)]+\.png)\)")


def _upload_chart_to_imgbb(image_path: Path, api_key: str) -> dict:
    """Upload a chart PNG to ImgBB. Returns {url, delete_url}."""
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
    return {
        "filename": image_path.name,
        "url": payload["data"]["url"],
        "delete_url": payload["data"].get("delete_url", ""),
    }


def _rewrite_chart_links(report_text: str, report_dir: Path, imgbb_key: str) -> tuple[str, list[dict]]:
    """Replace local chart paths with ImgBB URLs. Returns (rewritten_text, images_metadata)."""
    images: list[dict] = []

    def replace(match):
        alt_text, relative_path = match.group(1), match.group(2)
        image_path = report_dir / relative_path
        if not image_path.exists():
            raise FileNotFoundError(f"Chart not found on disk: {image_path}")
        meta = _upload_chart_to_imgbb(image_path, imgbb_key)
        images.append(meta)
        return f"![{alt_text}]({meta['url']})"

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

    imgbb_key = os.environ.get("IMGBB_API_KEY")
    if not imgbb_key:
        raise RuntimeError("IMGBB_API_KEY must be set in .env")
    buttondown_key = os.environ.get("BUTTONDOWN_API_KEY")
    if not buttondown_key:
        raise RuntimeError("BUTTONDOWN_API_KEY must be set in .env")

    run_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"{run_date}_vc-report.md"
    if not report_path.exists():
        raise FileNotFoundError(f"No report found at {report_path}")

    report_text = report_path.read_text()
    subject = _extract_subject(report_text)
    body, images = _rewrite_chart_links(report_text, report_path.parent, imgbb_key)

    draft = _publish_to_buttondown(subject, body, buttondown_key)

    manifest = {
        "date": run_date,
        "buttondown_draft_id": draft.get("id"),
        "imgbb_images": images,
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
