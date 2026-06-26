"""
Pipeline orchestrator.

Stages 1 (scraper), 4 (reporter), and the narrative half of 5 (vc-profiler) are run as
Claude agents via the Anthropic SDK. Stages 2 (parser), 3 (deduplicator), 3.5
(report_stats), and the stats half of 5 (vc_profile_stats) are called directly as
Python functions.

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
from pipeline import fetcher, parser, deduplicator, report_stats, chart_generator, vc_profile_stats, deal_table_generator

DOCS_VC_PROFILES = ROOT / "docs" / "vc-profiles"
DATA_REPORTS_CHARTS = DATA_REPORTS / "charts"


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


def _gate_fetcher(run_date):
    path = DATA_RAW / f"{run_date}_candidates.json"
    if path.exists():
        return True, None
    return False, f"data/raw/{run_date}_candidates.json not found."


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


def _gate_report_stats():
    path = DATA_PROCESSED / "report_stats.json"
    if path.exists():
        return True, None
    return False, "data/processed/report_stats.json not found."


def _gate_chart_generator(run_date):
    trend_path = DATA_REPORTS_CHARTS / f"{run_date}_trend.png"
    stage_path = DATA_REPORTS_CHARTS / f"{run_date}_stage.png"
    sector_path = DATA_REPORTS_CHARTS / f"{run_date}_sector.png"
    missing = [p.name for p in (trend_path, stage_path, sector_path) if not p.exists()]
    if missing:
        return False, f"Missing chart(s): {missing}"
    return True, None


def _gate_reporter(run_date):
    report_path = DATA_REPORTS / f"{run_date}_vc-report.md"
    if report_path.exists():
        return True, None
    return False, f"data/reports/{run_date}_vc-report.md not found."


def _slugify(name):
    import re
    s = name.lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _gate_profiler(run_date, expected_names):
    stale = []
    for name in expected_names:
        path = DOCS_VC_PROFILES / f"{_slugify(name)}.md"
        if not path.exists():
            stale.append(name)
            continue
        if f"last_updated: {run_date}" not in path.read_text():
            stale.append(name)
    if stale:
        return False, f"Profiles not refreshed for: {stale}"
    return True, None


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

    # Stage 1a — Fetcher (Python)
    logger.info("=== Stage 1a: Fetcher ===")
    try:
        fetch_result = fetcher.run(date=run_date)
    except Exception as e:
        fetch_result = {"candidates": 0, "errors": 1, "fallback_needed": True}
        logger.warning("Fetcher raised an exception: %s — scraper will use fallback mode", e)
    ok, err = _gate_fetcher(run_date)
    if not ok:
        logger.warning("Stage 1a gate: %s — scraper will use fallback mode", err)
    else:
        logger.info("Stage 1a gate passed. Candidates: %d", fetch_result.get("candidates", 0))

    # Stage 1b — Scraper (Claude agent)
    logger.info("=== Stage 1b: Scraper ===")
    _run_claude_agent("scraper", run_date)
    ok, err = _gate_scraper(run_date)
    if not ok:
        print(f"GATE FAIL (Stage 1b — Scraper): {err}", file=sys.stderr)
        print("Check data/raw/errors.json for source failures.", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 1b gate passed.")

    fetch_log_path = DATA_RAW / f"{run_date}_fetch_log.json"
    if fetch_log_path.exists():
        fetch_log = json.loads(fetch_log_path.read_text())
        issues = [
            e for e in fetch_log
            if (e.get("items_found", 0) > 0 and e.get("candidates_added", 0) == 0)
            or e.get("text_extract_failures", 0) > 0
        ]
        if issues:
            logger.warning(
                "Fetch log has %d source(s) with filter or extraction issues: %s",
                len(issues),
                [i["source_slug"] for i in issues],
            )

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
    merge_candidates_before = []
    merge_candidates_path = DATA_PROCESSED / "merge_candidates.json"
    if merge_candidates_path.exists():
        merge_candidates_before = json.loads(merge_candidates_path.read_text())
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

    # This script runs unattended (no human present to ask) — unlike an interactive
    # session, it cannot pause for Phill to resolve a new duplicate. The best it can
    # do is make new pending entries impossible to miss in the log, since CLAUDE.md's
    # synchronous-review policy still applies the moment Phill is next at the keyboard.
    if merge_candidates_path.exists():
        merge_candidates_after = json.loads(merge_candidates_path.read_text())
        new_pending = [
            c for c in merge_candidates_after
            if c.get("status") == "pending" and c not in merge_candidates_before
        ]
        if new_pending:
            logger.warning(
                "%d new pending duplicate pair(s) staged this run — resolve with Phill at the "
                "start of the next interactive session, before anything else: %s",
                len(new_pending),
                [(c["record_a"], c["record_b"]) for c in new_pending],
            )

    # Stage 3.5 — Report Stats (Python)
    logger.info("=== Stage 3.5: Report Stats ===")
    try:
        report_stats.run(date_str=run_date)
    except Exception as e:
        print(f"GATE FAIL (Stage 3.5 — Report Stats): Exception during stats computation: {e}", file=sys.stderr)
        sys.exit(1)
    ok, err = _gate_report_stats()
    if not ok:
        print(f"GATE FAIL (Stage 3.5 — Report Stats): {err}", file=sys.stderr)
        print("Do not let the reporter fall back to computing totals from the ledger itself.", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 3.5 gate passed.")

    # Stage 3.6 — Chart Generator (Python)
    logger.info("=== Stage 3.6: Chart Generator ===")
    try:
        chart_generator.run(date_str=run_date)
    except Exception as e:
        print(f"GATE FAIL (Stage 3.6 — Chart Generator): Exception during chart generation: {e}", file=sys.stderr)
        sys.exit(1)
    ok, err = _gate_chart_generator(run_date)
    if not ok:
        print(f"GATE FAIL (Stage 3.6 — Chart Generator): {err}", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 3.6 gate passed.")

    # Stage 4 — Reporter (Claude agent)
    logger.info("=== Stage 4: Reporter ===")
    _run_claude_agent("reporter", run_date)
    ok, err = _gate_reporter(run_date)
    if not ok:
        print(f"GATE FAIL (Stage 4 — Reporter): {err}", file=sys.stderr)
        sys.exit(1)
    logger.info("Stage 4 gate passed.")

    # Stage 5 — VC Profiler (Python stats + Claude agent)
    logger.info("=== Stage 5: VC Profiler ===")
    deduped_path = DATA_PROCESSED / "investments_deduped.json"
    results, unknown_names = vc_profile_stats.run(deduped_path=str(deduped_path))
    if unknown_names:
        logger.info("Investors active this run but not in known_vcs.json (no profile generated): %s", unknown_names)
    if results:
        _run_claude_agent("vc-profiler", run_date)
        ok, err = _gate_profiler(run_date, [r["canonical_name"] for r in results])
        if not ok:
            logger.warning("Stage 5 gate (soft): %s — profiles are reference data, not blocking the run.", err)
        else:
            logger.info("Stage 5 gate passed.")
    else:
        logger.info("No known VCs active this run — nothing to refresh.")

    # Stage 6 — Deal Table Generator (Python)
    logger.info("=== Stage 6: Deal Table Generator ===")
    try:
        deal_table_generator.run(date_str=run_date)
    except Exception as e:
        logger.warning("Stage 6 (Deal Table Generator) failed: %s — non-blocking, report still complete.", e)
    else:
        logger.info("Stage 6 complete. Static table: data/reports/deals.html")

    print(f"Pipeline complete. Report: data/reports/{run_date}_vc-report.md")


if __name__ == "__main__":
    main()
