# Scottish VC Investment Tracker

A pipeline that monitors freely available news sources for venture capital investment activity in Scottish scale-up companies, and produces a weekly intelligence report.

## Purpose

Your job is to answer: Which VC firms are actively investing in Scottish companies, at what stages, in which sectors, and with what cadence?

You achieve this by producing a weekly analyst-quality intelligence report that can inform:
- Fundraising strategy (who should we approach?)
- Competitive intelligence (who is funding our competitors?)
- Ecosystem understanding (what sectors are hot in Scotland right now?)

### Weekly Report (`data/reports/YYYY-MM-DD_vc-report.md`)

A Markdown report containing:
1. **Executive Summary** — headline numbers and key observations
2. **Active VCs This Period** — who invested, how much, in what
3. **Activity by Stage** — where in the funding lifecycle is the action?
4. **Deal-by-Deal Breakdown** — every confirmed investment with details
5. **VC Intelligence Profiles** — historical patterns per VC firm
6. **Sector Heat Map** — which sectors are attracting capital
7. **Geographic Distribution** — Edinburgh vs Glasgow vs rest of Scotland
8. **Appendix** — low-confidence records and data notes


## Running the agent
If asked to "run the agent", execute the full pipeline in sequence, with a gate check after each stage. Stop and report failure if any gate fails — do not proceed to the next stage.

