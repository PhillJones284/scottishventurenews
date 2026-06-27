#!/usr/bin/env python3
"""
Pre-launch backfill filter.

Removes records from investments.json where announcement_date falls within
the past N days, so those deals are picked up fresh on the first official run.
Run this between Stage 2 (parser) and Stage 3 (deduplicator).
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

PROCESSED_DIR = Path("data/processed")
INPUT_FILE = PROCESSED_DIR / "investments.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Reference date (YYYY-MM-DD), default today",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Window in days — records newer than this are removed (default 7)",
    )
    args = parser.parse_args()

    ref_date = date.fromisoformat(args.date)
    cutoff = (ref_date - timedelta(days=args.days)).isoformat()

    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found — run Stage 2 (parser) first")
        raise SystemExit(1)

    records = json.loads(INPUT_FILE.read_text())

    kept, removed = [], []
    for r in records:
        ad = r.get("announcement_date")
        if ad and ad >= cutoff:
            removed.append(r)
        else:
            kept.append(r)

    INPUT_FILE.write_text(json.dumps(kept, indent=2))

    print(f"Reference date : {args.date}")
    print(f"Cutoff         : {cutoff} (records on or after this date removed)")
    print(f"Kept           : {len(kept)}")
    print(f"Removed        : {len(removed)}")

    if removed:
        print("\nRemoved (will be picked up fresh on first official run):")
        for r in sorted(removed, key=lambda x: x.get("announcement_date", "")):
            print(
                f"  {r.get('announcement_date', 'unknown'):12}  "
                f"{r.get('company_name', 'unknown'):40}  "
                f"{r.get('round_type', '')}"
            )
    else:
        print("\nNo records removed — all records pre-date the cutoff.")


if __name__ == "__main__":
    main()
