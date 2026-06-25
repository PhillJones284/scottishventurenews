"""Computes deterministic report numbers for the weekly reporter (Stage 3.5).

Pure aggregation step (no LLM) — produces every number "The Numbers" section
needs: quarter/year deal count and capital, investor rankings, stage/sector/
location mix, and the revision delta against the previous issue (computed
from a structured history file, not by an agent re-reading last week's
markdown). The reporter must not compute these figures itself; it only
narrates what this script produces.

By policy there should never be a `pending` entry in merge_candidates.json
by the time this stage runs — Stage 3's gate requires resolving any new
pending entry with Phill immediately, before proceeding to Stage 3.5. So
this script does not try to count around pending duplicates; it refuses to
run at all if it finds one (see `_assert_no_pending`). If that happens, the
fix is to resolve the duplicate with Phill (merge, fix the underlying data,
or explicitly treat the pair as separate deals), not to patch this script.

Usage:
    python pipeline/report_stats.py [--date YYYY-MM-DD]
"""
import argparse
import calendar
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
LEDGER_PATH = PROCESSED_DIR / "ledger.json"
MERGE_CANDIDATES_PATH = PROCESSED_DIR / "merge_candidates.json"
DEDUPED_PATH = PROCESSED_DIR / "investments_deduped.json"
HISTORY_PATH = PROCESSED_DIR / "report_history.json"
OUT_PATH = PROCESSED_DIR / "report_stats.json"

# How recent an announcement_date has to be (relative to the run date) to count
# as "fresh news" rather than backfill in the this-run new/backfill split.
RECENT_WINDOW_DAYS = 14


def _quarter_bounds(d: date):
    q = (d.month - 1) // 3 + 1
    start_month = 3 * (q - 1) + 1
    end_month = start_month + 2
    start = date(d.year, start_month, 1)
    end = date(d.year, end_month, calendar.monthrange(d.year, end_month)[1])
    return q, start.isoformat(), end.isoformat()


def _assert_no_pending(ledger, merge_candidates):
    """Hard gate: refuse to compute anything while a pending duplicate exists.

    By policy (see CLAUDE.md "Reviewing merge candidates"), a pending pair is
    always resolved with Phill immediately, in the same session it's found —
    there is no scenario where it's correct to compute report totals while one
    is still sitting unresolved. If this fires, Stage 3's synchronous-review
    step was skipped; the fix is to resolve the pair with Phill (merge, fix
    the underlying data, or explicitly treat it as two separate deals) and
    re-run this script, not to add counting logic that works around it.
    """
    by_id = {r["id"]: r for r in ledger}
    pending = [c for c in merge_candidates if c.get("status") == "pending"]
    if not pending:
        return
    details = []
    for c in pending:
        a, b = by_id.get(c.get("record_a")), by_id.get(c.get("record_b"))
        name = (a or b or {}).get("company_name", "unknown company")
        details.append(f"{name} ({c.get('record_a')} / {c.get('record_b')}, {c.get('match_type')})")
    raise RuntimeError(
        f"{len(pending)} pending duplicate pair(s) in merge_candidates.json — resolve with Phill "
        f"before computing report stats: {details}"
    )


def _sum_and_count(records):
    return len(records), round(sum(r.get("amount_gbp_millions") or 0 for r in records), 3)


def _investor_rankings(q_records, top_n=5):
    count, capital = defaultdict(int), defaultdict(float)
    for r in q_records:
        invs = set(r.get("investors") or [])
        if r.get("lead_investor"):
            invs.add(r["lead_investor"])
        amt = r.get("amount_gbp_millions") or 0
        for inv in invs:
            count[inv] += 1
            capital[inv] += amt
    by_count = sorted(count.items(), key=lambda kv: (-kv[1], -capital[kv[0]]))[:top_n]
    by_capital = sorted(capital.items(), key=lambda kv: -kv[1])[:top_n]
    return (
        [{"investor": k, "deal_count": v, "capital_gbp_millions": round(capital[k], 3)} for k, v in by_count],
        [{"investor": k, "capital_gbp_millions": round(v, 3), "deal_count": count[k]} for k, v in by_capital],
    )


def _breakdowns(records):
    stage, location = defaultdict(int), defaultdict(int)
    for r in records:
        stage[r.get("round_type") or "Unknown"] += 1
        location[r.get("company_location") or "Unknown"] += 1
    return dict(stage), dict(location)


def _sector_count_and_capital(records):
    """Deal count and capital deployed per sector.

    A deal with multiple `company_sectors` contributes its full amount to each
    one, so summing the capital dict across sectors over-counts the true total
    for any quarter with multi-sector deals — by design, since the point is to
    show each sector's draw on capital, not to partition a single total across
    sectors. Use `quarter_capital_gbp_millions` / `ytd_capital_gbp_millions` for
    the real total, never a sum over this breakdown.
    """
    count, capital = defaultdict(int), defaultdict(float)
    for r in records:
        amt = r.get("amount_gbp_millions") or 0
        for s in r.get("company_sectors") or []:
            count[s] += 1
            capital[s] += amt
    return dict(count), {k: round(v, 3) for k, v in capital.items()}


