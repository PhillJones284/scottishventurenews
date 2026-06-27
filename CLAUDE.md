# Scottish VC Investment Tracker

A pipeline that monitors freely available news sources for venture capital investment activity in Scottish scale-up companies, and produces a weekly intelligence report.

## Purpose

Your job is to answer: Which VC firms are actively investing in Scottish companies, at what stages, in which sectors, and with what cadence?

You achieve this by producing a weekly analyst-quality intelligence report that can inform:
- Fundraising strategy (who should we approach?)
- Competitive intelligence (who is funding our competitors?)
- Ecosystem understanding (what sectors are hot in Scotland right now?)

### Weekly Report (`data/reports/YYYY-MM-DD_vc-report.md`)

A short Markdown briefing, opening with a one-line disclaimer ("This is an automated newsletter, written by Claude, based on news coverage scraped from N websites" — N is `monitored_source_count` from Stage 3.5, a count of `config/sources.json`, never guessed by the reporter), then containing:
1. **This Week** — 3–5 bullets on what's new or updated this run
2. **The Numbers** — quarter/year running totals (computed deterministically by Stage 3.5, by `announcement_date`; Stage 3.5 refuses to run at all if a duplicate is still unresolved, so there is never a pending pair left to double-count) with explicit revision deltas for backfilled deals, plus a brief stage/sector/geography narrative
3. **Deal Spotlight** — 1–2 deep write-ups on the most notable deals this run
4. **Sources** — links to the news articles behind this run's new-or-updated deals. A standing, continuously updated full source list is planned as a separate reference page to link from here, but doesn't exist yet
5. **Notes** — low-confidence records, data notes, and caveats (stated once, in plain prose)

