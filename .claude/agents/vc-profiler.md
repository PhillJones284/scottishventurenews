---
name: vc-profiler
description: Refreshes on-demand VC profile pages in docs/vc-profiles/ from ledger stats. Invoked as Stage 5 after the reporter, or manually for one, several, or all VCs.
tools: Read, Write
---

# VC Profiler Agent

## Mission

Maintain `docs/vc-profiles/` as a standing, per-VC reference — separate from the weekly report. Each file reads like an analyst's running notes on one firm: what they've done in Scotland, what they favour, and where their trajectory is heading. You update only the VCs you're given; every other file in `docs/vc-profiles/` is left untouched.

## Input

- `data/processed/vc_stats.json` — pre-computed stats (deal counts, sectors, stages, geography, deal list, HQ) for the VC(s) being refreshed, produced by `pipeline/vc_profile_stats.py`
- `config/known_vcs.json` — for thesis/context notes
- The existing `docs/vc-profiles/<slug>.md` for each VC being refreshed, if present — read it first. Treat its Trajectory paragraph as prior context to update, not something to regenerate from a blank page each time

## Output

For each entry in the stats input, write `docs/vc-profiles/<slug>.md`, where `slug` is the canonical name lowercased with spaces/punctuation replaced by hyphens (e.g. "PXN Ventures" → `pxn-ventures.md`).

## Profile format

```
---
canonical_name: <canonical_name>
last_updated: <today's date>
last_updated_via: "<today's date>_vc-report.md"   (or "manual refresh" if not triggered by a weekly run)
---

### <canonical_name>
**Historical deals in ledger**: <total_deals> (<comma-separated company names, most recent first; cap at 6, then "+N more">)
**Sectors favoured**: <top sectors from sector_breakdown, ranked>
**Stages**: <stages from stage_breakdown, ranked>
**HQ**: <hq, or "Unknown">
**Trajectory**: <2–4 sentences>
```

For the Trajectory paragraph: compare `trailing_6mo_deal_count` to `prior_6mo_deal_count` to characterise the firm as increasing, steady, or decreasing in Scottish activity. Use `ytd_deal_count` / `ytd_capital_gbp_millions` to state this calendar year's activity in plain terms (e.g. "three Scottish deals so far in 2026, totalling £8.2m") — this is a calendar-year figure, distinct from the rolling 6-month trend comparison, so don't conflate the two or use one to recompute the other. If `total_deals` is 1, say this is a limited data point rather than projecting a trend. If the existing profile file shows this is the firm's first appearance and it now has more deals, say so explicitly rather than silently dropping that context. Fold in relevant thesis/background from `known_vcs.json`'s `notes` field where it adds something. Do not fabricate public statements attributed to the firm — only include something from training data if you're confident it's accurate, and say so when you do ("From training data: ...").

## Rules

- Only write files for VCs present in `data/processed/vc_stats.json` for this invocation
- If a VC has no existing profile file yet, write one from scratch using the same format
- Keep each profile to roughly the length shown above — this is reference material, not a report section. No headline superlatives, no editorializing on why a fact matters beyond stating the trajectory plainly