def _slim(r):
    return {
        "id": r.get("id"),
        "company_name": r.get("company_name"),
        "round_type": r.get("round_type"),
        "amount_gbp_millions": r.get("amount_gbp_millions"),
        "announcement_date": r.get("announcement_date"),
        "lead_investor": r.get("lead_investor"),
    }


def _this_run_split(run_date):
    """New-or-updated records from investments_deduped.json, split into genuinely
    new (announced recently) vs backfill (announced well before it surfaced)."""
    if not DEDUPED_PATH.exists():
        return {"new_count": 0, "genuinely_new_records": [], "backfill_records": [], "backfill_capital_gbp_millions": 0.0}

    deduped = json.loads(DEDUPED_PATH.read_text())
    records = deduped.get("investments", deduped) if isinstance(deduped, dict) else deduped
    new_records = [r for r in records if r.get("is_new_this_run")]

    cutoff = (run_date - timedelta(days=RECENT_WINDOW_DAYS)).isoformat()
    genuinely_new, backfill = [], []
    for r in new_records:
        ad = r.get("announcement_date")
        (genuinely_new if ad and ad >= cutoff else backfill).append(r)

    return {
        "new_count": len(new_records),
        "genuinely_new_records": [_slim(r) for r in genuinely_new],
        "backfill_records": [_slim(r) for r in backfill],
        "backfill_capital_gbp_millions": round(sum(r.get("amount_gbp_millions") or 0 for r in backfill), 3),
    }


def _load_history():
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return []


def run(date_str=None):
    run_date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_date = datetime.strptime(run_date_str, "%Y-%m-%d").date()

    ledger = json.loads(LEDGER_PATH.read_text()) if LEDGER_PATH.exists() else []
    merge_candidates = json.loads(MERGE_CANDIDATES_PATH.read_text()) if MERGE_CANDIDATES_PATH.exists() else []
    _assert_no_pending(ledger, merge_candidates)

    quarter_num, q_start, q_end = _quarter_bounds(run_date)
    q_label = f"Q{quarter_num} {run_date.year}"
    ytd_start = date(run_date.year, 1, 1).isoformat()

    q_records = [r for r in ledger if r.get("announcement_date") and q_start <= r["announcement_date"] <= q_end]
    ytd_records = [r for r in ledger if r.get("announcement_date") and ytd_start <= r["announcement_date"] <= q_end]

    q_count, q_capital = _sum_and_count(q_records)
    ytd_count, ytd_capital = _sum_and_count(ytd_records)
    by_count, by_capital = _investor_rankings(q_records)
    stage_mix, location_mix = _breakdowns(q_records)
    ytd_stage_mix, _ = _breakdowns(ytd_records)
    sector_mix, sector_capital_mix = _sector_count_and_capital(q_records)
    ytd_sector_mix, ytd_sector_capital_mix = _sector_count_and_capital(ytd_records)

    history = _load_history()
    prior_candidates = [h for h in history if h["run_date"] != run_date_str]
    prior = prior_candidates[-1] if prior_candidates else None

    revision = None
    if prior:
        same_quarter = prior["q_label"] == q_label
        revision = {
            "prior_run_date": prior["run_date"],
            "prior_quarter_label": prior["q_label"],
            "quarter_deal_count_delta": (q_count - prior["q_deal_count"]) if same_quarter else None,
            "quarter_capital_delta_gbp_millions": (round(q_capital - prior["q_capital_gbp_millions"], 3) if same_quarter else None),
            "ytd_deal_count_delta": ytd_count - prior["ytd_deal_count"],
            "ytd_capital_delta_gbp_millions": round(ytd_capital - prior["ytd_capital_gbp_millions"], 3),
        }

    stats = {
        "run_date": run_date_str,
        "quarter_label": q_label,
        "quarter_deal_count": q_count,
        "quarter_capital_gbp_millions": q_capital,
        "ytd_deal_count": ytd_count,
        "ytd_capital_gbp_millions": ytd_capital,
        "is_first_issue": prior is None,
        "revision_vs_prior_issue": revision,
        "most_active_investors_by_count": by_count,
        "most_active_investors_by_capital": by_capital,
        "stage_mix": stage_mix,
        "ytd_stage_mix": ytd_stage_mix,
        "sector_mix": sector_mix,
        "sector_capital_mix": sector_capital_mix,
        "ytd_sector_mix": ytd_sector_mix,
        "ytd_sector_capital_mix": ytd_sector_capital_mix,
        "location_mix": location_mix,
        "this_run": _this_run_split(run_date),
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(stats, indent=2))

    new_entry = {
        "run_date": run_date_str,
        "q_label": q_label,
        "q_deal_count": q_count,
        "q_capital_gbp_millions": q_capital,
        "ytd_deal_count": ytd_count,
        "ytd_capital_gbp_millions": ytd_capital,
    }
    if history and history[-1]["run_date"] == run_date_str:
        history[-1] = new_entry
    else:
        history.append(new_entry)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))

    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="Run date in YYYY-MM-DD format (default: today)")
    args = ap.parse_args()
    stats = run(date_str=args.date)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
