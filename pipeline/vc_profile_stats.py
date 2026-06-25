"""Computes historical per-VC stats from the ledger for the VC profiler agent.

This is a pure aggregation step (no LLM) — it produces the structured numbers
a profile narrative is built from. Output is JSON on stdout.

Usage:
    python pipeline/vc_profile_stats.py "Octopus Ventures" ["Par Equity" ...]
    python pipeline/vc_profile_stats.py --all
    python pipeline/vc_profile_stats.py --active-in data/processed/investments_deduped.json
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

LEDGER_PATH = Path("data/processed/ledger.json")
KNOWN_VCS_PATH = Path("config/known_vcs.json")
PROCESSED_DIR = Path("data/processed")


def _load_known_vcs():
    data = json.loads(KNOWN_VCS_PATH.read_text())
    return {v["canonical_name"]: v for v in data["known_vcs"]}


def _record_investor_names(record):
    names = set(record.get("investors") or [])
    if record.get("lead_investor"):
        names.add(record["lead_investor"])
    return names


def _matches(record, canonical_name, aliases):
    return bool({canonical_name, *aliases} & _record_investor_names(record))


def compute_stats(canonical_name, ledger, known_vc):
    aliases = known_vc.get("aliases", []) if known_vc else []
    deals = [r for r in ledger if _matches(r, canonical_name, aliases)]
    deals.sort(key=lambda r: r.get("announcement_date") or "", reverse=True)

    stage_counts, sector_counts, geo_counts = {}, {}, {}
    for d in deals:
        stage = d.get("round_type") or "Unknown"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        for s in d.get("company_sectors") or []:
            sector_counts[s] = sector_counts.get(s, 0) + 1
        loc = d.get("company_location") or "Unknown"
        geo_counts[loc] = geo_counts.get(loc, 0) + 1

    dates = [d.get("announcement_date") for d in deals if d.get("announcement_date")]

    today = date.today()
    six_mo_ago = (today - timedelta(days=182)).isoformat()
    twelve_mo_ago = (today - timedelta(days=365)).isoformat()
    trailing_6mo = sum(1 for d in dates if d >= six_mo_ago)
    prior_6mo = sum(1 for d in dates if twelve_mo_ago <= d < six_mo_ago)

    ytd_start = date(today.year, 1, 1).isoformat()
    ytd_deals = [d for d in deals if d.get("announcement_date") and d["announcement_date"] >= ytd_start]
    ytd_deal_count = len(ytd_deals)
    ytd_capital_gbp_millions = round(sum(d.get("amount_gbp_millions") or 0 for d in ytd_deals), 2)

    return {
        "canonical_name": canonical_name,
        "hq": known_vc.get("hq") if known_vc else None,
        "total_deals": len(deals),
        "total_capital_gbp_millions": round(sum(d.get("amount_gbp_millions") or 0 for d in deals), 2),
        "stage_breakdown": stage_counts,
        "sector_breakdown": sector_counts,
        "geo_breakdown": geo_counts,
        "first_deal_date": min(dates) if dates else None,
        "most_recent_deal_date": max(dates) if dates else None,
        "trailing_6mo_deal_count": trailing_6mo,
        "prior_6mo_deal_count": prior_6mo,
        "ytd_deal_count": ytd_deal_count,
        "ytd_capital_gbp_millions": ytd_capital_gbp_millions,
        "deals": [
            {
                "id": d["id"],
                "company_name": d["company_name"],
                "round_type": d.get("round_type"),
                "amount_gbp_millions": d.get("amount_gbp_millions"),
                "announcement_date": d.get("announcement_date"),
                "lead_investor": d.get("lead_investor"),
                "confidence": d.get("confidence"),
            }
            for d in deals
        ],
    }


def _resolve_active_names(deduped_path, known_vcs):
    deduped = json.loads(Path(deduped_path).read_text())
    records = deduped.get("investments", deduped) if isinstance(deduped, dict) else deduped
    active_names = set()
    for r in records:
        active_names |= _record_investor_names(r)

    alias_to_canonical = {}
    for canonical, info in known_vcs.items():
        for a in info.get("aliases", []):
            alias_to_canonical[a] = canonical

    targets = set()
    unknown = set()
    for name in active_names:
        if name in known_vcs:
            targets.add(name)
        elif name in alias_to_canonical:
            targets.add(alias_to_canonical[name])
        else:
            unknown.add(name)
    return sorted(targets), sorted(unknown)


def run(deduped_path=None, vc_names=None, all_vcs=False):
    """Compute stats and write them to data/processed/vc_stats.json.

    Used by the pipeline orchestrator (Stage 5, scoped to this run's active VCs
    via `deduped_path`) and by manual on-demand refreshes (`vc_names` or `all_vcs`).
    Returns (results, unknown_names).
    """
    ledger = json.loads(LEDGER_PATH.read_text())
    known_vcs = _load_known_vcs()
    unknown_names = []

    if deduped_path:
        names_to_compute, unknown_names = _resolve_active_names(deduped_path, known_vcs)
    elif all_vcs:
        names_to_compute = sorted(known_vcs.keys())
    else:
        names_to_compute = vc_names or []

    results = [compute_stats(name, ledger, known_vcs.get(name)) for name in names_to_compute]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "vc_stats.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    return results, unknown_names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vc_names", nargs="*", help="Canonical VC name(s) to compute stats for")
    parser.add_argument("--all", action="store_true", help="Compute stats for every VC in known_vcs.json")
    parser.add_argument("--active-in", help="Path to an investments_deduped.json file; compute stats only for VCs appearing in it")
    args = parser.parse_args()

    results, unknown_names = run(deduped_path=args.active_in, vc_names=args.vc_names, all_vcs=args.all)

    if unknown_names:
        print(f"NOTE: investors active this run but not in known_vcs.json (no profile generated): {unknown_names}", file=sys.stderr)

    json.dump(results, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
