#!/usr/bin/env python3
"""Investor page generator.

Reads ledger.json, known_vcs.json, and data/vc-profiles/*.md.
Writes:
  docs/investors/investors.json  — data payload (fetched by the browser at runtime)
  docs/investors/index.html      — static HTML shell (JS fetches investors.json on load)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT         = Path(__file__).parent.parent
LEDGER       = ROOT / "data" / "processed" / "ledger.json"
KNOWN_VCS    = ROOT / "config" / "known_vcs.json"
PROFILES_DIR = ROOT / "data" / "vc-profiles"
OUT_DIR      = ROOT / "docs" / "investors"
OUT_HTML     = OUT_DIR / "index.html"
OUT_JSON     = OUT_DIR / "investors.json"

# Raw investor strings to drop entirely (descriptors / personal names)
SKIP_INVESTORS: set[str] = {
    "crowdcube investors",
    "republic investors",
    "angel investors",
    "unnamed hnw investors",
    "unnamed existing and new investors",
    "existing and new investors (undisclosed)",
    "anna lagerqvist christopherson (boda bars)",
    "brad peltz",
    "david peterson",
    "gareth williams (skyscanner co-founder)",
}

# Sub-fund / long-form variants → canonical name they should fold into
MERGE_TO: dict[str, str] = {
    "maven capital partners (investment fund for scotland)": "Maven Capital Partners",
    "maven income and growth vcts":                          "Maven Capital Partners",
    "investment fund for scotland (ifs maven equity finance)": "Maven Capital Partners",
    "gu holdings ltd (university of glasgow)":               "GU Holdings",
    "british business bank":                                 "British Business Investments",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _fmt_capital(m: float | None) -> str:
    if m is None or m == 0:
        return "—"
    if m >= 1000:
        return f"£{m/1000:.1f}bn"
    if m >= 1:
        return f"£{m:.1f}m"
    return f"£{round(m * 1000)}k"


# ── data loading ──────────────────────────────────────────────────────────────

def load_known_vcs() -> tuple[dict, dict]:
    """Return (vc_by_canonical, alias_map).

    alias_map: normalised string → canonical_name
    """
    raw = json.loads(KNOWN_VCS.read_text())
    vcs: list[dict] = raw["known_vcs"]
    vc_by_canonical: dict[str, dict] = {}
    alias_map: dict[str, str] = {}
    for vc in vcs:
        canonical = vc["canonical_name"]
        vc_by_canonical[canonical] = vc
        alias_map[_norm(canonical)] = canonical
        for alias in vc.get("aliases") or []:
            alias_map[_norm(alias)] = canonical
    return vc_by_canonical, alias_map


def resolve_name(raw: str, alias_map: dict[str, str]) -> str:
    """Map a raw investor name from the ledger to its canonical form."""
    lower = raw.strip().lower()
    if lower in MERGE_TO:
        return MERGE_TO[lower]
    canonical = alias_map.get(_norm(raw))
    return canonical if canonical else raw.strip()


def load_profile(canonical_name: str) -> str | None:
    path = PROFILES_DIR / f"{_slug(canonical_name)}.md"
    if not path.exists():
        return None
    text = path.read_text().strip()
    # Strip YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()
    return text or None


# ── aggregation ───────────────────────────────────────────────────────────────

def aggregate(ledger: list[dict], vc_by_canonical: dict, alias_map: dict) -> dict[str, dict]:
    stats: dict[str, dict] = {}

    def _get(canonical: str) -> dict:
        if canonical not in stats:
            meta = vc_by_canonical.get(canonical, {})
            stats[canonical] = {
                "canonical_name": canonical,
                "hq": meta.get("hq") or "Unknown",
                "stage_focus": meta.get("stage_focus") or [],
                "notes": meta.get("notes") or "",
                "in_known_vcs": canonical in vc_by_canonical,
                "deal_count": 0,
                "lead_count": 0,
                "capital_sum": 0.0,
                "capital_deal_count": 0,
                "sectors": set(),
                "stages": set(),
                "companies": [],
                "deals": [],
                "first_active": None,
                "last_active": None,
            }
        return stats[canonical]

    for deal in ledger:
        investors  = deal.get("investors") or []
        lead_raw   = deal.get("lead_investor") or ""
        lead_canon = resolve_name(lead_raw, alias_map) if lead_raw else ""
        amount     = deal.get("amount_gbp_millions")
        date_str   = deal.get("announcement_date") or ""
        company    = deal.get("company_name") or ""
        sectors    = deal.get("company_sectors") or []
        stage      = deal.get("round_type") or ""
        src_url    = deal.get("source_url") or (deal.get("source_urls") or [None])[0]

        seen: set[str] = set()
        for raw in investors:
            if not raw:
                continue
            lower = raw.strip().lower()
            if lower in SKIP_INVESTORS:
                continue
            canonical = resolve_name(raw, alias_map)
            if canonical in seen:
                continue
            seen.add(canonical)

            s = _get(canonical)
            s["deal_count"] += 1
            is_lead = bool(lead_canon and canonical == lead_canon)
            if is_lead:
                s["lead_count"] += 1
            if amount is not None:
                s["capital_sum"] += amount
                s["capital_deal_count"] += 1
            for sec in sectors:
                if sec:
                    s["sectors"].add(sec)
            if stage:
                s["stages"].add(stage)
            if company and company not in s["companies"]:
                s["companies"].append(company)
            if date_str:
                if s["first_active"] is None or date_str < s["first_active"]:
                    s["first_active"] = date_str
                if s["last_active"] is None or date_str > s["last_active"]:
                    s["last_active"] = date_str
            s["deals"].append({
                "company":   company,
                "stage":     stage,
                "amount":    amount,
                "date":      date_str,
                "is_lead":   is_lead,
                "source_url": src_url,
            })

    for s in stats.values():
        s["sectors"] = sorted(s["sectors"])
        s["stages"]  = sorted(s["stages"])
        s["deals"].sort(key=lambda d: d["date"] or "", reverse=True)

    return stats


# ── JSON payload builder ──────────────────────────────────────────────────────

def build_json(stats: dict[str, dict], ledger: list[dict], today: str) -> dict:
    active = [s for s in stats.values() if s["deal_count"] > 0]
    active.sort(key=lambda s: (-s["deal_count"], s["canonical_name"]))

    total_vcs     = len(active)
    unique_deals  = len(ledger)
    disclosed     = [d for d in ledger if d.get("amount_gbp_millions") is not None]
    total_capital = sum(d["amount_gbp_millions"] for d in disclosed)

    top5_count   = sorted(active, key=lambda s: -s["deal_count"])[:5]
    top5_capital = sorted([s for s in active if s["capital_sum"] > 0],
                          key=lambda s: -s["capital_sum"])[:5]

    vc_list = []
    for s in active:
        vc_list.append({
            "canonical_name":     s["canonical_name"],
            "hq":                 s["hq"],
            "stage_focus":        s["stage_focus"],
            "deal_count":         s["deal_count"],
            "lead_count":         s["lead_count"],
            "capital_sum":        round(s["capital_sum"], 3),
            "capital_deal_count": s["capital_deal_count"],
            "sectors":            s["sectors"],
            "stages":             s["stages"],
            "companies":          s["companies"],
            "first_active":       s["first_active"],
            "last_active":        s["last_active"],
            "profile":            load_profile(s["canonical_name"]),
            "deals":              s["deals"],
        })

    return {
        "generated":     today,
        "total_vcs":     total_vcs,
        "unique_deals":  unique_deals,
        "total_capital": _fmt_capital(total_capital),
        "vcs": vc_list,
        "chart_deals":   [{"name": s["canonical_name"], "value": s["deal_count"]}
                          for s in top5_count],
        "chart_capital": [{"name": s["canonical_name"], "value": round(s["capital_sum"], 2)}
                          for s in top5_capital],
    }


# ── HTML shell — no data embedded; JS fetches investors.json at runtime ───────

_SHELL = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scottish Venture News — Investor Directory</title>
  <style>
    :root {
      --navy:       #1F3B57;
      --slate:      #7C93A8;
      --grey:       #9AA0A6;
      --light-grey: #D8DCE0;
      --blue:       #7B9EB9;
      --green:      #6BA58A;
      --gold:       #C49A5A;
      --maroon:     #A07878;
      --tan:        #A89B8C;
      --ink:        #222222;
      --bg:         #F7F7F6;
      --white:      #FFFFFF;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 13px;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.45;
    }
    a { color: inherit; text-decoration: none; }
    .container { max-width: 1280px; margin: 0 auto; padding: 28px 20px 48px; }

    /* header */
    header { margin-bottom: 24px; }
    header h1 { font-size: 20px; font-weight: 700; color: var(--navy); letter-spacing: -0.01em; }
    header p  { color: var(--slate); font-size: 12px; margin-top: 5px; }

    /* stats bar */
    .stats-bar {
      display: flex; flex-wrap: wrap; gap: 0;
      margin-bottom: 20px;
      background: var(--white); border: 1px solid var(--light-grey); border-radius: 6px; overflow: hidden;
    }
    .stat { flex: 1; min-width: 110px; padding: 12px 18px; border-right: 1px solid var(--light-grey); }
    .stat:last-child { border-right: none; }
    .stat-value { font-size: 20px; font-weight: 700; color: var(--navy); }
    .stat-label { font-size: 10px; color: var(--slate); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }

    /* charts */
    .charts-row {
      display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap;
    }
    .chart-box {
      flex: 1; min-width: 300px;
      background: var(--white); border: 1px solid var(--light-grey); border-radius: 6px;
      padding: 16px 16px 12px;
    }
    .chart-title {
      font-size: 10px; font-weight: 600; color: var(--slate);
      text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;
    }
    canvas { display: block; width: 100%; }

    /* controls */
    .controls {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px;
    }
    .controls input[type="text"] {
      padding: 6px 10px; border: 1px solid var(--light-grey); border-radius: 4px;
      font-size: 13px; width: 230px; background: var(--white); outline: none;
    }
    .controls input[type="text"]:focus { border-color: var(--blue); }
    .controls select {
      padding: 6px 8px; border: 1px solid var(--light-grey); border-radius: 4px;
      font-size: 12px; color: var(--ink); background: var(--white); cursor: pointer; outline: none;
    }
    .controls select:focus { border-color: var(--blue); }
    .btn-reset {
      padding: 6px 12px; border: 1px solid var(--light-grey); border-radius: 4px;
      background: var(--white); color: var(--slate); font-size: 12px; cursor: pointer;
    }
    .btn-reset:hover { color: var(--ink); border-color: var(--grey); }
    .result-count { color: var(--slate); font-size: 12px; margin-left: auto; }

    /* table */
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; background: var(--white); border: 1px solid var(--light-grey); border-radius: 6px; overflow: hidden; min-width: 860px; }
    thead th {
      text-align: left; padding: 9px 12px; font-size: 10px; font-weight: 600;
      color: var(--slate); text-transform: uppercase; letter-spacing: 0.06em;
      background: #F0F1F2; border-bottom: 1px solid var(--light-grey);
      white-space: nowrap; cursor: pointer; user-select: none;
    }
    thead th.no-sort { cursor: default; }
    thead th:hover:not(.no-sort) { color: var(--navy); }
    .sort-icon { color: var(--light-grey); margin-left: 3px; font-style: normal; }
    th.sort-asc .sort-icon, th.sort-desc .sort-icon { color: var(--navy); }
    tbody tr.data-row { border-bottom: 1px solid var(--light-grey); transition: background 0.08s; cursor: pointer; }
    tbody tr.data-row:hover { background: #F4F5F6; }
    tbody tr.data-row.open { background: #EEF2F6; }
    tbody tr.profile-row td { padding: 0; border-bottom: 1px solid var(--light-grey); }
    td { padding: 9px 12px; vertical-align: top; }
    .vc-name { font-weight: 600; color: var(--navy); }
    .hq-cell { color: var(--slate); font-size: 12px; white-space: nowrap; }
    .num-cell { font-weight: 600; color: var(--navy); }
    .num-sub  { font-size: 11px; color: var(--slate); font-weight: 400; }
    .capital-nil { color: var(--grey); font-style: italic; }
    .stage-tag {
      display: inline-block; padding: 1px 6px; border-radius: 3px;
      background: #ECF1F7; color: var(--navy); font-size: 10px; font-weight: 600;
      margin: 1px 2px 1px 0; white-space: nowrap;
    }
    .sector-tag {
      display: inline-block; padding: 1px 6px; border-radius: 3px;
      background: var(--light-grey); color: var(--slate); font-size: 10px;
      margin: 1px 2px 1px 0; white-space: nowrap;
    }
    .date-cell { color: var(--slate); font-size: 12px; white-space: nowrap; }

    /* profile card */
    .profile-card {
      background: #EEF2F6; border-top: 2px solid var(--blue);
      padding: 20px 24px; display: flex; gap: 32px; flex-wrap: wrap;
    }
    .profile-narrative { flex: 2; min-width: 280px; }
    .profile-narrative h4 { font-size: 14px; font-weight: 700; color: var(--navy); margin-bottom: 10px; }
    .profile-narrative .kv { margin-bottom: 4px; font-size: 12px; }
    .profile-narrative .kv strong { color: var(--navy); }
    .profile-narrative .trajectory { margin-top: 10px; font-size: 12px; color: var(--ink); line-height: 1.55; }
    .profile-no-narrative { font-size: 12px; color: var(--grey); font-style: italic; }
    .profile-deals { flex: 1; min-width: 240px; }
    .profile-deals h5 {
      font-size: 10px; font-weight: 600; color: var(--slate);
      text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;
    }
    .deal-row { display: flex; gap: 8px; margin-bottom: 6px; align-items: baseline; }
    .deal-company { font-size: 12px; font-weight: 600; color: var(--navy); flex: 1; }
    .deal-meta    { font-size: 11px; color: var(--slate); white-space: nowrap; }
    .deal-lead    { font-size: 10px; color: var(--blue); font-weight: 600; margin-left: 4px; white-space: nowrap; }
    .deal-link    { color: var(--blue); font-size: 13px; margin-left: 4px; }
    .deal-link:hover { color: var(--navy); }

    /* loading / error */
    .status-msg {
      text-align: center;
      padding: 48px 24px;
      color: var(--grey);
      background: var(--white);
      border: 1px solid var(--light-grey);
      border-radius: 6px;
    }

    /* no results */
    .no-results {
      display: none; text-align: center; padding: 48px 24px; color: var(--grey);
      background: var(--white); border: 1px solid var(--light-grey); border-radius: 6px;
    }

    /* footer */
    footer { margin-top: 20px; color: var(--grey); font-size: 11px; text-align: right; }
    .back-link { font-size: 12px; color: var(--slate); margin-bottom: 20px; display: inline-block; }
    .back-link:hover { color: var(--navy); text-decoration: none; }
  </style>
</head>
<body>
<div class="container">

  <a class="back-link" href="../">← Scottish Venture News</a>

  <header>
    <h1>Scottish VC Investors</h1>
    <p>Automated pipeline &nbsp;·&nbsp; Generated <span id="generated-date">—</span> &nbsp;·&nbsp; Source: public news coverage</p>
  </header>

  <div class="stats-bar">
    <div class="stat">
      <div class="stat-value" id="stat-total-vcs">—</div>
      <div class="stat-label">Investors tracked</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-unique-deals">—</div>
      <div class="stat-label">Deals (all time)</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-total-capital">—</div>
      <div class="stat-label">Capital deployed</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-repeat">—</div>
      <div class="stat-label">Repeat investors</div>
    </div>
  </div>

  <div class="charts-row">
    <div class="chart-box">
      <div class="chart-title">Top investors by deal count</div>
      <canvas id="chart-deals"></canvas>
    </div>
    <div class="chart-box">
      <div class="chart-title">Top investors by capital deployed</div>
      <canvas id="chart-capital"></canvas>
    </div>
  </div>

  <div class="controls">
    <input type="text" id="search" placeholder="Search investor, sector…" autocomplete="off">
    <select id="filter-stage"><option value="">All stages</option></select>
    <select id="filter-hq"><option value="">All HQ locations</option></select>
    <button class="btn-reset" id="btn-reset">Reset</button>
    <span class="result-count" id="result-count"></span>
  </div>

  <div id="status-wrap" class="status-msg">Loading investors…</div>

  <div id="table-wrap" style="display:none">
    <div class="table-wrap">
      <table id="inv-table">
        <thead>
          <tr>
            <th data-col="canonical_name">Investor<i class="sort-icon">↕</i></th>
            <th data-col="hq">HQ<i class="sort-icon">↕</i></th>
            <th data-col="deal_count">Deals<i class="sort-icon">↕</i></th>
            <th data-col="capital_sum">Capital<i class="sort-icon">↕</i></th>
            <th class="no-sort">Stage Focus</th>
            <th class="no-sort">Top Sectors</th>
            <th data-col="last_active">Last Active<i class="sort-icon">↕</i></th>
          </tr>
        </thead>
        <tbody id="inv-tbody"></tbody>
      </table>
      <div class="no-results" id="no-results">No investors match your filters.</div>
    </div>
  </div>

  <footer>Scottish Venture News &nbsp;·&nbsp; Data sourced from public news coverage only &nbsp;·&nbsp; Not investment advice</footer>

</div>
<script>
let DATA = null;

// ── chart drawing ────────────────────────────────────────────────────────────
const PALETTE = ["#5B7FA0","#6BA58A","#C49A5A","#A07878","#8C9B8A"];
const LOGICAL_W = 480, LOGICAL_H = 220;
const PAD_L = 200, PAD_R = 70, PAD_T = 8, PAD_B = 16;
const BAR_H = 22, BAR_GAP = 14;

function drawChart(canvasId, items, fmtVal) {
  const el  = document.getElementById(canvasId);
  const dpr = window.devicePixelRatio || 1;
  el.width  = LOGICAL_W * dpr;
  el.height = LOGICAL_H * dpr;
  el.style.width  = LOGICAL_W + "px";
  el.style.height = LOGICAL_H + "px";
  const ctx = el.getContext("2d");
  ctx.scale(dpr, dpr);

  const chartW = LOGICAL_W - PAD_L - PAD_R;
  const maxVal = Math.max(...items.map(d => d.value), 1);

  items.forEach((d, i) => {
    const y    = PAD_T + i * (BAR_H + BAR_GAP);
    const barW = (d.value / maxVal) * chartW;

    ctx.fillStyle = PALETTE[i % PALETTE.length];
    ctx.beginPath();
    ctx.roundRect(PAD_L, y, barW, BAR_H, 3);
    ctx.fill();

    ctx.fillStyle = "#222";
    ctx.font = "11px 'Helvetica Neue', Helvetica, Arial, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    const label = d.name.length > 26 ? d.name.slice(0, 24) + "…" : d.name;
    ctx.fillText(label, PAD_L - 8, y + BAR_H / 2);

    ctx.fillStyle = "#7C93A8";
    ctx.font = "bold 11px 'Helvetica Neue', Helvetica, Arial, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(fmtVal(d.value), PAD_L + barW + 6, y + BAR_H / 2);
  });
}

// ── formatting helpers ───────────────────────────────────────────────────────
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function fmtDate(d) {
  if (!d) return "—";
  const [y, m, day] = d.split("-");
  return `${parseInt(day)} ${MONTHS[+m-1]} ${y}`;
}
function fmtCapital(m) {
  if (!m) return null;
  if (m >= 1000) return "£" + (m/1000).toFixed(1) + "bn";
  if (m >= 1)    return "£" + m.toFixed(1) + "m";
  return "£" + Math.round(m * 1000) + "k";
}

// ── markdown-ish profile renderer ────────────────────────────────────────────
function renderProfile(text) {
  if (!text) return '<p class="profile-no-narrative">No profile available yet.</p>';
  const lines = text.split("\n");
  let html = "";
  let inTrajectory = false;
  lines.forEach(line => {
    if (line.startsWith("### ")) {
      html += `<h4>${esc(line.slice(4))}</h4>`;
    } else if (line.startsWith("**Trajectory**:")) {
      inTrajectory = true;
      const body = line.replace("**Trajectory**:", "").trim();
      html += `<div class="trajectory"><strong>Trajectory:</strong> ${esc(body)}`;
    } else if (inTrajectory && line.trim()) {
      html += " " + esc(line.trim());
    } else if (inTrajectory && !line.trim()) {
      html += "</div>";
      inTrajectory = false;
    } else if (line.match(/^\*\*[^*]+\*\*:/)) {
      const m = line.match(/^\*\*([^*]+)\*\*:(.*)/);
      if (m) html += `<div class="kv"><strong>${esc(m[1])}:</strong>${esc(m[2])}</div>`;
    }
  });
  if (inTrajectory) html += "</div>";
  return html;
}
function esc(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── table state ──────────────────────────────────────────────────────────────
let sortCol = "deal_count", sortDir = -1;
let searchQuery = "", filterStage = "", filterHq = "";
let openRow = null;

function applyFilters() {
  const q = searchQuery.toLowerCase();
  return DATA.filter(d => {
    if (filterStage && !(d.stage_focus || []).includes(filterStage)) return false;
    if (filterHq && d.hq !== filterHq) return false;
    if (q) {
      const hay = [
        d.canonical_name, d.hq,
        (d.sectors || []).join(" "),
        (d.stage_focus || []).join(" "),
        (d.companies || []).join(" "),
      ].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function applySort(rows) {
  return [...rows].sort((a, b) => {
    let va = a[sortCol] ?? "", vb = b[sortCol] ?? "";
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return -sortDir;
    if (va > vb) return  sortDir;
    return 0;
  });
}

function updateSortHeaders() {
  document.querySelectorAll("thead th[data-col]").forEach(th => {
    th.classList.remove("sort-asc","sort-desc");
    const icon = th.querySelector(".sort-icon");
    if (th.dataset.col === sortCol) {
      th.classList.add(sortDir === 1 ? "sort-asc" : "sort-desc");
      if (icon) icon.textContent = sortDir === 1 ? "↑" : "↓";
    } else {
      if (icon) icon.textContent = "↕";
    }
  });
}

// ── profile card HTML ─────────────────────────────────────────────────────────
function buildProfileCard(d, colSpan) {
  const narrative = renderProfile(d.profile);
  const dealsHtml = (d.deals || []).map(deal => {
    const amt   = fmtCapital(deal.amount);
    const meta  = [deal.stage, amt].filter(Boolean).join(" · ");
    const link  = deal.source_url ? `<a href="${deal.source_url}" target="_blank" rel="noopener" class="deal-link">↗</a>` : "";
    const lead  = deal.is_lead ? `<span class="deal-lead">LEAD</span>` : "";
    return `<div class="deal-row">
      <span class="deal-company">${esc(deal.company)}</span>
      <span class="deal-meta">${esc(meta)}</span>
      <span class="deal-meta">${esc(fmtDate(deal.date))}</span>
      ${lead}${link}
    </div>`;
  }).join("");

  return `<tr class="profile-row">
    <td colspan="${colSpan}">
      <div class="profile-card">
        <div class="profile-narrative">${narrative}</div>
        <div class="profile-deals">
          <h5>Deals in ledger</h5>
          ${dealsHtml || '<em style="font-size:12px;color:#9AA0A6">None recorded</em>'}
        </div>
      </div>
    </td>
  </tr>`;
}

// ── render table ─────────────────────────────────────────────────────────────
function render() {
  const filtered = applyFilters();
  const sorted   = applySort(filtered);
  updateSortHeaders();

  const count = document.getElementById("result-count");
  count.textContent = filtered.length === DATA.length
    ? DATA.length + " investor" + (DATA.length !== 1 ? "s" : "")
    : filtered.length + " of " + DATA.length + " investors";

  const tbody     = document.getElementById("inv-tbody");
  const noResults = document.getElementById("no-results");
  const COL_SPAN  = 7;

  if (sorted.length === 0) {
    tbody.innerHTML = "";
    noResults.style.display = "block";
    return;
  }
  noResults.style.display = "none";

  if (openRow && !sorted.find(d => d.canonical_name === openRow)) {
    openRow = null;
  }

  tbody.innerHTML = sorted.map(d => {
    const cap = d.capital_sum > 0 ? fmtCapital(d.capital_sum) : null;
    const capHtml = cap
      ? `<span class="num-cell">${cap}</span><div class="num-sub">${d.capital_deal_count} disclosed</div>`
      : `<span class="capital-nil">—</span>`;

    const stageTags = (d.stage_focus || [])
      .map(s => `<span class="stage-tag">${esc(s)}</span>`).join("");
    const sectorTags = (d.sectors || []).slice(0, 3)
      .map(s => `<span class="sector-tag">${esc(s)}</span>`).join("");

    const isOpen = d.canonical_name === openRow;
    const rowClass = "data-row" + (isOpen ? " open" : "");

    const dataRow = `<tr class="${rowClass}" data-name="${esc(d.canonical_name)}">
      <td><span class="vc-name">${esc(d.canonical_name)}</span></td>
      <td class="hq-cell">${esc(d.hq)}</td>
      <td><span class="num-cell">${d.deal_count}</span><div class="num-sub">${d.lead_count} as lead</div></td>
      <td>${capHtml}</td>
      <td>${stageTags}</td>
      <td>${sectorTags}</td>
      <td class="date-cell">${fmtDate(d.last_active)}</td>
    </tr>`;

    const profileRow = isOpen ? buildProfileCard(d, COL_SPAN) : "";
    return dataRow + profileRow;
  }).join("");

  tbody.querySelectorAll("tr.data-row").forEach(row => {
    row.addEventListener("click", () => {
      const name = row.dataset.name;
      openRow = openRow === name ? null : name;
      render();
    });
  });
}

// ── filters setup ─────────────────────────────────────────────────────────────
function populateFilters() {
  const stages = [...new Set(DATA.flatMap(d => d.stage_focus || []))].sort();
  const hqs    = [...new Set(DATA.map(d => d.hq).filter(Boolean))].sort();

  const stageEl = document.getElementById("filter-stage");
  stages.forEach(s => stageEl.append(new Option(s, s)));

  const hqEl = document.getElementById("filter-hq");
  hqs.forEach(h => hqEl.append(new Option(h, h)));
}

// ── stats ─────────────────────────────────────────────────────────────────────
function setStats() {
  const repeat = DATA.filter(d => d.deal_count >= 2).length;
  document.getElementById("stat-repeat").textContent = repeat;
}

// ── wire events ───────────────────────────────────────────────────────────────
document.getElementById("search").addEventListener("input", e => {
  searchQuery = e.target.value; openRow = null; render();
});
document.getElementById("filter-stage").addEventListener("change", e => {
  filterStage = e.target.value; openRow = null; render();
});
document.getElementById("filter-hq").addEventListener("change", e => {
  filterHq = e.target.value; openRow = null; render();
});
document.getElementById("btn-reset").addEventListener("click", () => {
  document.getElementById("search").value = "";
  document.getElementById("filter-stage").value = "";
  document.getElementById("filter-hq").value = "";
  searchQuery = filterStage = filterHq = "";
  openRow = null; render();
});
document.querySelectorAll("thead th[data-col]").forEach(th => {
  th.addEventListener("click", () => {
    const col = th.dataset.col;
    if (col === sortCol) { sortDir *= -1; }
    else {
      sortCol = col;
      sortDir = (col === "deal_count" || col === "capital_sum" || col === "last_active") ? -1 : 1;
    }
    render();
  });
});

// ── bootstrap: fetch data then initialise ────────────────────────────────────
fetch("investors.json")
  .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
  .then(data => {
    DATA = data.vcs;
    document.title = "Scottish Venture News — Investor Directory";
    document.getElementById("generated-date").textContent   = data.generated;
    document.getElementById("stat-total-vcs").textContent   = data.total_vcs;
    document.getElementById("stat-unique-deals").textContent = data.unique_deals;
    document.getElementById("stat-total-capital").textContent = data.total_capital;
    document.getElementById("status-wrap").style.display    = "none";
    document.getElementById("table-wrap").style.display     = "";
    populateFilters();
    setStats();
    render();
    drawChart("chart-deals", data.chart_deals, v => v + (v === 1 ? " deal" : " deals"));
    drawChart("chart-capital", data.chart_capital, v => {
      if (v >= 1000) return "£" + (v/1000).toFixed(1) + "bn";
      if (v >= 1)    return "£" + v.toFixed(1) + "m";
      return "£" + Math.round(v * 1000) + "k";
    });
  })
  .catch(err => {
    document.getElementById("status-wrap").textContent = "Failed to load investor data (" + err.message + ").";
  });
</script>
</body>
</html>"""


# ── main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    today          = date.today().isoformat()
    ledger         = json.loads(LEDGER.read_text())
    vc_by_canonical, alias_map = load_known_vcs()
    stats          = aggregate(ledger, vc_by_canonical, alias_map)
    payload        = build_json(stats, ledger, today)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    OUT_HTML.write_text(_SHELL, encoding="utf-8")

    active_count = sum(1 for s in stats.values() if s["deal_count"] > 0)
    print(f"Written: {OUT_JSON}  ({active_count} investors, {len(ledger)} deals)")
    print(f"Written: {OUT_HTML}  (shell)")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
