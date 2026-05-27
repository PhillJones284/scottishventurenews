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
If asked to "run the agent", execute the full pipeline in sequence using the Agent tool, with a gate check after each stage. Stop and report failure if any gate fails — do not proceed to the next stage (except Stage 1a, which has a soft gate — see below).

**Stage 1** has two sub-steps: **Stage 1a** (Fetcher, Python) and **Stage 1b** (Scraper, Claude agent). **Stage 4** (reporter) is a Claude agent.
**Stages 2 and 3** (parser, deduplicator) are Python — run them with `python pipeline/parser.py` and `python pipeline/deduplicator.py` via the Bash tool. Both accept an optional `--date YYYY-MM-DD` argument; omit it to default to today.

**How to invoke agent stages:** Use the Agent tool with `subagent_type: "general-purpose"`. Read the body of the relevant `.claude/agents/<stage>.md` file (everything after the second `---` frontmatter delimiter) and use it as the prompt, prepending `Today's date is YYYY-MM-DD.` with today's actual date substituted.

**Headless / automated runs:** `pipeline/run.py` orchestrates all four stages in one command (`python pipeline/run.py [--date YYYY-MM-DD]`). It requires `ANTHROPIC_API_KEY` to be set and the `claude` CLI to be on `$PATH`. Use this for cron or CI; use the Agent tool approach for interactive runs.

### Stage 1a — Fetcher (Python)
Run: `python pipeline/fetcher.py` (or `python pipeline/fetcher.py --date YYYY-MM-DD`)

**Gate**: `data/raw/YYYY-MM-DD_candidates.json` must exist. An empty array `[]` is acceptable.
If the gate fails: do **not** stop — proceed to Stage 1b anyway (the scraper agent will fall back to WebFetch mode). Before proceeding, read `data/raw/errors.json` and `data/raw/YYYY-MM-DD_fetch_log.json` (if either exists) and report to Phill:
- that the fetcher failed and fallback mode will be used this run
- a brief summary of what went wrong (error messages, which sources failed)
- that the fetch_log is available for bug fixing before the next run

### Stage 1b — Scraper (Claude agent)
Agent tool: `subagent_type: "general-purpose"`, prompt = today's date + body of `.claude/agents/scraper.md`