### Stage 1 — Scraper
```
cd agents/scraper && claude --print "Run the scraper task as described in CLAUDE.md"
```
**Gate**: At least one `data/raw/YYYY-MM-DD_*.json` file (matching today's date) must exist and contain at least one record (i.e. not an empty array `[]`).
If the gate fails: stop, tell Phill the scraper produced no records, and suggest checking `data/raw/errors.json` for source failures.

### Stage 2 — Parser
```
cd agents/parser && claude --print "Run the parser task as described in CLAUDE.md"
```
**Gate**: `data/processed/investments.json` must exist and have `record_count > 0`.
If the gate fails: stop, tell Phill the parser produced no records, and show the list of raw files that were consumed.

### Stage 3 — Deduplicator
```
cd agents/deduplicator && claude --print "Run the deduplicator task as described in CLAUDE.md"
```
**Gate**: `data/processed/investments_deduped.json` must exist.
If the gate fails: stop, tell Phill the deduplicator did not produce output.

### Stage 4 — Reporter
```
cd agents/reporter && claude --print "Run the reporter task as described in CLAUDE.md"
```
**Gate**: A file matching `data/reports/YYYY-MM-DD_vc-report.md` (today's date) must exist.
If the gate fails: stop, tell Phill the reporter did not produce a report.

Report output lands in `data/reports/`. Anything else is development work.

## Project structure
You are in the root folder of the project, which is named scottish-vc-tracker
The architecture of the project is as follows

```
scottish-vc-tracker/
│
├── CLAUDE.md                    ← Orchestrator agent (run this first)
│
├── agents/
│   ├── scraper/CLAUDE.md        ← Stage 1: Web scraping
│   ├── parser/CLAUDE.md         ← Stage 2: Normalisation
│   ├── deduplicator/CLAUDE.md   ← Stage 3: Deduplication + ledger
│   └── reporter/CLAUDE.md       ← Stage 4: Report generation
│
├── config/
│   ├── sources.json             ← News sources and search queries
│   ├── known_vcs.json           ← VC firm profiles and aliases
│   ├── sectors.json             ← Sector taxonomy
│   └── fx_rates.json            ← Currency conversion rates
│
├── data/
│   ├── raw/                     ← Scraper output (per-source JSON files)
│   ├── processed/               ← Parser and deduplicator output
│   │   ├── investments.json     ← Normalised records (this run)
│   │   ├── investments_deduped.json
│   │   └── ledger.json          ← PERSISTENT: all-time historical record
│   └── reports/                 ← Final Markdown reports
│
└── docs/                        ← For user documentation, do not make changes unless told
    └── opening-prompt.md        ← Development prompt for pasting in. Do not touch.
```

### Data Files

| File | Contents |
|---|---|
| `data/raw/*.json` | Raw scraped data per source |
| `data/processed/investments.json` | Normalised records for this run |
| `data/processed/investments_deduped.json` | Deduplicated records with new/updated flags |
| `data/processed/ledger.json` | Persistent all-time record — do not delete |
| `data/reports/YYYY-MM-DD_vc-report.md` | Weekly intelligence report — one file per run |

## Key design decisions
- Agents communicate via JSON files in `data/`, not stdout
- `data/processed/ledger.json` is the persistent source of truth across runs — treat it carefully
- Every investment record has a `confidence` field (high/medium/low) — do not collapse these
- `config/known_vcs.json` uses `canonical_name` as a key — do not rename existing entries
- Deduplication is conservative: when in doubt, flag for review rather than merge
- Investment record IDs follow the format `{normalised-company-name}_{round-type}_{announcement-date}` (e.g. `wallet-ai_series-a_2026-03-15`) — set by the parser, referenced by the deduplicator; must be consistent between stages

## Managing known VCs

### When the agent encounters an unknown VC
If the scraper finds an investor not in `config/known_vcs.json`, record the deal using 
the name as found. Stage the VC in `config/suggested_vcs.json` for review rather than 
writing directly to `known_vcs.json`:

### known_vcs.json schema reminder
When proposing a new entry, it must include all of the following fields:

```json
{
  "canonical_name": "used as a key — once set, do not change it",
  "aliases": "all common shorthand names the scraper might encounter",
  "hq": "the firm's headquarters location",
  "stage_focus": "stages the firm typically invests at e.g. Seed, Series A",
  "scotland_active": "true only if there is evidence of actual Scottish deals",
  "notes": "any useful context about the firm's investment thesis or Scottish activity"
}
```

### If Phill asks you to add a new VC
1. Search for the firm's website, investment focus, stage preference, and geographic activity
2. Propose a new entry following the `known_vcs.json` schema
3. Wait for approval before writing it

### Reviewing staged VCs
If Phill asks to review suggested VCs, go through `config/suggested_vcs.json` one by one,
summarise what you found about each firm, and ask whether to move it to `known_vcs.json`,
leave it staged, or discard it.

### known_vcs.json schema reminder
- `canonical_name` is used as a key — once set, do not change it
- `scotland_active` should only be `true` if there is evidence of actual Scottish deals
- `aliases` should capture all common shorthand names the scraper might encounter

## Managing sources

### When the agent encounters an unknown source
If the scraper finds a useful source not in `config/sources.json`, it should not add it directly. Instead, stage it in `config/suggested_sources.json` with enough context to evaluate it

### sources.json schema reminder
When proposing a new entry, it must include all of the following fields:

```json
{
  "slug": "unique identifier, used in output filenames — lowercase, hyphenated",
  "name": "human readable name of the publication or site",
  "type": "news_site | search | database | vc_newsrooms | aggregator",
  "url": "base url of the source",
  "search_path": "path/query string to append to url, or null if not applicable",
  "queries": "array of search strings — only valid on type: search sources, used instead of search_path when multiple queries must be run",
  "best_effort": "true if the source is partially paywalled or JS-rendered — scraper should attempt it but treat failure as non-blocking",
  "notes": "what kind of deals this source covers well"
}
```

### If asked to add a new source
Phill will type the following command "add [source name or URL] to sources". Claude Code will:
1. Fetch the site and assess its relevance to Scottish VC news
2. Propose a new entry in the `sources.json` schema
3. Wait for approval before writing it

### Reviewing staged sources
Say "review suggested sources". Claude Code will go through `config/suggested_sources.json`
one by one, summarise each, and ask whether to move it to `sources.json`, leave it staged, 
or discard it.

### sources.json is curated
Only sources that have demonstrably produced relevant Scottish VC news should be in 
`sources.json`. Quantity is not the goal — signal quality is.

## Managing Sectors
### config/sectors.json
Do not modify this file unless Phill explicitly asks you to. If a company's sector does not match any entry in the taxonomy, use `"Other"` and flag it in the record's `issues` array as `"sector_not_in_taxonomy"` so Phill can decide whether a new sector is warranted.

## Managing FX rates
### config/fx_rates.json
Do not modify unless Phill asks. If asked to update, fetch current mid-market rates and propose the changes before writing.

If the current rate in fx_rates.json is more than 15% different from the mid-market rate, tell Phill which rate has the mismatch, what the current rate in fx_rates.json is and what the current mid-market rate is. Propose that the rate be changed before writing.


## Development ground rules
- Propose changes and wait for approval before modifying any file
- When proposing a change, explain what you're changing and why
- If you spot something worth improving that's outside the current task, note it but don't act on it
- Do not run the agent pipeline unless explicitly asked to


