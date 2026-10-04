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


def _parse_sifted_uk(markdown: str, source_url: str) -> list[dict]:
    # sifted.eu blocks plain httpx/WebFetch (403 on the RSS feed, empty shell
    # on /search) — Firecrawl renders it like a real browser. The rendered
    # markdown of /sector/venture-capital/ is a flat list of article teasers,
    # each starting with a markdown list item "- [Headline](article_url)"
    # immediately followed by category/date/description/author metadata for
    # that same article before the next "- [" list item begins. Like
    # techstart-portfolio, there's no reliable per-item date in a form we can
    # parse deal fields from here, so this is a link-candidates source:
    # Stage 1b follows each link and extracts (or discards) the real record.
    candidates = []
    seen_urls = set()
    for match in re.finditer(
        r"^-\s*\[([^\]]+)\]\((https://sifted\.eu/articles/[^)]+)\)",
        markdown,
        re.MULTILINE,
    ):
        title, url = (s.strip() for s in match.groups())
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append({
            "source_slug": "sifted-uk",
            "source_name": "Sifted",
            "url": url,
            "title": title,
            "published": None,
            "text": None,
            "company_hint": None,
            "needs_extraction": True,
        })
    return candidates


_PARSERS = {
    "crunchbase": _parse_crunchbase,
    "techstart-portfolio": _parse_techstart_portfolio,
    "sifted-uk": _parse_sifted_uk,
}


# ---------------------------------------------------------------------------
# PROTOTYPE (2026-10-04) — Firecrawl native search() path
#
# duckduckgo-scottish-vc runs several distinct text queries rather than
# scraping one fixed URL, so it doesn't fit the single scrape_url() per
# source shape above. Firecrawl's search() API runs the query itself and,
# with scrape_options, returns each result already rendered to markdown —
# a closer replacement for fetcher.py's old _fetch_queries() (plain httpx
# search + per-result fetch) than scrape_url() would be.
#
# Sources using this path are marked "firecrawl_mode": "search" in
# sources.json and registered in _SEARCH_PARSERS below (not _PARSERS —
# the run() loop checks firecrawl_mode first and takes this branch instead
# of calling scrape_url()).
#
# NOT YET WIRED INTO Stage 1b: this writes output_mode "link_candidates"
# records with `text` already populated from Firecrawl's render, but
# .claude/agents/scraper.md Step 2c currently always re-WebFetches the url
# for link_candidates entries, ignoring any pre-fetched text. For the 403/429
# URLs this source hits, a Stage 1b WebFetch may hit the same block that
# Firecrawl just avoided. Fully wiring this up would mean either teaching
# Step 2c to skip the re-fetch when `text` is already present, or giving
# this source its own output_mode. Left as link_candidates for this
# prototype so the existing contract isn't changed without Phill's sign-off.
# ---------------------------------------------------------------------------

def _parse_duckduckgo_scottish_vc(results: list[dict]) -> list[dict]:
    candidates = []
    seen_urls = set()
    for r in results:
        url = r["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append({
            "source_slug": "duckduckgo-scottish-vc",
            "source_name": "DuckDuckGo — Scottish VC search",
            "url": url,
            "title": r.get("title"),
            "published": None,
            "text": r.get("markdown") or r.get("description"),
            "company_hint": None,
            "needs_extraction": True,
            "fetched_via": "firecrawl_search",
            "matched_query": r.get("query"),
        })
    return candidates


_SEARCH_PARSERS = {
    "duckduckgo-scottish-vc": _parse_duckduckgo_scottish_vc,
}


def _run_search_source(app, source: dict, date: str) -> int:
    """
    Runs each of source["queries"] through Firecrawl's native search() API
    (web results, scraped to markdown), dedupes by URL across queries, parses
    via _SEARCH_PARSERS[slug], and writes the output file. Returns the
    record count written. Per-query failures are caught and logged; other
    queries for the same source continue.
    """
    from firecrawl.v2.types import ScrapeOptions

    slug = source["slug"]
    search_limit = source.get("search_limit", 8)
    all_results = []
    seen_urls: set = set()

    for query in source["queries"]:
        try:
            resp = app.search(
                query,
                sources=["web"],
                limit=search_limit,
                scrape_options=ScrapeOptions(formats=["markdown"]),
            )
            for doc in (resp.web or []):
                meta = getattr(doc, "metadata", None)
                doc_url = getattr(meta, "url", None) if meta else None
                if not doc_url or doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)
                all_results.append({
                    "query": query,
                    "url": doc_url,
                    "title": getattr(meta, "title", None) if meta else None,
                    "description": getattr(meta, "description", None) if meta else None,
                    "markdown": getattr(doc, "markdown", None),
                })
        except Exception as e:
            logger.warning("Stage 1c (%s): search failed for query '%s' — %s", slug, query, e)

    deals = _SEARCH_PARSERS[slug](all_results)
    output_mode = source.get("output_mode", "deals")
    if output_mode == "link_candidates":
        out_path = DATA_RAW / f"{date}_{slug}_candidates.json"
    else:
        out_path = DATA_RAW / f"{date}_{slug}.json"
    out_path.write_text(json.dumps(deals, indent=2, ensure_ascii=False))
    logger.info("Stage 1c (%s): wrote %d %s → %s", slug, len(deals), output_mode, out_path.name)
    return len(deals)


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
        registry = _SEARCH_PARSERS if source.get("firecrawl_mode") == "search" else _PARSERS
        if slug not in registry:
            raise NotImplementedError(
                f"No parse function registered for firecrawl source '{slug}'. "
                "Add _parse_{slug}() to pipeline/firecrawl_scraper.py and register it in "
                f"{'_SEARCH_PARSERS' if source.get('firecrawl_mode') == 'search' else '_PARSERS'}."
            )

    app = FirecrawlApp(api_key=api_key)
    results = {}

    for source in firecrawl_sources:
        slug = source["slug"]

        if source.get("firecrawl_mode") == "search":
            results[slug] = _run_search_source(app, source, date)
            continue

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
