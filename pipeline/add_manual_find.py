"""Stage a manually found article for the next full pipeline run.

Fetches the article now (while the link is live) and appends it to
the persistent data/raw/manual_finds.json queue. The scraper agent
(Stage 1b) drains pending entries on the next run and extracts a
structured investment record from the captured text.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import trafilatura

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
MANUAL_FINDS_PATH = DATA_RAW / "manual_finds.json"

USER_AGENT = "Mozilla/5.0 (compatible; Scottish-VC-Tracker/1.0)"


def _fetch(url: str) -> tuple[str | None, str | None]:
    """Return (title, text), or (None, None) if fetch/extraction fails."""
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as e:
        print(
            f"Warning: fetch failed ({e}) — saving URL only; "
            "the scraper agent will WebFetch it on the next run."
        )
        return None, None

    extracted = trafilatura.extract(resp.text, output_format="json", with_metadata=True)
    if not extracted:
        print(
            "Warning: could not extract article text — saving URL only; "
            "the scraper agent will WebFetch it on the next run."
        )
        return None, None

    data = json.loads(extracted)
    return data.get("title"), data.get("text")


def run(url: str, note: str | None = None) -> dict:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    title, text = _fetch(url)

    entry = {
        "source_slug": "manual",
        "source_name": "Manual submission",
        "url": url,
        "title": title,
        "text": text,
        "note": note,
        "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "pending",
    }

    existing = []
    if MANUAL_FINDS_PATH.exists():
        existing = json.loads(MANUAL_FINDS_PATH.read_text())
    existing.append(entry)
    MANUAL_FINDS_PATH.write_text(json.dumps(existing, indent=2))
    return entry


def main():
    parser = argparse.ArgumentParser(
        description="Stage a manually found article for the next full pipeline run."
    )
    parser.add_argument("url")
    parser.add_argument("note", nargs="?", default=None)
    args = parser.parse_args()

    entry = run(args.url, args.note)
    status = "with extracted text" if entry["text"] else "URL only (fetch failed)"
    print(f"Saved to {MANUAL_FINDS_PATH.relative_to(ROOT)} ({status}).")
    if entry["title"]:
        print(f"Title: {entry['title']}")


if __name__ == "__main__":
    main()
