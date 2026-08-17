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

from vc_names import SKIP_INVESTORS, load_alias_map, resolve_name

LEDGER_PATH = Path("data/processed/ledger.json")
KNOWN_VCS_PATH = Path("config/known_vcs.json")
PROCESSED_DIR = Path("data/processed")

# Alias map is loaded once and cached, not per-record/per-VC — compute_stats
# is called in a loop over every known VC across the whole ledger.
_ALIAS_MAP_CACHE = None


def _get_alias_map():
    global _ALIAS_MAP_CACHE
    if _ALIAS_MAP_CACHE is None:
        _ALIAS_MAP_CACHE = load_alias_map()
    return _ALIAS_MAP_CACHE


def _load_known_vcs():
    data = json.loads(KNOWN_VCS_PATH.read_text())
    return {v["canonical_name"]: v for v in data["known_vcs"]}


def _record_investor_names(record):
    names = set(record.get("investors") or [])
    if record.get("lead_investor"):
        names.add(record["lead_investor"])
    return names


def _matches(record, canonical_name, alias_map):
    resolved = {resolve_name(n, alias_map) for n in _record_investor_names(record)}
    return canonical_name in resolved


def compute_stats(canonical_name, ledger, known_vc, alias_map=None):
    if alias_map is None:
        alias_map = _get_alias_map()
    deals = [r for r in ledger if _matches(r, canonical_name, alias_map)]
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


def _resolve_active_names(deduped_path, known_vcs, alias_map=None):
    if alias_map is None:
        alias_map = _get_alias_map()
    deduped = json.loads(Path(deduped_path).read_text())
    records = deduped.get("investments", deduped) if isinstance(deduped, dict) else deduped
    active_names = set()
    for r in records:
        active_names |= _record_investor_names(r)

    targets = set()
    unknown = set()
    for name in active_names:
        canonical = resolve_name(name, alias_map)
        if canonical in known_vcs:
            targets.add(canonical)
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
    alias_map = _get_alias_map()
    unknown_names = []

    if deduped_path:
        names_to_compute, unknown_names = _resolve_active_names(deduped_path, known_vcs, alias_map=alias_map)
    elif all_vcs:
        names_to_compute = sorted(known_vcs.keys())
    else:
        names_to_compute = vc_names or []

    results = [compute_stats(name, ledger, known_vcs.get(name), alias_map=alias_map) for name in names_to_compute]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "vc_stats.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    return results, unknown_names


def audit():
    """Print a human-readable audit of investor-name resolution and return
    True if it passes, False if it finds a real problem.

    (a) Unresolved investor names: every distinct raw ledger investor string
        that resolves to no known VC. INFO only — roughly 20 of these are
        expected (non-VC funders, personal names, generic descriptors like
        "angel investors") and are not a failure on their own.
    (b) Cross-checker consistency: for every canonical VC, compute_stats()'s
        deal count must equal investor_page_generator.aggregate()'s deal
        count. This is the actual regression check — it's precisely the
        invariant that broke (three divergent matching rules) and the reason
        this module exists. Any mismatch is a hard failure.
    """
    ledger = json.loads(LEDGER_PATH.read_text())
    known_vcs = _load_known_vcs()
    alias_map = _get_alias_map()

    # --- (a) Unresolved investor names ---
    unresolved: dict = {}
    for r in ledger:
        for raw in _record_investor_names(r):
            if not raw or raw.strip().lower() in SKIP_INVESTORS:
                continue
            if resolve_name(raw, alias_map) not in known_vcs:
                unresolved.setdefault(raw, []).append(r["id"])

    print("=== (a) Unresolved investor names (INFO — expected for non-VC funders, personal names, etc.) ===")
    if unresolved:
        for raw in sorted(unresolved):
            ids = unresolved[raw]
            print(f"  {raw!r}: {len(ids)} deal(s) — {ids}")
    else:
        print("  none")
    print(f"  Total distinct unresolved names: {len(unresolved)}")

    # --- (b) Cross-checker consistency: compute_stats() vs investor_page_generator.aggregate() ---
    #
    # Comparability note: compute_stats() matches on investors UNION
    # lead_investor (via _record_investor_names), while aggregate() matches on
    # `investors` only and additionally drops SKIP_INVESTORS entries before
    # resolving. These two differences are real and are not papered over here
    # — they only produce identical counts because, in the current ledger:
    #   (1) lead_investor is always already a member of `investors` (verified:
    #       0 exceptions across all records), so unioning it in adds nothing
    #       new to the matched set; and
    #   (2) no SKIP_INVESTORS string resolves to a canonical VC — they're
    #       descriptive text / personal names, not aliases in known_vcs.json
    #       — so dropping them before resolution never changes a VC's count.
    # If either precondition stops holding for future ledger data (e.g. a
    # lead_investor recorded without also appearing in `investors`), this
    # check would start reporting real mismatches rather than silently
    # tolerating drift — which is the intended behaviour, not a gap to fix.
    import investor_page_generator  # lazy: pulls in webgen.shell, not needed for normal runs

    agg_stats = investor_page_generator.aggregate(ledger, known_vcs, alias_map)

    failures = []
    for canonical in sorted(known_vcs):
        cs = compute_stats(canonical, ledger, known_vcs[canonical], alias_map=alias_map)
        cs_ids = {d["id"] for d in cs["deals"]}
        agg = agg_stats.get(canonical)
        agg_count = agg["deal_count"] if agg else 0
        if cs["total_deals"] != agg_count:
            # Diagnostic only: recompute aggregate-side deal ids directly,
            # mirroring aggregate()'s own investors-only + SKIP_INVESTORS
            # logic, so the mismatch can be reported concretely by deal id.
            agg_ids = set()
            for r in ledger:
                for raw in (r.get("investors") or []):
                    if not raw or raw.strip().lower() in SKIP_INVESTORS:
                        continue
                    if resolve_name(raw, alias_map) == canonical:
                        agg_ids.add(r["id"])
                        break
            failures.append((canonical, cs["total_deals"], agg_count, cs_ids - agg_ids, agg_ids - cs_ids))

    print()
    print("=== (b) Cross-checker consistency: compute_stats() vs investor_page_generator.aggregate() ===")
    if failures:
        for canonical, cs_count, agg_count, only_cs, only_agg in failures:
            print(f"  FAIL {canonical}: compute_stats={cs_count} aggregate={agg_count}")
            if only_cs:
                print(f"    only in compute_stats: {sorted(only_cs)}")
            if only_agg:
                print(f"    only in aggregate: {sorted(only_agg)}")
    else:
        print(f"  PASS — all {len(known_vcs)} known VCs agree between compute_stats() and aggregate()")

    return len(failures) == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vc_names", nargs="*", help="Canonical VC name(s) to compute stats for")
    parser.add_argument("--all", action="store_true", help="Compute stats for every VC in known_vcs.json")
    parser.add_argument("--active-in", help="Path to an investments_deduped.json file; compute stats only for VCs appearing in it")
    parser.add_argument("--audit", action="store_true", help="Audit investor-name resolution across the whole ledger; exits non-zero on a real problem")
    args = parser.parse_args()

    if args.audit:
        ok = audit()
        sys.exit(0 if ok else 1)

    results, unknown_names = run(deduped_path=args.active_in, vc_names=args.vc_names, all_vcs=args.all)

    if unknown_names:
        print(f"NOTE: investors active this run but not in known_vcs.json (no profile generated): {unknown_names}", file=sys.stderr)

    json.dump(results, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
