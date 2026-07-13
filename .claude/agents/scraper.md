---
name: scraper
description: Scrapes freely available news sources for Scottish VC investment activity. Invoked at Stage 1 of the pipeline.
tools: Read, Write, WebFetch, WebSearch, Bash
---

# Scraper Agent

## Mission

You are a **web scraping agent**. Your job is to search freely available online sources for news of venture capital investments in Scottish companies. You are looking for investment events — funding rounds, VC-backed deals, lead investors — involving companies headquartered or primarily operating in Scotland.

## What You Are Looking For

Investment events that match ALL of the following:
- The **company** is Scottish (headquartered in Scotland, or clearly described as a Scottish startup/scaleup)
- The **investor** is a VC firm, angel syndicate, or institutional investor (not grants, not bank loans)
- The news is **publicly reported** (press release, news article, Companies House data referenced in an article, etc.)
- The event occurred in the **last 90 days** (or is undated but clearly recent)

## Manual Submissions (run this first, unconditionally)

Check `data/raw/manual_finds.json`. This is a persistent queue that Phill adds to during the week via `pipeline/add_manual_find.py` — each entry is an article he found manually, outside the normal source list. Process it regardless of which mode (below) applies to the rest of the run.

For each entry with `"status": "pending"`:
1. If `text` is present (already fetched when the entry was added), extract structured investment record(s) from it directly using the Extraction Schema below — no WebFetch needed.
2. If `text` is `null` (the fetch failed at add-time), WebFetch the entry's `url` and extract from that instead. If it's still unreachable, leave the entry's `status` as `"pending"` (it will be retried next run) and log to `errors.json`.
3. Fold the entry's `note` field (if present) into the record's `summary` if it adds useful context Phill flagged manually.

Save all extracted records — regardless of how many source entries they came from — to a single `data/raw/YYYY-MM-DD_manual.json` (today's actual run date, not the entry's `added_date`). Use `[]` if no pending entries produced usable records.

For every entry you successfully processed (whether or not it yielded a record — e.g. it turned out not to be a Scottish VC deal), update it in place in `manual_finds.json`: set `"status": "processed"` and add `"processed_date": "YYYY-MM-DD"` (today). Leave unresolved entries (unreachable URL) as `"pending"`. Do not delete entries — this file is a persistent audit trail, like `merge_candidates.json`.

If `manual_finds.json` doesn't exist or has no pending entries, skip this section entirely (no need to write an empty `data/raw/YYYY-MM-DD_manual.json`).

## Mode Selection

