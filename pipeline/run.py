"""
Pipeline orchestrator.

Stages 1 (scraper) and 4 (reporter) are run as Claude agents via the Anthropic SDK.
Stages 2 (parser) and 3 (deduplicator) are called directly as Python functions.

Claude agent invocation approach: we use the Anthropic Python SDK with a streaming
Messages call rather than shelling out to the claude CLI, so the orchestrator has no
subprocess dependency and can surface API errors cleanly. The scraper and reporter agents
need tool access (Read, Write, WebFetch, WebSearch, Bash). We pass these via the
`tools` parameter using the standard tool_use format. Claude is prompted to use them
as it sees fit; we collect the conversation in an agentic loop until Claude stops
requesting tool calls.

Trade-off: the claude CLI subprocess approach is simpler to set up (no tool loop) but
harder to control, harder to stream output, and requires the CLI to be installed and
authenticated separately. The SDK approach is self-contained but requires implementing
the tool-use loop. We go with the SDK loop because it's production-appropriate for an
automated pipeline.

Note on tool implementations: Bash, Read, Write, WebFetch, and WebSearch are not
automatically executed by the SDK — this orchestrator only handles the *message loop*.
True tool execution in a headless Claude Code context is done by the Claude Code harness,
not here. In practice, run.py invokes the claude CLI as a subprocess for agent stages
because Claude Code's harness (not this script) is what actually owns the filesystem
and browser tools. See _run_claude_agent() for the implementation.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_REPORTS = ROOT / "data" / "reports"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(ROOT))
from pipeline import parser, deduplicator


def _read_agent_prompt(stage_name, run_date):
    path = AGENTS_DIR / f"{stage_name}.md"
    content = path.read_text()
    # Strip YAML frontmatter (everything up to and including the second ---)
    parts = content.split("---", 2)
    body = parts[2].strip() if len(parts) >= 3 else content.strip()
    return f"Today's date is {run_date}.\n\n{body}"


def _run_claude_agent(stage_name, run_date):
    """
    Invoke a Claude Code agent stage using the `claude` CLI subprocess.

    We use the CLI rather than the raw Anthropic SDK because the scraper and reporter
    agents require Claude Code-native tools (WebFetch, WebSearch, Bash, Read, Write)
    that the SDK's tool_use loop would need to re-implement. The CLI already owns those
    tool implementations and the permission model — shelling out is the right boundary.

    Requires: `claude` CLI to be on $PATH and authenticated (ANTHROPIC_API_KEY or
    `claude auth login` already completed).
    """
    prompt = _read_agent_prompt(stage_name, run_date)

    logger.info("Running Stage (%s) via claude CLI...", stage_name)
    result = subprocess.run(
        ["claude", "--model", "claude-sonnet-4-6", "-p", prompt],
        capture_output=False,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI exited with code {result.returncode} for stage {stage_name}")


def _gate_scraper(run_date):
    raw_files = list(DATA_RAW.glob(f"{run_date}_*.json"))
    if not raw_files:
        return False, "No raw files found for today's date."
    for f in raw_files:
        try:
            data = json.loads(f.read_text())
            if isinstance(data, list) and len(data) > 0:
                return True, None
            if isinstance(data, dict):
                records = data.get("records") or data.get("investments") or []
                if records:
                    return True, None
        except Exception:
            pass
    return False, f"Raw files exist but all are empty: {[f.name for f in raw_files]}"


def _gate_parser():
    path = DATA_PROCESSED / "investments.json"
    if not path.exists():
        return False, "data/processed/investments.json not found."
    try:
        data = json.loads(path.read_text())
        if data.get("record_count", 0) > 0:
            return True, None
        return False, "investments.json exists but record_count is 0."
    except Exception as e:
        return False, f"Could not read investments.json: {e}"


def _gate_deduplicator():
    path = DATA_PROCESSED / "investments_deduped.json"
    if path.exists():
        return True, None
    return False, "data/processed/investments_deduped.json not found."


def _gate_reporter(run_date):
    report_path = DATA_REPORTS / f"{run_date}_vc-report.md"
    if report_path.exists():
        return True, None
    return False, f"data/reports/{run_date}_vc-report.md not found."


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it before running the pipeline: export ANTHROPIC_API_KEY=sk-...", file=sys.stderr)
        sys.exit(1)

    ap = argparse.ArgumentParser(description="Scottish VC Tracker pipeline orchestrator")
    ap.add_argument("--date", default=None, help="Run date in YYYY-MM-DD format (default: today)")
    args = ap.parse_args()

    run_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("Pipeline starting. Run date: %s", run_date)

    # Stage 1 — Scraper (Claude agent)
    logger.info("=== Stage 1: Scraper ===")
    _run_claude_agent("scraper", run_date)
    ok, err = _gate_scraper(run_date)
    if not ok:
        print(f"GATE FAIL (Stage 1 — Scraper): {err}", file=sys.stderr)
        print("Check data/raw/errors.json for source failures.", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 1 gate passed.")

    # Stage 2 — Parser (Python)
    logger.info("=== Stage 2: Parser ===")
    try:
        parser.run(date=run_date)
    except Exception as e:
        print(f"GATE FAIL (Stage 2 — Parser): Exception during parsing: {e}", file=sys.stderr)
        sys.exit(1)
    ok, err = _gate_parser()
    if not ok:
        print(f"GATE FAIL (Stage 2 — Parser): {err}", file=sys.stderr)
        raw_files = sorted(DATA_RAW.glob(f"{run_date}_*.json"))
        print(f"Raw files consumed: {[f.name for f in raw_files]}", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 2 gate passed.")

    # Stage 3 — Deduplicator (Python)
    logger.info("=== Stage 3: Deduplicator ===")
    try:
        deduplicator.run(date=run_date)
    except Exception as e:
        print(f"GATE FAIL (Stage 3 — Deduplicator): Exception during deduplication: {e}", file=sys.stderr)
        sys.exit(1)
    ok, err = _gate_deduplicator()
    if not ok:
        print(f"GATE FAIL (Stage 3 — Deduplicator): {err}", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 3 gate passed.")

    # Stage 4 — Reporter (Claude agent)
    logger.info("=== Stage 4: Reporter ===")
    _run_claude_agent("reporter", run_date)
    ok, err = _gate_reporter(run_date)
    if not ok:
        print(f"GATE FAIL (Stage 4 — Reporter): {err}", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 4 gate passed.")

    print(f"Pipeline complete. Report: data/reports/{run_date}_vc-report.md")


if __name__ == "__main__":
    main()