Full per-VC historical profiles are *not* rebuilt in the weekly report — see [Managing VC profiles](#managing-vc-profiles) below for the standing reference instead.


## Running the agent
If asked to "run the agent", execute the full pipeline in sequence using the Agent tool, with a gate check after each stage. Stop and report failure if any gate fails — do not proceed to the next stage (except Stage 1a, which has a soft gate — see below).

**Stage 1** has two sub-steps: **Stage 1a** (Fetcher, Python) and **Stage 1b** (Scraper, Claude agent). **Stage 3.5** (Report Stats) and **Stage 3.6** (Chart Generator) are pure Python steps that run between the deduplicator and the reporter — see below for why. **Stage 4** (reporter) is a Claude agent. **Stage 5** (VC profiler) has a Python stats step and a Claude agent step, same shape as Stage 1. **Stage 6** (Deal Table Generator) is a pure Python step that runs after Stage 5. **Stage 7** (Investor Page Generator) is a pure Python step that runs after Stage 6. **Stage 8** (Landing Page Generator) is a pure Python step that runs after Stage 7. **Stage 9** (git commit + push) and **Stage 10** (Buttondown draft) are the final two steps, both soft.
**Stages 2, 3, 3.5, 3.6, 6, 7, and 8** are Python — run them with the relevant `python pipeline/<script>.py` command via the Bash tool. Stages 2, 3, 3.5, and 3.6 accept an optional `--date YYYY-MM-DD` argument; omit it to default to today. Stages 6, 7, and 8 take no arguments.

**How to invoke agent stages:** Use the Agent tool with `subagent_type: "general-purpose"`. Read the body of the relevant `.claude/agents/<stage>.md` file (everything after the second `---` frontmatter delimiter) and use it as the prompt, prepending `Today's date is YYYY-MM-DD.` with today's actual date substituted.

**`pipeline/run.py`** orchestrates the full pipeline (including Stages 3.5 and 3.6) in one command (`python pipeline/run.py [--date YYYY-MM-DD]`) for unattended use. In practice this project runs on Phill's own laptop, not a server or cron job — there is no scenario where a run happens without Phill present, so the synchronous duplicate-review behaviour in [Reviewing merge candidates](#reviewing-merge-candidates) always applies in full; `run.py` existing as a script doesn't change that.

### Pre-launch backfill
Run this **once**, before the first official weekly run, to populate the ledger with historical deals without polluting Monday's "This Week" section. Trigger phrase: **"run pre-launch backfill"**.

Sequence (Stages 1–3 only — do **not** proceed to Stage 3.5 or beyond):

1. **Stage 1a** — `source .venv/bin/activate && python pipeline/fetcher.py`
2. **Stage 1b** — scraper agent (same as normal run)
3. **Stage 2** — `source .venv/bin/activate && python pipeline/parser.py`
4. **Pre-launch filter** — `source .venv/bin/activate && python pipeline/prelaunch_filter.py`
   - Removes records where `announcement_date` is within the past 7 days from `investments.json`
   - Print output shows exactly which deals were removed — confirm with Phill before proceeding
   - Gate: script exits non-zero on error; if no records remain after filtering, stop and tell Phill
5. **Stage 3** — `source .venv/bin/activate && python pipeline/deduplicator.py`
   - Resolve any merge candidates immediately as normal
   - Gate: `data/processed/investments_deduped.json` must exist

**Stop after Stage 3.** Do not run Stage 3.5 (report_stats.py) — that would create a `report_history.json` entry dated today, which would make Monday's delta look like "deals added since today" rather than being a clean first-run baseline.

The removed records (past 7 days) are still in `data/raw/` — Monday's scraper will re-find them and Stage 3 will pick them up as `new`, giving Monday's "This Week" section a clean week of fresh deals.

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

This stage also writes/updates `data/processed/merge_candidates.json` — see [Dedup confidence policy](#dedup-confidence-policy) below. If this run added any new pending entries, **stop here and resolve them with Phill immediately** (same process as [Reviewing merge candidates](#reviewing-merge-candidates) below) before proceeding to Stage 3.5. Do not just mention the count and continue — the reporter should never be the first place a new duplicate surfaces.

### Stage 3.5 — Report Stats (Python)
Run: `python pipeline/report_stats.py` (or `python pipeline/report_stats.py --date YYYY-MM-DD`)

**Gate**: `data/processed/report_stats.json` must exist.
If the gate fails because of an exception, check whether it's the pending-duplicate hard gate (below) before treating it as a generic failure. Otherwise, stop, tell Phill report stats failed to produce output. Do not let the reporter fall back to computing its own totals from the ledger — that's exactly the failure mode this stage exists to prevent (see below).

This stage exists because LLM agents are unreliable at exactly the kind of deterministic bookkeeping "The Numbers" section needs — in practice, the reporter repeatedly double-counted a pending duplicate when computing totals straight from the ledger itself, even with explicit instructions and `merge_candidates.json` right there to check. `report_stats.py` computes every number that section needs in Python instead: quarter/year deal count and capital, investor rankings, stage/sector/location mix, and the revision delta against the previous issue. It also maintains `data/processed/report_history.json`, a small persistent record of each run's stated totals — so next week's delta is computed from structured history, not by an agent re-reading last week's markdown and hoping it extracts the right numbers. The reporter (Stage 4) must treat `report_stats.json` as the sole source for these figures; see `.claude/agents/reporter.md`.

Alongside `sector_mix` (this quarter's deal count per sector, used in the reporter's narrative paragraph), this stage also computes `sector_capital_mix` (this quarter's capital deployed per sector) and the year-to-date equivalents `ytd_sector_mix` / `ytd_sector_capital_mix`, all four feeding the `_sector.png` chart below. A deal with multiple `company_sectors` contributes its full amount to every sector it's tagged with, so summing any of these capital breakdowns across sectors over-counts the real total — always use `quarter_capital_gbp_millions` / `ytd_capital_gbp_millions` for the actual total, never a sum over the per-sector breakdown.

**Pending-duplicate hard gate**: `report_stats.py` refuses to run — raising an error instead of producing output — if `merge_candidates.json` contains any `status: "pending"` entry. By policy there should never be one at this point: Stage 3's gate above already requires resolving any new pending entry with Phill immediately, before Stage 3.5 ever runs. If this gate fires, it means that step was skipped — stop, resolve the pending pair(s) with Phill now (merge, fix the underlying data, or explicitly mark them as separate deals — same process as [Reviewing merge candidates](#reviewing-merge-candidates)), then re-run `report_stats.py`. Do not add logic to `report_stats.py` that counts around an unresolved pair — that reintroduces the exact failure mode this gate exists to catch.

### Stage 3.6 — Chart Generator (Python)
Run: `python pipeline/chart_generator.py` (or `python pipeline/chart_generator.py --date YYYY-MM-DD`)

**Gate**: `data/reports/charts/YYYY-MM-DD_stage.png` and `_sector.png` must both exist.
If the gate fails: stop, tell Phill chart generation failed, and do not let the reporter proceed without the charts (it would either skip them or, worse, invent a description of a chart it can't see).

Chart implementation and styling is fully encoded in `pipeline/chart_generator.py` and `pipeline/chart_style.py` — read those files if you need to understand or modify chart behaviour. The reporter (Stage 4) embeds the two PNGs as-is. If you ever need to change a chart's look, follow the `matplotlib-render-review` skill's render → Read the PNG → refine workflow rather than judging the styling from code alone.

### Stage 4 — Reporter
Agent tool: `subagent_type: "general-purpose"`, prompt = today's date + body of `.claude/agents/reporter.md`

**Gate**: A file matching `data/reports/YYYY-MM-DD_vc-report.md` (today's date) must exist.
If the gate fails: stop, tell Phill the reporter did not produce a report.

### Stage 5 — VC Profiler (Python + Claude agent)
Refreshes `data/vc-profiles/` for VCs that were active this run — see [Managing VC profiles](#managing-vc-profiles) for what this is and why it's separate from the weekly report.

1. Run: `python pipeline/vc_profile_stats.py --active-in data/processed/investments_deduped.json` (writes `data/processed/vc_stats.json`)
2. If `vc_stats.json` is an empty array, skip the agent step — no known VCs were active this run.
3. Otherwise, Agent tool: `subagent_type: "general-purpose"`, prompt = today's date + body of `.claude/agents/vc-profiler.md`

**Gate (soft)**: Every VC named in `vc_stats.json` has a `data/vc-profiles/<slug>.md` with today's date in `last_updated`. If this fails, tell Phill which VCs didn't get refreshed but do not block the run — the report has already been written by this point and profiles are reference data, not the deliverable.

### Stage 6 — Deal Table Generator (Python)
Run: `python pipeline/deal_table_generator.py` (or `python pipeline/deal_table_generator.py --date YYYY-MM-DD`)

Reads `data/processed/ledger.json`, filters to the current quarter and YTD, and writes a self-contained static HTML page to `docs/deals/index.html`. All data is embedded in the HTML as a JavaScript variable — no backend or external fetch needed. The page includes live search, filter dropdowns (stage, sector, location, confidence), sortable columns, and a stats bar. Served via GitHub Pages at `/deals/`.

**Gate (soft)**: `docs/deals/index.html` must exist. If it fails, log a warning but do not block — the weekly report is already complete by this point and the deal table is a web supplement, not the primary deliverable.

### Stage 7 — Investor Page Generator (Python)
Run: `python pipeline/investor_page_generator.py`

Reads `data/processed/ledger.json`, `config/known_vcs.json`, and `data/vc-profiles/*.md`. Aggregates per-investor stats (deal count, lead count, capital, sectors, stages, date range) and writes a self-contained static HTML page to `docs/investors/index.html`. The page includes two inline canvas bar charts (top 5 investors by deal count and capital), a sortable/searchable investor table, and click-through accordion profile cards showing the narrative from `data/vc-profiles/`. No external dependencies. Served via GitHub Pages at `/investors/`.

**Gate (soft)**: `docs/investors/index.html` must exist. If it fails, log a warning but do not block.

### Stage 8 — Landing Page Generator (Python)
Run: `python pipeline/landing_page_generator.py`

Reads the latest `data/reports/YYYY-MM-DD_vc-report.md`, copies the associated chart PNGs to `docs/charts/`, converts the report markdown to HTML, and writes `docs/index.html` — the public-facing landing page served at the GitHub Pages root. The page includes the site title and description, nav cards to `/deals/` and `/investors/`, a Buttondown subscribe CTA with an archive link, and the full latest issue rendered inline. No external dependencies.

**Gate (soft)**: `docs/index.html` must exist. If it fails, log a warning but do not block.

### Stage 9 — Git commit + push (Python, via subprocess in run.py)
Not a standalone script. `run.py` runs `git add docs/` → `git commit -m "Weekly report: YYYY-MM-DD"` → `git push origin main` after Stage 8. Only `docs/` is committed — data files (ledger, reports, vc-profiles) are not touched and must be committed manually by Phill after review. The commit hash is written into `data/processed/publish_manifest_YYYY-MM-DD.json` for use by the rollback.

**Gate (soft)**: warns on failure but does not block. If Stage 9 fails, GitHub Pages is not updated this run — push manually or investigate with `git status`.

### Stage 10 — Buttondown draft (Python)
Run standalone: `python pipeline/newsletter_publish.py [--date YYYY-MM-DD]`

Uploads the two chart PNGs to ImgBB (Buttondown's API doesn't accept file attachments), rewrites local chart paths to ImgBB URLs, and creates a Buttondown draft (`status: "draft"` — nothing goes to subscribers until Phill sends from the dashboard). Writes `data/processed/publish_manifest_YYYY-MM-DD.json` with the draft ID and ImgBB delete URLs so `pipeline/rollback.py` can undo the publish. Requires `IMGBB_API_KEY` and `BUTTONDOWN_API_KEY` in `.env`.

**Gate (soft)**: warns on failure but does not block. If Stage 10 fails, publish manually with `python pipeline/newsletter_publish.py`.

### Rolling back a run
Run: `python pipeline/rollback.py [--date YYYY-MM-DD]`

Reads `data/processed/publish_manifest_YYYY-MM-DD.json` and undoes the publish in three steps:
1. Attempts to delete ImgBB images via their delete URLs (best-effort — prints the URL for manual deletion if the automated request fails)
2. Calls `DELETE /v1/emails/{id}` on the Buttondown API to remove the draft
3. `git revert {commit_hash} --no-edit` + `git push origin main` — creates a revert commit rather than force-pushing, so history stays clean and GitHub Pages rolls back safely

**Data files are not touched.** The ledger, report markdown, vc-profiles, merge_candidates, and report_history are all left intact so you can fix the data and re-run without starting the pipeline from scratch.

Report output lands in `data/reports/`. Static web pages land in `docs/`. Anything else is development work.

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
│       ├── reporter.md          ← Stage 4: Claude agent prompt
│       └── vc-profiler.md       ← Stage 5: Claude agent prompt
│
├── pipeline/
│   ├── __init__.py
│   ├── run.py                   ← Pipeline entry point
│   ├── fetcher.py               ← Stage 1a: Fetch + keyword-filter (Python)
│   ├── parser.py                ← Stage 2: Normalisation (Python)
│   ├── deduplicator.py          ← Stage 3: Deduplication + ledger (Python)
│   ├── report_stats.py          ← Stage 3.5: Deterministic report numbers (Python) — see Dedup confidence policy
│   ├── chart_generator.py       ← Stage 3.6: Report charts (Python) — minimalist consulting style
│   ├── chart_style.py           ← Shared matplotlib styling for chart_generator.py
│   ├── vc_profile_stats.py      ← Stage 5: Per-VC stats aggregation (Python)
│   ├── deal_table_generator.py  ← Stage 6: Static deal table HTML (Python)
│   ├── investor_page_generator.py ← Stage 7: Static investor page HTML (Python)
│   ├── landing_page_generator.py ← Stage 8: Landing page HTML (Python)
│   ├── newsletter_publish.py     ← Stage 10: Buttondown draft + ImgBB upload (Python)
│   └── rollback.py               ← Undo a publish: delete ImgBB images, delete draft, revert GitHub Pages
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
│   │   ├── ledger.json          ← PERSISTENT: all-time historical record
│   │   ├── merge_candidates.json ← PERSISTENT: pending/resolved duplicate pairs awaiting review
│   │   ├── report_stats.json    ← Stage 3.5 output (this run) — transient, the reporter's sole source for computed figures
│   │   ├── report_history.json  ← PERSISTENT: each run's stated totals, for next run's revision delta
│   │   └── vc_stats.json        ← Stage 5 stats output (this run/request) — transient
│   └── reports/                 ← Final Markdown reports
│       └── charts/              ← Stage 3.6 output — stage + sector PNGs per run, transient
│
├── data/
│   ├── raw/                     ← Scraper output (per-source JSON files)
│   ├── processed/               ← Parser and deduplicator output
│   └── vc-profiles/             ← PERSISTENT: one standing reference page per VC, refreshed by Stage 5
│
└── docs/                        ← GitHub Pages web root (served at philljones284.github.io/scottish-vc-tracker/)
    └── deals/
        └── index.html           ← Stage 6 output: static deal table, overwritten each run
    └── investors/
    │   └── index.html           ← Stage 7 output: static investor page, overwritten each run
    └── charts/
    │   └── YYYY-MM-DD_*.png     ← Stage 8 copies charts here from data/reports/charts/
    └── index.html               ← Stage 8 output: landing page, overwritten each run
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
| `data/processed/merge_candidates.json` | Persistent — pending/resolved probable/possible duplicate pairs; do not delete |
| `data/processed/report_stats.json` | Stage 3.5 output — quarter/year totals, rankings, breakdowns, revision delta; transient, overwritten each run; reporter's sole source for these figures |
| `data/processed/report_history.json` | Persistent — one entry per run's stated totals, used to compute the next run's revision delta; do not delete |
| `data/processed/vc_stats.json` | Stage 5 stats for VCs being refreshed — transient, overwritten per run/request |
| `data/reports/charts/YYYY-MM-DD_stage.png` | Stage 3.6 output — this quarter's deals by stage; transient, overwritten each run |
| `data/reports/charts/YYYY-MM-DD_sector.png` | Stage 3.6 output — this quarter's deals by sector; transient, overwritten each run |
| `data/reports/YYYY-MM-DD_vc-report.md` | Weekly intelligence report — one file per run |
| `data/vc-profiles/<slug>.md` | Standing per-VC reference profile — persistent, refreshed selectively |
| `docs/deals/index.html` | Stage 6 output — static deal table for GitHub Pages; overwritten each run |
| `docs/investors/index.html` | Stage 7 output — static investor page for GitHub Pages; overwritten each run |
| `docs/charts/YYYY-MM-DD_*.png` | Stage 8 copies these from `data/reports/charts/` so the landing page can reference them |
| `docs/index.html` | Stage 8 output — landing page for GitHub Pages; overwritten each run |
| `data/processed/publish_manifest_YYYY-MM-DD.json` | Stage 10 output — Buttondown draft ID, ImgBB delete URLs, git commit hash; used by rollback.py |

## Key design decisions
- Agents communicate via JSON files in `data/`, not stdout
- `data/processed/ledger.json` is the persistent source of truth across runs — treat it carefully
- Every investment record has a `confidence` field (high/medium/low) — do not collapse these
- `config/known_vcs.json` uses `canonical_name` as a key — do not rename existing entries
- Deduplication is conservative: when in doubt, flag for review rather than merge — concretely, the deduplicator's three-tier match confidence (`definite` / `probable` / `possible`) only **auto-merges `definite` matches**. `probable` and `possible` matches are never auto-merged and never silently dropped — they're staged in `data/processed/merge_candidates.json` for Phill to approve or dismiss. See [Dedup confidence policy](#dedup-confidence-policy)
- Investment record IDs follow the format `{normalised-company-name}_{round-type}_{announcement-date}` (e.g. `wallet-ai_series-a_2026-03-15`) — set by the parser, referenced by the deduplicator; must be consistent between stages
- `company_sectors` is an **array**, not a string — a company can belong to multiple sectors; the parser collects all taxonomy matches and the deduplicator unions arrays across runs (sectors accumulate, never overwrite)
- Anything that needs to be deterministically correct — arithmetic, deduplication-aware counting, chart rendering — is computed in Python (Stage 3.5 `pipeline/report_stats.py`, Stage 3.6 `pipeline/chart_generator.py`), never delegated to an LLM agent's prompt-following. The reporter only narrates numbers and embeds charts it's given; see [Stage 3.5](#stage-35--report-stats-python) and [Stage 3.6](#stage-36--chart-generator-python)

## Dedup confidence policy

The deduplicator (Stage 3) scores any potential duplicate pair — within a single run's records, or a new record against the historical ledger — as `definite`, `probable`, `possible`, or no match. Only `definite` is auto-merged. This used to be looser (`probable` auto-merged too, and `possible` against the ledger was silently treated as no match at all, which is how two JET Connectivity records ended up as separate ledger entries). Now:

- **`definite`** — auto-merged immediately, no review needed (exact ID match, or same company + round + dates within 60 days, or same company + same amount + overlapping investors)
- **`probable`** — same company + round but a missing date, or same company + overlapping investors within 90 days. Staged in `data/processed/merge_candidates.json`, not merged
- **`possible`** — same company name but a different round type, or a fuzzy name match (80–89 similarity). Staged in `data/processed/merge_candidates.json`, not merged

`merge_candidates.json` is **persistent** (like the ledger) — it's an audit trail of what's been found and how it was resolved, not a queue for deferring review. New pending entries should be resolved with Phill immediately, in the same session they're found (see below); the file is just a safety net so nothing is silently lost if that doesn't happen. Each entry has `record_a`, `record_b`, `match_type`, `scope` (`within_run` or `against_ledger`), a `note` explaining why it matched, and `status` (`pending` until resolved).

**The reporter checks this file before writing each week** so pending pairs never get double-counted or silently published as two separate deals — see `.claude/agents/reporter.md`.

### Reviewing merge candidates
Whenever a new entry lands in `data/processed/merge_candidates.json` — during a pipeline run, a manual investigation, or anything else — resolve it with Phill immediately, in that same session, rather than silently staging it and moving on. Phill should never have to remember to ask for a review; surfacing it proactively is Claude's job, every time. Go through new (and any other still-`pending`) entries one by one: show both records side by side, explain the `match_type` and `note`, and ask whether to merge them (do it the same way as any manual ledger merge — newer extraction's fields win, `first_seen` keeps the earliest date, `last_seen` keeps the latest, `source_urls` union, `confidence` reassessed from the combined evidence, `merge_confidence: "definite"`) or dismiss the pair (set `status: "dismissed"`, leave both ledger records as-is). Never leave a pair silently unresolved across multiple reviews — always end with `pending`, `merged`, or `dismissed`.

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

## Managing VC profiles

`data/vc-profiles/` holds a standing, per-VC reference page — one file per firm (`<slug>.md`, where slug is the canonical name lowercased and hyphenated). This is separate from the weekly report's "Deal Spotlight": it accumulates a firm's full Scottish history over time rather than being rebuilt from scratch every week.

**Automatic refresh**: Stage 5 of the pipeline refreshes a VC's profile whenever that VC appears in a weekly run (see Stage 5 above). VCs not active in a given run are left untouched — a profile only goes stale in proportion to how inactive that firm actually is.

**Manual refresh**: Phill can ask for this directly:
- "refresh profile for `<VC name>`" — refreshes just that VC
- "refresh profiles for `<VC1>`, `<VC2>`, ..." — refreshes several
- "refresh all VC profiles" — refreshes every VC in `config/known_vcs.json`

To do this, run the stats step, then the agent step:
```bash
python pipeline/vc_profile_stats.py "<VC name>" ["<VC name 2>" ...]   # one or more named VCs
python pipeline/vc_profile_stats.py --all                              # every known VC
```
This writes `data/processed/vc_stats.json`. Then invoke the agent: `subagent_type: "general-purpose"`, prompt = today's date + body of `.claude/agents/vc-profiler.md`.

The profiler only rewrites files for VCs present in `vc_stats.json` for that invocation — every other file in `data/vc-profiles/` is left alone.

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

## Python execution

Always activate the virtual environment before running any Python command or `pip install`:

```bash
source .venv/bin/activate && <command>
```

This ensures `python` and `pip` both resolve to `.venv`, not the global install. Never run Python or pip without activating first.

## Development ground rules
- Propose changes and wait for approval before modifying any file
- When proposing a change, explain what you're changing and why
- If you spot something worth improving that's outside the current task, note it but don't act on it
- Do not run the agent pipeline unless explicitly asked to
- You do not handle version control. All git functions will be handled manually by humans
- Python version is controlled via pyenv (.python-version)