**Gate**: At least one `data/raw/YYYY-MM-DD_*.json` file (matching today's date) must exist and contain at least one record (i.e. not an empty array `[]`).
If the gate fails: stop, tell Phill the scraper produced no records, and suggest checking `data/raw/errors.json` for source failures.

**Post-run check**: After Stage 1b completes, run both of the following checks:

1. **Coverage check** — compare the source slugs present in `data/raw/YYYY-MM-DD_candidates.json` against the output files written by the scraper (`data/raw/YYYY-MM-DD_<slug>.json`). Report any slugs that appear in the candidates file but have no corresponding output file. These are sources the scraper silently skipped and whose candidates were not processed. Example one-liner:
   ```bash
   python -c "
   import json, glob
   from pathlib import Path
   date = 'YYYY-MM-DD'
   candidates = json.load(open(f'data/raw/{date}_candidates.json'))
   slugs_in_candidates = {c['source_slug'] for c in candidates}
   written = {Path(f).stem.replace(f'{date}_','') for f in glob.glob(f'data/raw/{date}_*.json')}
   written -= {'candidates', 'fetch_log'}
   missing = slugs_in_candidates - written
   if missing:
       print('SKIPPED SOURCES (candidates not processed):', missing)
   else:
       print('All candidate sources processed.')
   "
   ```

2. **Filter/extraction check** — read `data/raw/YYYY-MM-DD_fetch_log.json` if it exists. If any entry shows `items_found > 0` but `candidates_added = 0`, or `text_extract_failures > 0`, report these to Phill as potential filter or extraction issues worth investigating — even if the overall run succeeded. A source producing items but zero candidates may indicate the keyword filter is too aggressive for that source.

### Stage 2 — Parser (Python)
Run: `python pipeline/parser.py` (or `python pipeline/parser.py --date YYYY-MM-DD`)

**Gate**: `data/processed/investments.json` must exist and have `record_count > 0`.
If the gate fails: stop, tell Phill the parser produced no records, and show the list of raw files that were consumed.

### Stage 3 — Deduplicator (Python)
Run: `python pipeline/deduplicator.py` (or `python pipeline/deduplicator.py --date YYYY-MM-DD`)

**Gate**: `data/processed/investments_deduped.json` must exist.
If the gate fails: stop, tell Phill the deduplicator did not produce output.

### Stage 4 — Reporter
Agent tool: `subagent_type: "general-purpose"`, prompt = today's date + body of `.claude/agents/reporter.md`

**Gate**: A file matching `data/reports/YYYY-MM-DD_vc-report.md` (today's date) must exist.
If the gate fails: stop, tell Phill the reporter did not produce a report.

Report output lands in `data/reports/`. Anything else is development work.

## Project structure
You are in the root folder of the project, which is named scottish-vc-tracker
The architecture of the project is as follows

```
scottish-vc-tracker/
│
├── CLAUDE.md
│
├── .gitignore                   ← Used by git. Do not touch
├── .python-version              ← pyenv pins Python version
├── pyproject.toml               ← project + dependencies
├── .venv/                       ← virtual environment (NOT committed - )
│
├── .claude/
│   └── agents/
│       ├── scraper.md           ← Stage 1b: Claude agent prompt
│       ├── scraper-baseline.md  ← Baseline scraper (direct-fetch, no candidates file) — used for comparison testing only
│       ├── parser.md            ← Stage 2: Reference spec only (implemented in pipeline/parser.py)
│       ├── deduplicator.md      ← Stage 3: Reference spec only (implemented in pipeline/deduplicator.py)
│       └── reporter.md          ← Stage 4: Claude agent prompt
│
├── pipeline/
│   ├── __init__.py
│   ├── run.py                   ← Pipeline entry point
│   ├── fetcher.py               ← Stage 1a: Fetch + keyword-filter (Python)
│   ├── parser.py                ← Stage 2: Normalisation (Python)
│   └── deduplicator.py          ← Stage 3: Deduplication + ledger (Python)
│
├── config/
│   ├── sources.json             ← News sources and search queries (curated — do not edit directly)
│   ├── known_vcs.json           ← VC firm profiles and aliases (curated — do not edit directly)
│   ├── suggested_sources.json   ← Staging area for unknown sources found by scraper
│   ├── suggested_vcs.json       ← Staging area for unknown VCs found by scraper
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
| `data/raw/YYYY-MM-DD_candidates.json` | Pre-fetched + keyword-filtered article candidates |
| `data/raw/YYYY-MM-DD_fetch_log.json` | Per-source fetch diagnostics (items found, filtered, errors) |
| `data/raw/*.json` | Raw scraped data per source (scraper output) |
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
- `company_sectors` is an **array**, not a string — a company can belong to multiple sectors; the parser collects all taxonomy matches and the deduplicator unions arrays across runs (sectors accumulate, never overwrite)

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

When moving an entry to `known_vcs.json`, ensure:
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
  "rss_url": "full URL of the RSS or Atom feed, or null if none — scraper prefers this over HTML fetching when set",
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
Do not modify this file unless Phill explicitly asks you to.

If a company's sector does not match any entry in the taxonomy, the parser preserves the raw sector value as a single-element array (e.g. `["underwater basket weaving"]`) and sets `sector_normalised: false`. It does **not** replace the value with `"Other"` — `"Other"` only appears when the raw sector field is blank. Unrecognised sectors are surfaced via `sector_normalised: false` on the record — the parser does not add an `issues` flag for this. When reviewing records, use `sector_normalised: false` to identify companies whose sector may warrant a new taxonomy entry.

## Managing FX rates
### config/fx_rates.json
Do not modify unless Phill asks. If asked to update, fetch current mid-market rates and propose the changes before writing.

If the current rate in fx_rates.json is more than 15% different from the mid-market rate, tell Phill which rate has the mismatch, what the current rate in fx_rates.json is and what the current mid-market rate is. Propose that the rate be changed before writing.


## Architecture comparison test

To verify the Python fetcher is not losing deals compared to the original all-Claude architecture, run:

**Step 1 — Back up current data:**
```
cp -r data/ /tmp/scottish-vc-backup-YYYY-MM-DD/
```

**Step 2 — Run the baseline scraper** (writes to `data/raw/old-arch-test/`, never touches live data):

Use the Agent tool with `subagent_type: "general-purpose"`, prompt = today's date + body of `.claude/agents/scraper-baseline.md`.

**Step 3 — Parse the baseline output:**
```python
import json, sys
from pathlib import Path
sys.path.insert(0, 'pipeline')
import parser as p
p.RAW_DIR = Path('data/raw/old-arch-test')
result = p.run(date='YYYY-MM-DD')
with open('data/processed/investments_old_arch.json', 'w') as f:
    json.dump(result, f, indent=2)
```
Then restore `data/processed/investments.json` from the backup (the step above overwrites it).

**Step 4 — Compare:**
Compare company names in `investments_old_arch.json` vs the new-arch Stage 1b scraper output files (`data/raw/YYYY-MM-DD_*.json`), cross-referenced against the ledger to distinguish genuine data loss from records already captured in prior runs.

**Step 5 — Clean up:**
Delete `data/raw/old-arch-test/` and `data/processed/investments_old_arch.json` when done.

## Development ground rules
- Propose changes and wait for approval before modifying any file
- When proposing a change, explain what you're changing and why
- If you spot something worth improving that's outside the current task, note it but don't act on it
- Do not run the agent pipeline unless explicitly asked to
- You do not handle version control. All git functions will be handled manually by humans
- Python version is controlled via pyenv (.python-version)
- All local execution uses `python`, never `python3`
- A virtual environment (.venv) is required for any Python execution

