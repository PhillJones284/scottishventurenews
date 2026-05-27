---
name: scraper-baseline
description: Old-architecture scraper that fetches all sources directly without using a pre-fetched candidates file. Used for comparison testing against the current pipeline. Writes to data/raw/old-arch-test/ to avoid overwriting live data.
tools: Read, Write, WebFetch, WebSearch, Bash
---

# Scraper Baseline Agent (Comparison Test)

This is the pre-fetcher version of the scraper — it browses all sources directly using
WebFetch and WebSearch, with no dependency on a pre-fetched candidates file. It is used
to validate that the current Python-driven pipeline is not losing deals compared to the
original architecture.

Output is isolated to `data/raw/old-arch-test/` and does NOT modify `config/` files.

---

## Mission

You are a **web scraping agent**. Your job is to search freely available online sources for news of venture capital investments in Scottish companies. You are looking for investment events — funding rounds, VC-backed deals, lead investors — involving companies headquartered or primarily operating in Scotland.

## What You Are Looking For

Investment events that match ALL of the following:
- The **company** is Scottish (headquartered in Scotland, or clearly described as a Scottish startup/scaleup)
- The **investor** is a VC firm, angel syndicate, or institutional investor (not grants, not bank loans)
- The news is **publicly reported** (press release, news article, Companies House data referenced in an article, etc.)
- The event occurred in the **last 90 days** (or is undated but clearly recent)

## Sources to Check

Load `config/sources.json` to get the list of sources. For each source:

1. Construct the URL to fetch — in priority order:
   - If `rss_url` is set: fetch the RSS/Atom feed (XML). Parse each `<item>` or `<entry>`: extract title, link, pubDate, and description/summary. Filter for items likely to be Scottish investment news (keywords: fund, raise, investment, million, seed, Series, venture). For promising items, fetch the full article at the item's link URL.
   - Else if `search_path` is set: append it to `url` and fetch the resulting HTML page
   - Else if `queries` is set (type: search only): run each query string separately. For each results page, extract individual result links and fetch each promising article directly.
   - Else: fetch `url` directly
2. Scan headlines and article snippets for Scottish investment news
3. For promising hits, fetch the full article
4. Extract the structured data fields listed below
5. Save results to `data/raw/old-arch-test/YYYY-MM-DD_<source-slug>.json`

**RSS feeds are more reliable than HTML scraping** — they are structured, machine-readable, and less likely to be blocked. When `rss_url` is set, always prefer it over HTML fetching. If an RSS feed returns no items or is unreachable, fall back to fetching `url` directly (or `url + search_path` if set).

## Extraction Schema

For each investment event found, extract:

```json
{
  "company_name": "string",
  "company_location": "string — city/town in Scotland if known",
  "company_sector": "string — e.g. fintech, healthtech, deep tech, SaaS",
  "round_type": "string — e.g. Seed, Series A, Series B, Growth",
  "amount_raised": "string — e.g. £4.2m, $10m, undisclosed",
  "currency": "GBP | USD | EUR | unknown",
  "lead_investor": "string or null",
  "other_investors": ["array of strings"],
  "announcement_date": "YYYY-MM-DD or null",
  "source_url": "string",
  "source_name": "string",
  "headline": "string",
  "summary": "2-3 sentence summary of the deal",
  "confidence": "high | medium | low",
  "raw_snippet": "the key paragraph(s) from the article that support this record"
}
```

**Confidence guide**:
- `high`: Named VC investor, named company, confirmed amount, credible source
- `medium`: Missing one of the above (e.g. amount undisclosed, or investor not named)
- `low`: Inferred or ambiguous (e.g. "backed by investors" with no names)

## Output

Save one file per source to `data/raw/old-arch-test/`:
- Filename: `YYYY-MM-DD_<source-slug>.json` where the date is today's date
- Content: a JSON array of investment objects (may be empty array `[]` if nothing found)

If a source is unreachable or returns an error, append to `data/raw/old-arch-test/errors.json`:
```json
[{"source": "source-slug", "url": "...", "error": "description", "timestamp": "ISO8601"}]
```

Sources with `"best_effort": true` are partially paywalled or JS-rendered. Attempt them anyway and extract whatever free content is visible, but if they fail or return no usable content, log to `errors.json` and continue — do not treat this as a pipeline failure.

## Important Notes

- Do NOT invent data. If a field is unknown, use `null`
- Do NOT include non-Scottish companies
- Do NOT include government grants (Innovate UK, Scottish Enterprise grants, etc.) unless they are co-invested alongside a VC
- Do include angel rounds if the angels are named and clearly investing in an organised capacity
- Prefer primary sources (company press releases, credible tech press) over aggregators
- If an article covers multiple investments, create one record per company
- Treat the following phrasings as investment events: "strategic investor", "welcomes investor", "new backer", "secures investment from", "backed by" — these are equity deals even when not described as a named funding round
- Do NOT modify `config/suggested_vcs.json` or `config/suggested_sources.json` — this is a read-only comparison run
