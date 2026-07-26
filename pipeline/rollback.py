"""Roll back a pipeline publish.

Reads the publish manifest written by Stage 10, then:
  1. Deletes the Buttondown draft via the API
  2. Reverts the docs/ git commit and pushes to GitHub (restoring the previous
     page — this also reverts the chart PNGs the newsletter linked to, since
     they're published as part of the same docs/ commit)

The data files (ledger, reports, vc-profiles) are not touched — they remain
intact so you can fix and re-run without starting the pipeline from scratch.

Usage:
    python pipeline/rollback.py [--date YYYY-MM-DD]
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
BUTTONDOWN_EMAILS_URL = "https://api.buttondown.com/v1/emails"


def _delete_buttondown_draft(draft_id: str, api_key: str) -> None:
    resp = httpx.delete(
        f"{BUTTONDOWN_EMAILS_URL}/{draft_id}",
        headers={"Authorization": f"Token {api_key}"},
        timeout=15,
    )
    if resp.status_code == 404:
        print(f"  [Buttondown] Draft {draft_id} not found — may already be deleted.")
        return
    if resp.status_code >= 400:
        raise RuntimeError(f"Buttondown delete failed ({resp.status_code}): {resp.text}")
    print(f"  [Buttondown] Draft {draft_id} deleted.")


def _git_revert(commit_hash: str) -> None:
    print(f"  [Git] Reverting commit {commit_hash[:8]}...")
    result = subprocess.run(
        ["git", "revert", commit_hash, "--no-edit"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"git revert failed:\n{result.stderr}")
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"git push failed:\n{result.stderr}")
    print("  [Git] Revert commit pushed. GitHub Pages will redeploy shortly.")


def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="Date of the run to roll back (YYYY-MM-DD, default: today)")
    args = ap.parse_args()

    run_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    manifest_path = PROCESSED_DIR / f"publish_manifest_{run_date}.json"

    if not manifest_path.exists():
        print(f"ERROR: No publish manifest found for {run_date} at {manifest_path}", file=sys.stderr)
        print("Nothing to roll back.", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    print(f"Rolling back publish for {run_date}...\n")

    # 1. Buttondown draft
    draft_id = manifest.get("buttondown_draft_id")
    if draft_id:
        print("Step 1: Deleting Buttondown draft...")
        buttondown_key = os.environ.get("BUTTONDOWN_API_KEY")
        if not buttondown_key:
            print("  [Buttondown] BUTTONDOWN_API_KEY not set — skipping. Delete draft manually in the dashboard.")
        else:
            try:
                _delete_buttondown_draft(draft_id, buttondown_key)
            except Exception as exc:
                print(f"  [Buttondown] Failed: {exc}")
                print(f"  Delete manually in the Buttondown dashboard (draft id: {draft_id}).")
    else:
        print("Step 1: No Buttondown draft ID in manifest — skipping.")

    # 2. Git revert
    commit_hash = manifest.get("git_commit_hash")
    if commit_hash:
        print("\nStep 2: Reverting GitHub Pages commit...")
        try:
            _git_revert(commit_hash)
        except Exception as exc:
            print(f"  [Git] Failed: {exc}")
            print(f"  Revert manually: git revert {commit_hash} --no-edit && git push origin main")
    else:
        print("\nStep 2: No git commit hash in manifest — GitHub Pages not reverted.")
        print("  If a commit was made separately, revert it manually.")

    print("\nRollback complete. Data files (ledger, reports, vc-profiles) are untouched.")


if __name__ == "__main__":
    main()
