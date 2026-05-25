# Scottish VC Investment Tracker

A multi-agent system built on Claude Code that monitors freely available news sources for venture capital investment activity in Scottish scale-up companies.

## Purpose

This tool exists to answer: **Which VC firms are actively investing in Scottish companies, at what stages, in which sectors, and with what cadence?**

It produces a weekly analyst-quality intelligence report that can inform:
- Fundraising strategy (who should we approach?)
- Competitive intelligence (who is funding our competitors?)
- Ecosystem understanding (what sectors are hot in Scotland right now?)

---

## Architecture

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
└── data/
    ├── raw/                     ← Scraper output (per-source JSON files)
    ├── processed/               ← Parser and deduplicator output
    │   ├── investments.json     ← Normalised records (this run)
    │   ├── investments_deduped.json
    │   └── ledger.json          ← PERSISTENT: all-time historical record
    └── reports/                 ← Final Markdown reports
```

---

## How to Run

### Prerequisites

- [Claude Code](https://code.claude.com) installed. If you haven't already:
  ```bash
  curl https://claude.ai/install.sh | bash   # macOS / Linux
  ```
  Or via Homebrew: `brew install --cask claude-code`
- Authenticated with your Anthropic account (Pro, Max, Teams, or API key)

### Full Pipeline (recommended)

From the root directory:

```bash
cd scottish-vc-tracker
claude --print "Run the full pipeline as described in CLAUDE.md"
```

The orchestrator will invoke each subagent in sequence.

### Run a Single Stage

You can also run any agent individually:

```bash
# Just scrape
cd agents/scraper
claude --print "Run the scraper task as described in CLAUDE.md"

# Just generate a report from existing data
cd agents/reporter
claude --print "Run the reporter task as described in CLAUDE.md"
```

### Scheduled Weekly Run

Add to crontab (runs every Monday at 7am):

```cron
0 7 * * 1 cd /path/to/scottish-vc-tracker && claude --print "Run the full pipeline as described in CLAUDE.md" >> logs/run-$(date +\%Y-\%m-\%d).log 2>&1
```

---

## Configuration

### Adding New Sources

Edit `config/sources.json`. Each source needs:
- `slug`: unique identifier (used in output filenames)
- `name`: human-readable name
- `type`: `news_site | search | database | vc_newsrooms | aggregator`
- `url`: the base URL
- `notes`: what kind of deals this source covers well

### Adding Known VCs

Edit `config/known_vcs.json`. Add any VC firm you want the system to recognise and normalise. Include common aliases — the parser will use this to resolve "Octopus" → "Octopus Ventures" etc.

### Updating FX Rates

Edit `config/fx_rates.json`. These are rough conversion rates for GBP normalisation; update quarterly.

---

## Output

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

### Data Files

| File | Contents |
|---|---|
| `data/raw/*.json` | Raw scraped data per source |
| `data/processed/investments.json` | Normalised records for this run |
| `data/processed/investments_deduped.json` | Deduplicated records with new/updated flags |
| `data/processed/ledger.json` | Persistent all-time record — do not delete |
| `data/reports/YYYY-MM-DD_vc-report.md` | Weekly intelligence report — one file per run |

---

## Limitations & Caveats

- **Coverage is limited to publicly reported deals.** Many early-stage investments are never announced.
- **Amounts are often undisclosed.** Especially at Seed and Pre-Seed stage.
- **Some sources may be paywalled.** The scraper will note when it can't access content.
- **This is not financial advice.** It's an intelligence-gathering tool for ecosystem mapping.
- **VC activity ≠ VC interest.** A VC that hasn't invested in Scotland recently may still be actively evaluating Scottish companies.

---

## Extending the System

### Add a New Agent

1. Create `agents/<name>/CLAUDE.md` with a clear mission, input/output spec, and schema
2. Add the invocation step to the root `CLAUDE.md` orchestrator
3. Define what the new agent reads and writes in `data/`

### Ideas for Future Agents

- **LinkedIn Monitor**: Track when Scottish founders announce funding on LinkedIn
- **Companies House Agent**: Parse SH01 filings for Scottish companies to catch undisclosed rounds
- **VC Job Board Monitor**: Track VC job postings in Scotland as a leading indicator of activity
- **Sentiment Analyser**: Flag deals where the press coverage is unusually positive/negative

---

## Troubleshooting

**Scraper finds nothing**: Check `data/raw/errors.json`. Sources may have changed their HTML structure or URLs.

**Duplicate ledger entries**: The deduplicator uses fuzzy matching. If two genuinely different companies share a similar name, they may have been incorrectly merged. Check `flagged_for_review` in `investments_deduped.json`.

**Report is sparse**: If the report has few deals, it may be a quiet period — or the sources may not have been updated. Check the raw files for timestamps.
