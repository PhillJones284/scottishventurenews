"""Stage 3: Deduplicate investment records and maintain the persistent ledger.

By policy, every merge_candidates.json entry with status "merged" must carry
a merged_into pointing at the surviving record's id — otherwise a resolved
merge isn't binding and can silently resurface as a fresh duplicate (see
resolved_merges below). This script refuses to finish writing output while
any "merged" entry is missing it (see _assert_no_missing_merged_into); the
fix is to set merged_into directly in merge_candidates.json, not to patch
this script to tolerate the gap.
"""

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

# Geographic qualifiers that sources inconsistently append/omit (e.g. "Xburo UK"
# vs "Xburo") — stripped the same way legal suffixes are, since on short company
# names a single extra token like this drags token_sort_ratio below the possible
# threshold and the pair goes unflagged entirely rather than just unmerged.
GEO_QUALIFIERS = re.compile(
    r"\b(uk|united kingdom)\b",
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
    s = GEO_QUALIFIERS.sub("", s).strip()
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

    # Definite: name + same amount + dates within 60 days, regardless of round_type.
    # Sources are frequently inconsistent about stage labels for the same deal
    # (e.g. "Series B" vs "Growth" vs unstated) — an exact amount match plus a
    # tight date window is stronger evidence of a single deal than an exact
    # round_type string match, which round_type alone is too unreliable to gate on.
    if name_score >= DEFINITE_NAME_THRESHOLD and same_amount:
        if days is not None and days <= 60:
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


def _union_sectors(a, b):
    """Return sorted union of two company_sectors lists, handling legacy string field."""
    def _to_set(rec):
        v = rec.get("company_sectors")
        if isinstance(v, list):
            return set(v)
        # legacy single-string field
        v = rec.get("company_sector")
        return {v} if v else set()
    return sorted(_to_set(a) | _to_set(b)) or ["Other"]


def _is_empty(v):
    """Treat None, empty string, and empty list as 'no data' for merge gap-filling."""
    return v is None or v == "" or v == []


def _merge(base, other, merge_confidence):
    """Merge `other` into `base`: fill gaps in either direction so the result is the
    most complete record possible. A non-empty value already in `base` is never
    overwritten by a value from `other` — on conflicting non-empty values, the caller
    passes the higher-data_quality_score record as `base` so that one wins."""
    merged = dict(base)
    for key, val in other.items():
        if key in ("source_url", "source_urls", "company_sectors"):
            continue
        if _is_empty(merged.get(key)) and not _is_empty(val):
            merged[key] = val

    merged["company_sectors"] = _union_sectors(base, other)

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


def _duplicate_note(a, b, match_type):
    """Human-readable reason a pair was matched at this confidence level."""
    if _name_similarity(a["company_name"], b["company_name"]) < DEFINITE_NAME_THRESHOLD:
        return f"Similar company names ('{a['company_name']}' vs '{b['company_name']}')"
    if a.get("round_type") != b.get("round_type"):
        return f"Same company name, different round types ('{a['round_type']}' vs '{b['round_type']}')"
    if _days_apart(a.get("announcement_date"), b.get("announcement_date")) is None:
        return "Same company and round type, but the announcement date is missing on at least one record"
    return "Same company name, overlapping investors, announcement dates within range"


def _deduplicate_within_run(investments):
    """
    Group investments from the current run into canonical records.

    Only "definite" matches are auto-merged. "probable" and "possible" matches are
    never auto-merged — they're returned in `flagged` as merge candidates for manual
    review instead, per the project's conservative dedup policy (definite duplicates
    merge automatically; anything less certain goes to Phill for approval, not a
    silent merge or a silent drop).

    Returns (canonical_records, flagged_for_review).
    """
    clusters = []  # list of {"records": [...]}, definite-only
    assigned = [False] * len(investments)

    for i, rec in enumerate(investments):
        if assigned[i]:
            continue
        cluster = {"records": [rec]}
        for j in range(i + 1, len(investments)):
            if assigned[j]:
                continue
            mt = _match_type(rec, investments[j])
            if mt == "definite":
                cluster["records"].append(investments[j])
                assigned[j] = True
        assigned[i] = True
        clusters.append(cluster)

    canonical = []
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
            base_with_meta = dict(sorted_recs[0])
            base_with_meta["source_urls"] = (
                [sorted_recs[0]["source_url"]] if sorted_recs[0].get("source_url") else []
            )
            merged = base_with_meta
            for other in sorted_recs[1:]:
                merged = _merge(merged, other, "definite")
            canonical.append(merged)

    # Flag any remaining probable/possible pairs among the final (unmerged) records
    flagged = []
    for i, rec_i in enumerate(canonical):
        for j in range(i + 1, len(canonical)):
            rec_j = canonical[j]
            mt = _match_type(rec_i, rec_j)
            if mt in ("probable", "possible"):
                flagged.append({
                    "reason": f"{mt}_duplicate",
                    "records": [rec_i["id"], rec_j["id"]],
                    "note": _duplicate_note(rec_i, rec_j, mt),
                })

    return canonical, flagged


def _match_against_ledger(record, ledger_entries):
    """
    Find the best matching ledger entry, at any confidence tier.

    Returns (ledger_entry, match_type) where match_type is "definite", "probable",
    "possible", or (None, None) if nothing matches even at the "possible" threshold.

    Only "definite" should be auto-merged by the caller. "probable" and "possible"
    are returned so the caller can stage a merge candidate for manual review —
    never silently merged, and never silently dropped (the latter was the root
    cause of the JET Connectivity duplicate: a "possible" match used to be treated
    as no match at all).
    """
    # Exact ID match is always definite
    for entry in ledger_entries:
        if entry["id"] == record["id"]:
            return entry, "definite"

    priority = {"definite": 3, "probable": 2, "possible": 1}
    best_entry, best_type = None, None
    for entry in ledger_entries:
        mt = _match_type(record, entry)
        if mt and (best_type is None or priority[mt] > priority[best_type]):
            best_entry, best_type = entry, mt
            if mt == "definite":
                break  # can't do better than definite

    return best_entry, best_type


def _assert_no_missing_merged_into(merge_candidates):
    """Hard gate: refuse to finish while a 'merged' entry has no merged_into.

    Without merged_into, a resolved merge can't be binding (see the comment on
    resolved_merges above) — if the pair resurfaces on a later run (e.g. a
    source article gets re-scraped), it silently re-adds as a fresh standalone
    duplicate instead of auto-merging into the recorded survivor. That's
    exactly the 2026-08-12 Wordsmith AI/Esk bug this field exists to prevent,
    so a merge resolved without it is a policy violation, not just a loose
    end — this used to be a warning (easy to miss in run output) and let 8
    entries accumulate silently until an unrelated conversation surfaced them
    on 2026-08-17. The fix is to set merged_into directly in
    merge_candidates.json (the id of the record that survived) and re-run —
    not to relax this check or add logic that works around a missing value.
    """
    missing = [
        f"{c['record_a']} | {c['record_b']}"
        for c in merge_candidates
        if c.get("status") == "merged" and not c.get("merged_into")
    ]
    if not missing:
        return
    raise RuntimeError(
        f"{len(missing)} 'merged' merge_candidates entries have no merged_into, so they "
        f"won't be binding if the pair resurfaces — set merged_into on each (the id of the "
        f"record that survived the merge) directly in merge_candidates.json, then re-run: "
        f"{missing}"
    )


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

    # Deduplicate within this run first (definite-only auto-merge; probable/possible flagged)
    canonical, flagged = _deduplicate_within_run(investments)

    # Persistent merge-candidate staging — survives across runs until Phill resolves it
    merge_candidates_path = PROCESSED_DIR / "merge_candidates.json"
    if merge_candidates_path.exists():
        with open(merge_candidates_path) as f:
            merge_candidates = json.load(f)
    else:
        merge_candidates = []
    staged_pairs = {frozenset((c["record_a"], c["record_b"])) for c in merge_candidates}

    # Pairs already resolved as "merged" in a past run, keyed by the pair and pointing
    # at the id that survived. This makes that resolution binding: if the same pair
    # resurfaces (e.g. a source article gets re-scraped and reproduces the same
    # deterministic id), it must not silently become a fresh standalone duplicate.
    # staged_pairs (above) only stops the pair from being re-flagged for review — it
    # does nothing to stop the record itself being re-added to the ledger, which is
    # exactly how the 2026-08-12 Wordsmith AI and Esk duplicates happened. Requires
    # merged_into on the historical entry; entries without it (see the warning near
    # the end of this function) can't participate and fall back to normal handling.
    resolved_merges = {
        frozenset((c["record_a"], c["record_b"])): c["merged_into"]
        for c in merge_candidates
        if c.get("status") == "merged" and c.get("merged_into")
    }

    def _stage_merge_candidate(match_type, record_a, record_b, note, scope):
        pair = frozenset((record_a, record_b))
        if pair in staged_pairs:
            return
        staged_pairs.add(pair)
        merge_candidates.append({
            "match_type": match_type,
            "scope": scope,
            "record_a": record_a,
            "record_b": record_b,
            "note": note,
            "flagged_date": run_date,
            "status": "pending",
        })

    new_this_run = 0
    updated_existing = 0
    output_investments = []

    # Run-local id -> surviving id, populated below whenever a record's id changes
    # because it definite-merged into a ledger entry (see the "definite" branch).
    # Needed because `flagged` (within-run probable/possible pairs) is computed
    # before ledger reconciliation and still refers to run-local ids — if we staged
    # those directly, a pair could end up referencing an id that no longer exists
    # anywhere in investments_deduped.json or ledger.json once its record has been
    # absorbed into a ledger entry under the ledger's id.
    id_remap = {}

    for record in canonical:
        ledger_match, match_type = _match_against_ledger(record, ledger_entries)

        if match_type in ("probable", "possible") and ledger_match is not None:
            survivor_id = resolved_merges.get(frozenset((record["id"], ledger_match["id"])))
            if survivor_id and survivor_id == ledger_match["id"]:
                # This exact pair was already resolved as a merge, and the survivor
                # it was merged into is still the current best match — binding.
                # Auto-merge via the "definite" path below instead of re-flagging
                # (already prevented by staged_pairs) or adding a fresh duplicate.
                match_type = "definite"

        if match_type == "definite":
            run_local_id = record["id"]

            # Merge into the existing ledger entry — fill gaps in either direction
            # (see _merge()) rather than blindly taking the newer extraction's fields,
            # which previously let a thin/unsourced re-extraction (e.g. a Crunchbase
            # stub with no named investor) silently overwrite a well-sourced record.
            # The higher-data_quality_score record wins on genuine field conflicts,
            # matching the convention already used in _deduplicate_within_run.
            first_seen = ledger_match.get("first_seen", run_date)
            if record.get("data_quality_score", 0) > ledger_match.get("data_quality_score", 0):
                merged = _merge(record, ledger_match, "definite")
            else:
                merged = _merge(ledger_match, record, "definite")
            merged["first_seen"] = first_seen
            merged["last_seen"] = run_date
            merged["is_new_this_run"] = False
            merged.pop("company_sector", None)

            # Mutate in place so ledger_entries (written back to ledger.json below)
            # reflects the merge — ledger_match is the same object held in that list.
            ledger_match.clear()
            ledger_match.update(merged)

            # Read the surviving id AFTER the merge — it depends on which record
            # won as merge base (_merge keeps `base`'s id), so it isn't knowable
            # up front.
            id_remap[run_local_id] = ledger_match["id"]

            updated_existing += 1
            output_investments.append(ledger_match)
        else:
            # No match, or only probable/possible — never auto-merge below "definite".
            # Add as its own ledger entry; a probable/possible match gets staged for review
            # rather than silently merged or silently dropped (the latter was the JET
            # Connectivity bug — a "possible" match used to be treated as no match at all).
            record["first_seen"] = run_date
            record["last_seen"] = run_date
            record["is_new_this_run"] = True
            ledger_entries.append(dict(record))
            new_this_run += 1

            if match_type in ("probable", "possible"):
                _stage_merge_candidate(
                    match_type,
                    record["id"],
                    ledger_match["id"],
                    _duplicate_note(record, ledger_match, match_type),
                    "against_ledger",
                )

            output_investments.append(record)

    # Stage within-run flagged pairs only now, after ledger reconciliation above —
    # remap each run-local id through id_remap to the id it actually survived under.
    # Staging these earlier (before reconciliation) is the root cause of the
    # 2026-08-12 dangling-id bug: a run record that definite-merged into a ledger
    # entry keeps the ledger entry's id, not its own, so a pair staged beforehand
    # could point at an id that no longer exists anywhere in investments_deduped.json
    # or ledger.json.
    for f in flagged:
        a_id, b_id = f["records"]
        a_id = id_remap.get(a_id, a_id)
        b_id = id_remap.get(b_id, b_id)
        f["records"] = [a_id, b_id]
        if a_id == b_id:
            # Both sides of the pair merged into the same ledger entry — not a
            # duplicate of itself, so there's nothing left to review.
            continue
        _stage_merge_candidate(f["reason"].replace("_duplicate", ""), a_id, b_id, f["note"], "within_run")

    with open(merge_candidates_path, "w") as f:
        json.dump(merge_candidates, f, indent=2)

    pending_candidates = [c for c in merge_candidates if c["status"] == "pending"]

    _assert_no_missing_merged_into(merge_candidates)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "stats": {
            "input_records": len(investments),
            "after_dedup": len(output_investments),
            "new_this_run": new_this_run,
            "updated_existing": updated_existing,
            "flagged_for_review": len(flagged),
            "merge_candidates_pending": len(pending_candidates),
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
        "Deduplicator complete: %d → %d records (%d new, %d updated, %d flagged, %d merge candidates pending)",
        len(investments),
        len(output_investments),
        new_this_run,
        updated_existing,
        len(flagged),
        len(pending_candidates),
    )
    return output


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    run(date=ap.parse_args().date)
