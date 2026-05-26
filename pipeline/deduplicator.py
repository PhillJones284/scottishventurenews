"""Stage 3: Deduplicate investment records and maintain the persistent ledger."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"

LEGAL_SUFFIXES = re.compile(
    r"\b(ltd\.?|limited|plc\.?|llp\.?|inc\.?|corp\.?|llc\.?)\s*$",
    re.IGNORECASE,
)

# Thresholds chosen to balance precision vs recall:
# 90 for definite match avoids false merges on similarly-named companies (e.g. "Acme AI" vs "Acme Analytics").
# 80 for possible match catches abbreviated names without auto-merging them.
DEFINITE_NAME_THRESHOLD = 90
POSSIBLE_NAME_THRESHOLD = 80


def _normalise_for_compare(name):
    if not name:
        return ""
    s = LEGAL_SUFFIXES.sub("", name).strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _name_similarity(a, b):
    return fuzz.token_sort_ratio(_normalise_for_compare(a), _normalise_for_compare(b))


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_apart(date_a, date_b):
    d1 = _parse_date(date_a)
    d2 = _parse_date(date_b)
    if d1 is None or d2 is None:
        return None
    return abs((d1 - d2).days)


def _investors_overlap(list_a, list_b):
    if not list_a or not list_b:
        return False
    set_a = {n.lower() for n in list_a}
    set_b = {n.lower() for n in list_b}
    return bool(set_a & set_b)


def _match_type(a, b):
    """
    Return one of: "definite", "probable", "possible", or None.
    Evaluated in priority order per spec.
    """
    name_score = _name_similarity(a["company_name"], b["company_name"])
    if name_score < POSSIBLE_NAME_THRESHOLD:
        return None

    same_round = a.get("round_type") == b.get("round_type")
    days = _days_apart(a.get("announcement_date"), b.get("announcement_date"))
    same_amount = (
        a.get("amount_gbp_millions") is not None
        and b.get("amount_gbp_millions") is not None
        and abs(a["amount_gbp_millions"] - b["amount_gbp_millions"]) < 0.01
    )
    investors_match = _investors_overlap(a.get("investors"), b.get("investors"))

    # Definite: name + round + dates within 60 days
    if name_score >= DEFINITE_NAME_THRESHOLD and same_round:
        if days is not None and days <= 60:
            return "definite"
        # Definite: name + same amount + same investors
        if same_amount and investors_match:
            return "definite"

    # Probable: name + round, but missing date(s)
    if name_score >= DEFINITE_NAME_THRESHOLD and same_round:
        if days is None:
            return "probable"

    # Probable: name + overlapping investors, dates within 90 days
    if name_score >= DEFINITE_NAME_THRESHOLD and investors_match:
        if days is not None and days <= 90:
            return "probable"
        if days is None:
            return "probable"

    # Possible: name matches but different round
    if name_score >= DEFINITE_NAME_THRESHOLD and not same_round:
        return "possible"

    # Possible: similar but not identical names (could be different companies)
    if POSSIBLE_NAME_THRESHOLD <= name_score < DEFINITE_NAME_THRESHOLD:
        return "possible"

    return None


def _merge(base, other, merge_confidence):
    """Merge `other` into `base`, filling nulls and combining sources."""
    merged = dict(base)
    for key, val in other.items():
        if key in ("source_url", "source_urls"):
            continue
        if merged.get(key) is None and val is not None:
            merged[key] = val

    # Combine source URLs
    existing_urls = set()
    if base.get("source_urls"):
        existing_urls.update(base["source_urls"])
    elif base.get("source_url"):
        existing_urls.add(base["source_url"])
    if other.get("source_urls"):
        existing_urls.update(other["source_urls"])
    elif other.get("source_url"):
        existing_urls.add(other["source_url"])

    merged["source_urls"] = sorted(existing_urls)
    merged["source_count"] = len(merged["source_urls"])
    merged["merge_confidence"] = merge_confidence
    merged["duplicate_of"] = None
    return merged


def _deduplicate_within_run(investments):
    """
    Group investments from the current run into canonical records.
    Returns (canonical_records, flagged_for_review).
    """
    clusters = []  # list of {"records": [...], "match_type": str}
    assigned = [False] * len(investments)

    for i, rec in enumerate(investments):
        if assigned[i]:
            continue
        cluster = {"records": [rec], "match_type": None}
        for j in range(i + 1, len(investments)):
            if assigned[j]:
                continue
            mt = _match_type(rec, investments[j])
            if mt in ("definite", "probable"):
                cluster["records"].append(investments[j])
                if cluster["match_type"] is None or mt == "definite":
                    cluster["match_type"] = mt
                assigned[j] = True
        assigned[i] = True
        clusters.append(cluster)

    canonical = []
    flagged = []

    # Collect possible-match flags (cross-cluster)
    for i, rec_i in enumerate(investments):
        for j in range(i + 1, len(investments)):
            rec_j = investments[j]
            mt = _match_type(rec_i, rec_j)
            if mt == "possible":
                flagged.append({
                    "reason": "possible_duplicate",
                    "records": [rec_i["id"], rec_j["id"]],
                    "note": (
                        f"Similar company names ('{rec_i['company_name']}' vs '{rec_j['company_name']}')"
                        if _name_similarity(rec_i["company_name"], rec_j["company_name"]) < DEFINITE_NAME_THRESHOLD
                        else f"Same company name, different round types ('{rec_i['round_type']}' vs '{rec_j['round_type']}')"
                    ),
                })

    for cluster in clusters:
        records = cluster["records"]
        if len(records) == 1:
            r = dict(records[0])
            r.setdefault("source_urls", [r.get("source_url", "")] if r.get("source_url") else [])
            r.setdefault("source_count", len(r["source_urls"]))
            r.setdefault("merge_confidence", None)
            r.setdefault("duplicate_of", None)
            canonical.append(r)
        else:
            # Sort by data_quality_score descending; keep best as base
            sorted_recs = sorted(records, key=lambda x: x.get("data_quality_score", 0), reverse=True)
            base = sorted_recs[0]
            base_with_meta = dict(base)
            base_with_meta["source_urls"] = (
                [base["source_url"]] if base.get("source_url") else []
            )
            merged = base_with_meta
            for other in sorted_recs[1:]:
                merged = _merge(merged, other, cluster["match_type"])
            canonical.append(merged)

    return canonical, flagged


def _match_against_ledger(record, ledger_entries):
    """
    Find the best matching ledger entry.
    Returns (ledger_entry, match_type) or (None, None).
    """
    # Exact ID match first
    for entry in ledger_entries:
        if entry["id"] == record["id"]:
            return entry, "definite"

    # Fuzzy match using same rules
    for entry in ledger_entries:
        mt = _match_type(record, entry)
        if mt in ("definite", "probable"):
            return entry, mt

    return None, None


def run(date: str = None):
    run_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with open(PROCESSED_DIR / "investments.json") as f:
        parsed = json.load(f)

    investments = parsed.get("investments", [])

    ledger_path = PROCESSED_DIR / "ledger.json"
    if ledger_path.exists():
        with open(ledger_path) as f:
            ledger = json.load(f)
        if isinstance(ledger, dict):
            ledger_entries = ledger.get("investments", ledger.get("entries", []))
        else:
            ledger_entries = ledger
    else:
        ledger_entries = []

    # Deduplicate within this run first
    canonical, flagged = _deduplicate_within_run(investments)

    new_this_run = 0
    updated_existing = 0
    output_investments = []

    for record in canonical:
        ledger_match, match_type = _match_against_ledger(record, ledger_entries)

        if ledger_match is None:
            # New record
            record["first_seen"] = run_date
            record["last_seen"] = run_date
            record["is_new_this_run"] = True
            ledger_entries.append(dict(record))
            new_this_run += 1
        else:
            # Update existing ledger entry
            first_seen = ledger_match.get("first_seen", run_date)
            ledger_match.update(record)
            ledger_match["first_seen"] = first_seen
            ledger_match["last_seen"] = run_date

            # Merge source URLs in ledger
            existing_urls = set(ledger_match.get("source_urls", []))
            existing_urls.update(record.get("source_urls", []))
            if record.get("source_url"):
                existing_urls.add(record["source_url"])
            ledger_match["source_urls"] = sorted(existing_urls)
            ledger_match["source_count"] = len(ledger_match["source_urls"])

            record["first_seen"] = first_seen
            record["last_seen"] = run_date
            record["is_new_this_run"] = False
            updated_existing += 1

        output_investments.append(record)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "stats": {
            "input_records": len(investments),
            "after_dedup": len(output_investments),
            "new_this_run": new_this_run,
            "updated_existing": updated_existing,
            "flagged_for_review": len(flagged),
        },
        "investments": output_investments,
        "flagged_for_review": flagged,
    }

    with open(PROCESSED_DIR / "investments_deduped.json", "w") as f:
        json.dump(output, f, indent=2)

    # Update ledger
    with open(ledger_path, "w") as f:
        json.dump(ledger_entries, f, indent=2)

    logger.info(
        "Deduplicator complete: %d → %d records (%d new, %d updated, %d flagged)",
        len(investments),
        len(output_investments),
        new_this_run,
        updated_existing,
        len(flagged),
    )
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(date=date_arg)
