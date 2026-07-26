"""
Stage 1c — Firecrawl Scraper

Handles all sources with type: "firecrawl" in config/sources.json.

Each source must have a parse function registered in _PARSERS below.
Adding a type: "firecrawl" source to sources.json without a parse function
raises NotImplementedError for that source — add the function first.

Sources needing cookie auth specify "cookie_env_var": "<VAR>" in sources.json.
The value is read from .env at runtime. Missing env var → scrape proceeds
without the cookie (deal amounts may degrade to "—").
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
SOURCES_PATH = ROOT / "config" / "sources.json"


# ---------------------------------------------------------------------------
# Per-source parse functions
# Signature: (markdown: str, source_url: str) -> list[dict]
# Output dict keys must match the Stage 1c deal record format consumed by
# pipeline/parser.py: company_name, round_type, amount_original,
# announcement_date, lead_investor, other_investors, company_location,
# source_url, source_name, confidence.
# ---------------------------------------------------------------------------

def _parse_crunchbase(markdown: str, source_url: str) -> list[dict]:
    # Each deal row appears on one line, starting with the company name as the
    # tail of a composite image+text link: "Company Name](org_url)Round TypeAmountDate..."
    # The ^ anchor (MULTILINE) targets the start of those lines specifically.
    pattern = re.compile(
        r'^([^\]\n]+)\]\(https://www\.crunchbase\.com/organization/[^)]+\)'
        r'([\w][\w\s\-/]*?)'
        r'([$£€][\d,]+(?:\.\d+)?|—)'
        r'([A-Z][a-z]{2} \d{1,2}, \d{4})',
        re.MULTILINE,
    )
    deals = []
    seen = set()
    for match in pattern.finditer(markdown):
        org, round_type, raised, date = [s.strip() for s in match.groups()]
        key = (org, date)
        if key in seen:
            continue
        seen.add(key)
        deals.append({
            "company_name": org,
            "round_type": round_type,
            "amount_original": None if raised == "—" else raised,
            "announcement_date": date,
            "lead_investor": None,
            "other_investors": [],
            "company_location": "Scotland",
            "source_url": source_url,
            "source_name": "Crunchbase",
            "confidence": "high",
        })
    return deals


def _parse_techstart_portfolio(markdown: str, source_url: str) -> list[dict]:
    # techstart.vc/portfolio is a Framer site with no server-rendered content —
    # Firecrawl's rendered markdown is the only way to see the page at all.
    # Unlike Crunchbase, the "Recent follow-on rounds" teasers have no date and
    # inconsistent round/investor wording, so we can't build a final deal record
    # here. Instead we extract the teaser's link to the actual press coverage
    # (tech.eu, TechCrunch, Sifted, ...) as a link candidate — Stage 1b follows
    # each one and extracts the real record from the linked article.
    section_match = re.search(r"# Recent follow-on rounds(.*?)\n# ", markdown, re.DOTALL)
    if not section_match:
        return []
    section = section_match.group(1)

    candidates = []
    seen_urls = set()
    for match in re.finditer(r"-\s*(.+?)\n+\[Read on ([^\]]+)\]\(([^)]+)\)", section, re.DOTALL):
        teaser, publication, url = (s.strip() for s in match.groups())
        if url in seen_urls:
            continue
        seen_urls.add(url)
        # Best-effort company name hint from the teaser sentence — Stage 1b
        # re-confirms the name from the actual article regardless.
        name_match = re.match(r"^(.+?)\s+(?:raises?|rasies?|secures?)\s", teaser, re.IGNORECASE)
        candidates.append({
            "source_slug": "techstart-portfolio",
            "source_name": publication,
            "url": url,
            "title": teaser,
            "published": None,
            "text": None,
            "company_hint": name_match.group(1).strip() if name_match else None,
            "needs_extraction": True,
        })
    return candidates


_PARSERS = {
    "crunchbase": _parse_crunchbase,
    "techstart-portfolio": _parse_techstart_portfolio,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(date: str | None = None) -> dict[str, int]:
    """
    Fetch and parse all type: "firecrawl" sources.
    Returns {slug: record_count} for each source attempted.
    Raises EnvironmentError if FIRECRAWL_API_KEY is not set.
    Raises NotImplementedError if a source has no registered parse function.
    Per-source fetch/parse failures are caught and logged; other sources continue.
    """
    from firecrawl import FirecrawlApp

    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise EnvironmentError("FIRECRAWL_API_KEY not set")

    all_sources = json.loads(SOURCES_PATH.read_text())["sources"]
    firecrawl_sources = [s for s in all_sources if s.get("type") == "firecrawl"]

    if not firecrawl_sources:
        logger.info("Stage 1c: no firecrawl sources configured.")
        return {}

    # Validate parse functions exist for all configured sources before fetching anything.
    for source in firecrawl_sources:
        slug = source["slug"]
        if slug not in _PARSERS:
            raise NotImplementedError(
                f"No parse function registered for firecrawl source '{slug}'. "
                "Add _parse_{slug}() to pipeline/firecrawl_scraper.py and register it in _PARSERS."
            )

    app = FirecrawlApp(api_key=api_key)
    results = {}

    for source in firecrawl_sources:
        slug = source["slug"]
        url = source["url"]
        wait_ms = source.get("wait_ms", 5000)

        headers = {}
        cookie_env_var = source.get("cookie_env_var")
        if cookie_env_var:
            cookie_val = os.environ.get(cookie_env_var, "")
            if cookie_val:
                headers["Cookie"] = f"authcookie={cookie_val}"
            else:
                logger.warning(
                    "Stage 1c (%s): cookie_env_var '%s' is not set — "
                    "scraping without auth (amounts may show as '—')",
                    slug, cookie_env_var,
                )

        try:
            logger.info("Stage 1c: fetching %s via firecrawl (%s)", slug, url)
            result = app.scrape_url(
                url,
                formats=["markdown"],
                headers=headers or None,
                actions=[{"type": "wait", "milliseconds": wait_ms}],
            )
            deals = _PARSERS[slug](result.markdown, url)
            output_mode = source.get("output_mode", "deals")
            if output_mode == "link_candidates":
                # Not final deal records (e.g. no announcement_date) — filename
                # includes "_candidates" so Stage 2's parser skips it; Stage 1b
                # follows each link and writes the real records separately.
                out_path = DATA_RAW / f"{date}_{slug}_candidates.json"
            else:
                out_path = DATA_RAW / f"{date}_{slug}.json"
            out_path.write_text(json.dumps(deals, indent=2))
            logger.info("Stage 1c (%s): wrote %d %s → %s", slug, len(deals), output_mode, out_path.name)
            results[slug] = len(deals)
        except Exception as e:
            logger.warning("Stage 1c (%s): failed — %s", slug, e)
            results[slug] = 0

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    counts = run(date=date_arg)
    for slug, n in counts.items():
        print(f"{slug}: {n} deals")