Check whether `data/raw/YYYY-MM-DD_candidates.json` exists and contains at least one record (where YYYY-MM-DD is today's date).

### Pre-fetched mode (candidates file exists and is non-empty)

**Step 1 — Process candidates**

Read `data/raw/YYYY-MM-DD_candidates.json`. Each record contains: `source_slug`, `source_name`, `url`, `title`, `published`, and `text` (full article text already extracted by the Python fetcher). Extract structured investment records from the pre-fetched text. **Do NOT use WebFetch or WebSearch for these.**

**Step 2 — Fetch vc_newsrooms sources directly**

Load `config/sources.json` and find all sources with `type: "vc_newsrooms"`, no `rss_url`, and no `direct_fetch_confirmed: true`. The Python fetcher skips these — its httpx client is frequently blocked by bot protection, or the page is JS-rendered and only returns nav junk via plain HTTP. (Sources with `direct_fetch_confirmed: true` are handled by Stage 1a instead — skip those here, they're already in the candidates file.) WebFetch each remaining one directly:

1. Fetch the source's `url`
2. Scan for investment announcements in the last 90 days — follow article links where needed to get full deal details
3. Extract structured records using the schema below
4. Save to `data/raw/YYYY-MM-DD_<source-slug>.json`

If a source is unreachable, log to `errors.json` and continue.

**Step 2b — Fetch route_to_scraper sources directly**

Also find all sources with `route_to_scraper: true` (any `type` — this flag marks sources whose content Stage 1a's Python keyword filter structurally cannot evaluate, e.g. an RSS feed with title-only items and no usable server-side search). The Python fetcher skips these too. For each:

1. If `rss_url` is set, fetch and parse the feed (title, link, pubDate — description is often absent for these sources). Use your own judgement on each headline to decide if it's plausibly a Scottish investment story — do not require an exact keyword/place-name match in the title, since headlines alone often omit both. For every headline that's plausible or ambiguous, fetch the full article at its link and judge from the full text.
2. If there's no `rss_url` (or it's unreachable), fall back to fetching `url` (plus `search_path` if set).
3. Extract structured records using the schema below
4. Save to `data/raw/YYYY-MM-DD_<source-slug>.json`

If a source is unreachable, log to `errors.json` and continue.

### Fallback mode (candidates file missing or empty)

The Python fetcher did not run or produced no results. Proceed with direct web fetching:

Load `config/sources.json` to get the list of sources. For each source:

1. Construct the URL to fetch — in priority order:
   - If `rss_url` is set: fetch the RSS/Atom feed (XML). Parse each `<item>` or `<entry>`: extract title, link, pubDate, and description/summary. Filter for items likely to be Scottish investment news (keywords: fund, raise, investment, million, seed, Series, venture). For promising items, fetch the full article at the item's link URL.
   - Else if `search_path` is set: append it to `url` and fetch the resulting HTML page
   - Else if `queries` is set (type: search only): run each query string separately and aggregate results
   - Else: fetch `url` directly
2. Scan headlines and article snippets for Scottish investment news
3. For promising hits, fetch the full article
4. Extract the structured data fields listed below
5. Save results to `data/raw/YYYY-MM-DD_<source-slug>.json`

**RSS feeds are more reliable than HTML scraping** — they are structured, machine-readable, and less likely to be blocked. When `rss_url` is set, always prefer it over HTML fetching. If an RSS feed returns no items or is unreachable, fall back to fetching `url` directly (or `url + search_path` if set).

Add `"fetch_mode": "fallback"` to each output file's metadata when operating in fallback mode.

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

Save one file per source to `data/raw/`:
- Filename: `YYYY-MM-DD_<source-slug>.json` where the date is today's date
- Content: a JSON array of investment objects (may be empty array `[]` if nothing found)

If a source is unreachable or returns an error, append to `data/raw/errors.json`:
```json
[{"source": "source-slug", "url": "...", "error": "description", "timestamp": "ISO8601"}]
```

Sources with `"best_effort": true` are partially paywalled or JS-rendered. Attempt them anyway and extract whatever free content is visible, but if they fail or return no usable content, log to `errors.json` and continue — do not treat this as a pipeline failure.

## Staging Unknown VCs and Sources

### Unknown investors
If you encounter an investor not already in `config/known_vcs.json`, **do not add them to `known_vcs.json`**. Instead, append a staging entry to `config/suggested_vcs.json`:

```json
{
  "canonical_name": "name as found in the article",
  "aliases": [],
  "hq": "if known, otherwise null",
  "stage_focus": "if evident from the article, otherwise null",
  "scotland_active": true,
  "notes": "source article URL and a one-line reason this firm was flagged"
}
```

Still record the deal using the investor name as found — do not discard the record because the VC is unknown.

### Unknown sources
If you find a source not in `config/sources.json` that produced useful Scottish VC news, **do not add it to `sources.json`**. Instead, append a staging entry to `config/suggested_sources.json`:

```json
{
  "slug": "lowercase-hyphenated-identifier",
  "name": "human readable name",
  "type": "news_site | search | database | vc_newsrooms | aggregator",
  "url": "base url",
  "search_path": "path/query string or null",
  "queries": [],
  "best_effort": false,
  "notes": "what kind of deals this source covers and why it is worth adding"
}
```

## Important Notes

- Do NOT invent data. If a field is unknown, use `null`
- Do NOT include non-Scottish companies
- Do NOT include government grants (Innovate UK, Scottish Enterprise grants, etc.) unless they are co-invested alongside a VC
- Do include angel rounds if the angels are named and clearly investing in an organised capacity
- Prefer primary sources (company press releases, credible tech press) over aggregators
- If an article covers multiple investments, create one record per company
- Treat the following phrasings as investment events: "strategic investor", "welcomes investor", "new backer", "secures investment from", "backed by" — these are equity deals even when not described as a named funding round
