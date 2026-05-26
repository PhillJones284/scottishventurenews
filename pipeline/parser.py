"""Stage 2: Normalise raw scraped records into a clean investment dataset."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CONFIG_DIR = ROOT / "config"

LOCATION_KEYWORDS = {
    "Edinburgh": ["edinburgh"],
    "Glasgow": ["glasgow"],
    "Aberdeen": ["aberdeen"],
    "Dundee": ["dundee"],
    "Inverness": ["inverness"],
    "St Andrews": ["st andrews", "saint andrews"],
}

ROUND_NORMALISATION = {
    "pre-seed": "Pre-Seed",
    "preseed": "Pre-Seed",
    "pre seed": "Pre-Seed",
    "seed": "Seed",
    "series a": "Series A",
    "series-a": "Series A",
    "series b": "Series B",
    "series-b": "Series B",
    "series c": "Series C+",
    "series-c": "Series C+",
    "series c+": "Series C+",
    "series d": "Series C+",
    "series e": "Series C+",
    "series f": "Series C+",
    "growth": "Growth",
    "growth equity": "Growth",
    "bridge": "Bridge",
    "convertible": "Bridge",
    "extension": "Bridge",
}

# Patterns that suggest a grant rather than a VC investment
GRANT_PATTERNS = [
    r"\bgrant\b",
    r"\baward\b",
    r"\bsubsidy\b",
    r"\bfunding award\b",
    r"\binnovate uk\b",
    r"\bhorizon\b",
]

LEGAL_SUFFIXES = re.compile(
    r"\b(ltd\.?|limited|plc\.?|llp\.?|inc\.?|corp\.?|llc\.?)\s*$",
    re.IGNORECASE,
)

# Matches amounts like £4.2m, $10m, €5 million, £1.5bn
AMOUNT_RE = re.compile(
    r"([£$€]?)\s*([\d,]+(?:\.\d+)?)\s*(m|million|bn|billion|k|thousand)?",
    re.IGNORECASE,
)

CURRENCY_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR"}

# Matches a YYYY-MM-DD date anywhere in a string
DATE_IN_STRING_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Matches /YYYY/MM/DD/ or /YYYY/MM/ in URLs
DATE_IN_URL_RE = re.compile(r"/(\d{4})/(\d{1,2})(?:/(\d{1,2}))?")


def _load_config():
    with open(CONFIG_DIR / "sectors.json") as f:
        sectors_data = json.load(f)
    with open(CONFIG_DIR / "fx_rates.json") as f:
        fx_data = json.load(f)
    with open(CONFIG_DIR / "known_vcs.json") as f:
        vcs_data = json.load(f)
    return sectors_data["sectors"], fx_data["rates"], vcs_data["known_vcs"]


def _build_vc_lookup(known_vcs):
    """Return a dict mapping lowercase alias/canonical → canonical_name."""
    lookup = {}
    for vc in known_vcs:
        lookup[vc["canonical_name"].lower()] = vc["canonical_name"]
        for alias in vc.get("aliases", []):
            lookup[alias.lower()] = vc["canonical_name"]
    return lookup


def _normalise_location(text):
    if not text:
        return "Unknown"
    lower = text.lower()
    for city, keywords in LOCATION_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return city
    if "scotland" in lower or "scottish" in lower:
        return "Other Scotland"
    return "Unknown"


def _sector_word_match(needle, haystack):
    # Short single-word aliases (≤4 chars, e.g. "AI", "ML", "EV") need word boundaries
    # to prevent matching inside longer words ("AI" inside "entertainment").
    # Longer aliases and phrases use plain substring matching, which is intentional:
    # "entertainment tech" should match inside "entertainment technology".
    if " " not in needle and len(needle) <= 4:
        return bool(re.search(r"\b" + re.escape(needle) + r"\b", haystack, re.IGNORECASE))
    return needle.lower() in haystack


def _normalise_sector(raw_sector, sectors):
    if not raw_sector:
        return None, False
    lower = raw_sector.lower().strip()
    for s in sectors:
        if lower == s["canonical"].lower():
            return s["canonical"], True
        for alias in s.get("aliases", []):
            if lower == alias.lower():
                return s["canonical"], True
    # Substring fallback: sector text contains a canonical name or alias as a whole word
    for s in sectors:
        if _sector_word_match(s["canonical"], lower):
            return s["canonical"], True
        for alias in s.get("aliases", []):
            if _sector_word_match(alias, lower):
                return s["canonical"], True
    return raw_sector, False


def _normalise_round(raw_round):
    if not raw_round:
        return "Unknown"
    key = raw_round.lower().strip()
    return ROUND_NORMALISATION.get(key, "Unknown")


def _parse_amount(raw_str, fx_rates):
    """Return (amount_gbp_millions, currency_original). Both None if unparseable."""
    if not raw_str:
        return None, None
    lower = raw_str.lower().strip()
    if lower in ("undisclosed", "not disclosed", "confidential", "tbc", "n/a", ""):
        return None, None

    m = AMOUNT_RE.search(raw_str)
    if not m:
        return None, None

    symbol = m.group(1)
    number_str = m.group(2).replace(",", "")
    unit = (m.group(3) or "").lower()

    try:
        number = float(number_str)
    except ValueError:
        return None, None

    if unit in ("bn", "billion"):
        number *= 1000
    elif unit in ("k", "thousand"):
        number /= 1000
    # "m" / "million" → already in millions; no suffix → assume millions

    currency = CURRENCY_SYMBOLS.get(symbol, "GBP")
    rate = fx_rates.get(currency, 1.0)
    return round(number * rate, 3), currency


def _normalise_investors(lead, others, vc_lookup):
    raw = []
    if lead:
        raw.append(lead)
    if others:
        if isinstance(others, list):
            raw.extend(others)
        elif isinstance(others, str):
            raw.extend([x.strip() for x in re.split(r"[,;]", others) if x.strip()])
    seen = set()
    result = []
    for name in raw:
        canonical = vc_lookup.get(name.lower().strip(), name.strip())
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            result.append(canonical)
    return result


def _parse_date(raw_date, source_url=None, headline=None):
    if raw_date:
        # Try as-is first
        m = DATE_IN_STRING_RE.search(str(raw_date))
        if m:
            return m.group(1)
        try:
            return dateparser.parse(str(raw_date), dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Attempt to extract from URL
    if source_url:
        m = DATE_IN_URL_RE.search(source_url)
        if m:
            year, month, day = m.group(1), m.group(2).zfill(2), (m.group(3) or "01").zfill(2)
            try:
                datetime(int(year), int(month), int(day))
                return f"{year}-{month}-{day}"
            except ValueError:
                pass
        m = DATE_IN_STRING_RE.search(source_url)
        if m:
            return m.group(1)

    # Attempt to extract from headline
    if headline:
        m = DATE_IN_STRING_RE.search(headline)
        if m:
            return m.group(1)

    return None


def _normalise_company_name(name):
    if not name:
        return name
    # Strip trailing legal suffixes for the display name
    # We keep the cleaned display version as company_name
    cleaned = LEGAL_SUFFIXES.sub("", name).strip()
    # Title case unless it looks like it's already styled (has internal caps)
    if cleaned == cleaned.upper() or cleaned == cleaned.lower():
        cleaned = cleaned.title()
    return cleaned


def _make_record_id(company_name, round_type, announcement_date):
    """Produce a stable record ID."""
    name_part = company_name or "unknown"
    # Strip legal suffixes, lowercase, spaces→hyphens, keep letters/digits/hyphens
    name_part = LEGAL_SUFFIXES.sub("", name_part).strip().lower()
    name_part = re.sub(r"\s+", "-", name_part)
    name_part = re.sub(r"[^a-z0-9\-]", "", name_part)
    name_part = re.sub(r"-{2,}", "-", name_part).strip("-")

    round_part = (round_type or "unknown").lower().replace(" ", "-")

    date_part = announcement_date if announcement_date else "undated"

    return f"{name_part}_{round_part}_{date_part}"


def _score_record(record, sectors):
    score = 0
    if record.get("company_name"):
        score += 20
    if record.get("company_location") not in (None, "Unknown"):
        score += 10
    if record.get("sector_normalised"):
        score += 10
    if record.get("round_type") not in (None, "Unknown"):
        score += 10
    if record.get("amount_gbp_millions") is not None:
        score += 15
    if record.get("investors"):
        score += 20
    if record.get("announcement_date"):
        score += 10
    source_url = record.get("source_url", "")
    # Primary source heuristics: press release or company blog
    if source_url and any(kw in source_url.lower() for kw in ("press-release", "news", "blog", "newsroom", "media")):
        score += 5
    return score


def _flag_issues(record, raw_text=""):
    issues = []
    if not record.get("amount_gbp_millions") and not record.get("amount_original"):
        issues.append("amount_missing")
    if not record.get("investors"):
        issues.append("investor_unnamed")
    if not record.get("announcement_date"):
        issues.append("date_missing")
    if record.get("company_location") in (None, "Unknown"):
        issues.append("location_unknown")

    combined_text = " ".join(filter(None, [
        raw_text,
        record.get("headline", ""),
        record.get("summary", ""),
    ])).lower()
    if any(re.search(p, combined_text) for p in GRANT_PATTERNS):
        issues.append("possible_grant_not_vc")

    location = record.get("company_location", "Unknown")
    if location in ("Unknown",):
        issues.append("company_not_clearly_scottish")

    return issues


def _normalise_record(raw, sectors, fx_rates, vc_lookup):
    company_name = _normalise_company_name(raw.get("company_name") or raw.get("company"))
    location_raw = raw.get("company_location") or raw.get("location") or raw.get("city") or ""
    company_location = _normalise_location(location_raw)

    sector_raw = raw.get("company_sector") or raw.get("sector") or ""
    company_sector, sector_normalised = _normalise_sector(sector_raw, sectors)
    if company_sector is None:
        company_sector = "Other"
        sector_normalised = False

    round_type = _normalise_round(raw.get("round_type") or raw.get("funding_round") or "")

    amount_original = raw.get("amount_original") or raw.get("amount_raised") or raw.get("amount") or raw.get("raise_amount")
    amount_gbp, currency_original = _parse_amount(str(amount_original) if amount_original else None, fx_rates)

    lead = raw.get("lead_investor") or raw.get("lead")
    others = raw.get("other_investors") or raw.get("investors") or []
    investors = _normalise_investors(lead, others, vc_lookup)
    # Normalise lead investor name too
    lead_investor = vc_lookup.get((lead or "").lower().strip()) or lead or None
    if lead_investor:
        lead_investor = vc_lookup.get(lead_investor.lower(), lead_investor)

    source_url = raw.get("source_url") or raw.get("url") or ""
    headline = raw.get("headline") or raw.get("title") or ""
    announcement_date = _parse_date(
        raw.get("announcement_date") or raw.get("date"),
        source_url=source_url,
        headline=headline,
    )

    record = {
        "id": "",  # filled below
        "company_name": company_name,
        "company_location": company_location,
        "company_sector": company_sector,
        "sector_normalised": sector_normalised,
        "round_type": round_type,
        "amount_original": str(amount_original) if amount_original else None,
        "amount_gbp_millions": amount_gbp,
        "currency_original": currency_original or "GBP",
        "investors": investors,
        "lead_investor": lead_investor,
        "announcement_date": announcement_date,
        "source_url": source_url,
        "source_name": raw.get("source_name") or raw.get("source") or "",
        "headline": headline,
        "summary": raw.get("summary") or raw.get("description") or "",
        "confidence": raw.get("confidence") or "medium",
        "data_quality_score": 0,
        "issues": [],
        "raw_snippet": raw.get("raw_snippet") or raw.get("snippet") or "",
    }

    record["id"] = _make_record_id(company_name, round_type, announcement_date)
    record["data_quality_score"] = _score_record(record, sectors)
    record["issues"] = _flag_issues(record, raw_text=record["raw_snippet"])

    return record


def run(date: str = None):
    sectors, fx_rates, known_vcs = _load_config()
    vc_lookup = _build_vc_lookup(known_vcs)

    date_prefix = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    raw_files = sorted(
        f for f in RAW_DIR.glob(f"{date_prefix}_*.json")
        if "errors" not in f.name
    )

    if not raw_files:
        # Fall back to any raw files if date-filtered set is empty
        raw_files = sorted(
            f for f in RAW_DIR.glob("*.json")
            if "errors" not in f.name
        )

    all_records = []
    source_files = []
    parse_errors = []

    for path in raw_files:
        source_files.append(path.name)
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                all_records.extend(data)
            elif isinstance(data, dict) and "records" in data:
                all_records.extend(data["records"])
            elif isinstance(data, dict) and "investments" in data:
                all_records.extend(data["investments"])
        except Exception as e:
            logger.warning("Failed to parse %s: %s", path.name, e)
            parse_errors.append(path.name)

    investments = []
    for raw in all_records:
        try:
            investments.append(_normalise_record(raw, sectors, fx_rates, vc_lookup))
        except Exception as e:
            logger.warning("Failed to normalise record: %s — %s", raw, e)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(investments),
        "source_files": source_files,
        "parse_errors": parse_errors,
        "investments": investments,
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "investments.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info("Parser complete: %d records written to %s", len(investments), out_path)
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(date=date_arg)
