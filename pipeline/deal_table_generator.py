"""Stage 6 — Deal Table Generator.

Reads ledger.json, filters to the current quarter and YTD, and writes:
  docs/deals/deals.json   — data payload (fetched by the browser at runtime)
  docs/deals/index.html   — static HTML shell (JS fetches deals.json on load)

No backend needed: all filtering, sorting, and search runs in vanilla JS.
"""
import argparse
import calendar
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
LEDGER   = ROOT / "data" / "processed" / "ledger.json"
OUT_DIR  = ROOT / "docs" / "deals"
OUT_HTML = OUT_DIR / "index.html"
OUT_JSON = OUT_DIR / "deals.json"


def quarter_bounds(d: date) -> tuple[date, date]:
    q = (d.month - 1) // 3
    start_month = q * 3 + 1
    end_month = start_month + 2
    end_day = calendar.monthrange(d.year, end_month)[1]
    return date(d.year, start_month, 1), date(d.year, end_month, end_day)


def quarter_label(d: date) -> str:
    return f"Q{(d.month - 1) // 3 + 1} {d.year}"


def _in_window(record: dict, start: date, end: date) -> bool:
    raw = record.get("announcement_date")
    if not raw:
        return False
    try:
        return start <= date.fromisoformat(str(raw)) <= end
    except ValueError:
        return False


def _slim(records: list[dict]) -> list[dict]:
    """Strip fields not needed in the browser to keep the JSON small."""
    out = []
    for r in records:
        investors = r.get("investors") or []
        lead = r.get("lead_investor") or ""
        ordered = [lead] + [i for i in investors if i != lead] if lead else investors
        out.append({
            "id": r.get("id", ""),
            "company_name": r.get("company_name", ""),
            "company_location": r.get("company_location") or "Unknown",
            "company_sectors": r.get("company_sectors") or [],
            "round_type": r.get("round_type") or "Unknown",
            "amount_gbp_millions": r.get("amount_gbp_millions"),
            "investors": ordered,
            "lead_investor": lead,
            "announcement_date": r.get("announcement_date") or "",
            "source_url": r.get("source_url") or "",
            "headline": r.get("headline") or "",
            "confidence": r.get("confidence") or "medium",
        })
    return out


def _build_data(run_date: date) -> dict:
    ledger = json.loads(LEDGER.read_text())

    q_start, q_end = quarter_bounds(run_date)
    ytd_start = date(run_date.year, 1, 1)
    ytd_end = date(run_date.year, 12, 31)

    q_deals = sorted(
        [r for r in ledger if _in_window(r, q_start, q_end)],
        key=lambda r: r.get("announcement_date") or "",
        reverse=True,
    )
    ytd_deals = sorted(
        [r for r in ledger if _in_window(r, ytd_start, ytd_end)],
        key=lambda r: r.get("announcement_date") or "",
        reverse=True,
    )

    return {
        "quarter_label": quarter_label(run_date),
        "year": run_date.year,
        "generated": run_date.isoformat(),
        "quarter_deals": _slim(q_deals),
        "ytd_deals": _slim(ytd_deals),
    }


# ---------------------------------------------------------------------------
# HTML shell — no data embedded; JS fetches deals.json at runtime
# ---------------------------------------------------------------------------

_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="../favicon.ico">
  <title>Scottish Venture News — Deal Table</title>
  <link rel="stylesheet" href="../assets/style.css">
  <style>
    body { font-size: 13px; line-height: 1.45; }
    a { color: inherit; text-decoration: none; }

    .container { max-width: 1280px; margin: 0 auto; padding: 28px 20px 48px; }

    /* ── tabs ── */
    .tabs {
      display: flex;
      gap: 0;
      margin-bottom: 16px;
      border-bottom: 2px solid var(--light-grey);
    }
    .tab {
      padding: 8px 20px;
      cursor: pointer;
      color: var(--slate);
      font-size: 13px;
      font-weight: 500;
      border-bottom: 2px solid transparent;
      margin-bottom: -2px;
      transition: color 0.1s;
    }
    .tab.active { color: var(--navy); border-bottom-color: var(--navy); }
    .tab:hover:not(.active) { color: var(--ink); }

    /* ── stats bar ── */
    .stats-bar { margin-bottom: 16px; }

    /* ── controls ── */
    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
    }
    .controls input[type="text"] {
      padding: 6px 10px;
      border: 1px solid var(--light-grey);
      border-radius: 4px;
      font-size: 13px;
      width: 230px;
      background: var(--white);
      outline: none;
    }
    .controls input[type="text"]:focus { border-color: var(--blue); }
    .controls select {
      padding: 6px 8px;
      border: 1px solid var(--light-grey);
      border-radius: 4px;
      font-size: 12px;
      color: var(--ink);
      background: var(--white);
      cursor: pointer;
      outline: none;
    }
    .controls select:focus { border-color: var(--blue); }
    .btn-reset {
      padding: 6px 12px;
      border: 1px solid var(--light-grey);
      border-radius: 4px;
      background: var(--white);
      color: var(--slate);
      font-size: 12px;
      cursor: pointer;
    }
    .btn-reset:hover { color: var(--ink); border-color: var(--grey); }
    .result-count { color: var(--slate); font-size: 12px; margin-left: auto; }

    /* ── table ── */
    table { min-width: 860px; }
    thead th {
      padding: 9px 12px;
      background: #F0F1F2;
      white-space: nowrap;
      cursor: pointer;
      user-select: none;
    }
    thead th:last-child { cursor: default; }
    thead th:hover:not(:last-child) { color: var(--navy); }
    .sort-icon { color: var(--light-grey); margin-left: 3px; font-style: normal; }
    th.sort-asc .sort-icon, th.sort-desc .sort-icon { color: var(--navy); }
    tbody tr { transition: background 0.08s; }
    tbody tr:hover { background: #F4F5F6; }

    /* ── cell styles ── */
    .date { color: var(--slate); white-space: nowrap; font-size: 12px; }
    .company-name { font-weight: 600; color: var(--navy); }
    .headline { font-size: 11px; color: var(--grey); margin-top: 2px; line-height: 1.35; max-width: 260px; }
    .location { color: var(--slate); font-size: 12px; }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      white-space: nowrap;
    }
    .badge-stage { background: #ECF1F7; color: var(--navy); }
    .badge-high   { background: #E8F4EF; color: #3A7860; }
    .badge-medium { background: #FEF4E3; color: #8A6828; }
    .badge-low    { background: #F5ECEC; color: #8A4848; }
    .amount { font-weight: 600; color: var(--navy); white-space: nowrap; }
    .amount-undisclosed { color: var(--grey); font-style: italic; white-space: nowrap; }
    .lead-investor { font-weight: 500; }
    .other-investors { color: var(--slate); font-size: 11px; margin-top: 2px; }
    .source-link {
      color: var(--blue);
      font-size: 14px;
      display: inline-block;
      line-height: 1;
    }
    .source-link:hover { color: var(--navy); }

    /* ── footer ── */
    footer { margin-top: 20px; }
  </style>
</head>
<body>
<div class="container">

  <a class="back-link" href="../">← Scottish Venture News</a>

  <header>
    <h1>Scottish VC Deals</h1>
    <p>Automated pipeline &nbsp;·&nbsp; Generated <span id="generated-date">—</span> &nbsp;·&nbsp; Source: public news coverage</p>
  </header>

  <div class="tabs">
    <div class="tab active" data-window="quarter" id="tab-quarter">—</div>
    <div class="tab" data-window="ytd" id="tab-ytd">—</div>
  </div>

  <div class="stats-bar">
    <div class="stat">
      <div class="stat-value" id="stat-deals">—</div>
      <div class="stat-label">Deals</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-capital">—</div>
      <div class="stat-label">Capital raised</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-disclosed">—</div>
      <div class="stat-label">Amount disclosed</div>
    </div>
    <div class="stat">
      <div class="stat-value" id="stat-investors">—</div>
      <div class="stat-label">Investors active</div>
    </div>
  </div>

  <div class="controls">
    <input type="text" id="search" placeholder="Search company, investor…" autocomplete="off">
    <select id="filter-stage"><option value="">All stages</option></select>
    <select id="filter-sector"><option value="">All sectors</option></select>
    <select id="filter-location"><option value="">All locations</option></select>
    <select id="filter-confidence">
      <option value="">All confidence</option>
      <option value="high">High confidence</option>
      <option value="medium">Medium confidence</option>
      <option value="low">Low confidence</option>
    </select>
    <button class="btn-reset" id="btn-reset">Reset</button>
    <span class="result-count" id="result-count"></span>
  </div>

  <div id="status-wrap" class="status-msg">Loading deals…</div>

  <div id="table-wrap" style="display:none">
    <div class="table-wrap">
      <table id="deals-table">
        <thead>
          <tr>
            <th data-col="announcement_date">Date<i class="sort-icon">↕</i></th>
            <th data-col="company_name">Company<i class="sort-icon">↕</i></th>
            <th data-col="company_location">Location<i class="sort-icon">↕</i></th>
            <th>Sector</th>
            <th data-col="round_type">Stage<i class="sort-icon">↕</i></th>
            <th data-col="amount_gbp_millions">Amount<i class="sort-icon">↕</i></th>
            <th data-col="lead_investor">Investors<i class="sort-icon">↕</i></th>
            <th data-col="confidence">Confidence<i class="sort-icon">↕</i></th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody id="deals-tbody"></tbody>
      </table>
      <div class="no-results" id="no-results">No deals match your filters.</div>
    </div>
  </div>

  <footer>Scottish Venture News &nbsp;·&nbsp; Data sourced from public news coverage only &nbsp;·&nbsp; Not investment advice</footer>

</div>
<script>
let DATA = null;
let currentWindow = "quarter";
let sortCol = "announcement_date";
let sortDir = -1;
let searchQuery = "";
let filterStage = "";
let filterSector = "";
let filterLocation = "";
let filterConfidence = "";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtDate(d) {
  if (!d) return "";
  const [y, m, day] = d.split("-");
  return `${parseInt(day)} ${MONTHS[+m - 1]} ${y}`;
}

function fmtAmount(m) {
  if (m === null || m === undefined) return null;
  if (m >= 1000) return "£" + (m / 1000).toFixed(1) + "bn";
  if (m >= 1) return "£" + m.toFixed(1) + "m";
  return "£" + Math.round(m * 1000) + "k";
}

function getDeals() {
  return currentWindow === "quarter" ? DATA.quarter_deals : DATA.ytd_deals;
}

function populateFilters() {
  const all = DATA.ytd_deals;
  const stages = [...new Set(all.map(d => d.round_type).filter(Boolean))].sort();
  const sectors = [...new Set(all.flatMap(d => d.company_sectors || []))].sort();
  const locs = [...new Set(all.map(d => d.company_location).filter(Boolean))].sort();

  const stageEl = document.getElementById("filter-stage");
  stages.forEach(s => stageEl.append(new Option(s, s)));

  const sectorEl = document.getElementById("filter-sector");
  sectors.forEach(s => sectorEl.append(new Option(s.length > 30 ? s.slice(0, 28) + "…" : s, s)));

  const locEl = document.getElementById("filter-location");
  locs.forEach(l => locEl.append(new Option(l, l)));
}

function applyFilters(deals) {
  const q = searchQuery.toLowerCase();
  return deals.filter(d => {
    if (filterStage && d.round_type !== filterStage) return false;
    if (filterSector && !(d.company_sectors || []).includes(filterSector)) return false;
    if (filterLocation && d.company_location !== filterLocation) return false;
    if (filterConfidence && d.confidence !== filterConfidence) return false;
    if (q) {
      const hay = [
        d.company_name, d.company_location,
        (d.company_sectors || []).join(" "),
        (d.investors || []).join(" "),
        d.headline,
      ].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function applySort(deals) {
  return [...deals].sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (sortCol === "amount_gbp_millions") {
      va = va ?? -1; vb = vb ?? -1;
    } else {
      va = (Array.isArray(va) ? va.join(",") : va ?? "").toString();
      vb = (Array.isArray(vb) ? vb.join(",") : vb ?? "").toString();
    }
    if (va < vb) return -sortDir;
    if (va > vb) return sortDir;
    return 0;
  });
}

function updateStats(filtered) {
  const disclosed = filtered.filter(d => d.amount_gbp_millions != null);
  const capital = disclosed.reduce((s, d) => s + d.amount_gbp_millions, 0);
  const investors = new Set(filtered.flatMap(d => d.investors || []));

  document.getElementById("stat-deals").textContent = filtered.length;
  document.getElementById("stat-capital").textContent = disclosed.length ? fmtAmount(capital) : "—";
  document.getElementById("stat-disclosed").textContent = disclosed.length + " / " + filtered.length;
  document.getElementById("stat-investors").textContent = investors.size;
}

function updateSortHeaders() {
  document.querySelectorAll("thead th[data-col]").forEach(th => {
    th.classList.remove("sort-asc", "sort-desc");
    const icon = th.querySelector(".sort-icon");
    if (th.dataset.col === sortCol) {
      th.classList.add(sortDir === 1 ? "sort-asc" : "sort-desc");
      if (icon) icon.textContent = sortDir === 1 ? "↑" : "↓";
    } else {
      if (icon) icon.textContent = "↕";
    }
  });
}

function render() {
  const deals = getDeals();
  const filtered = applyFilters(deals);
  const sorted = applySort(filtered);

  updateStats(filtered);
  updateSortHeaders();

  const count = document.getElementById("result-count");
  count.textContent = filtered.length === deals.length
    ? deals.length + " deal" + (deals.length !== 1 ? "s" : "")
    : filtered.length + " of " + deals.length + " deals";

  const tbody = document.getElementById("deals-tbody");
  const noResults = document.getElementById("no-results");

  if (sorted.length === 0) {
    tbody.innerHTML = "";
    noResults.style.display = "block";
    return;
  }
  noResults.style.display = "none";

  const confClass = { high: "badge-high", medium: "badge-medium", low: "badge-low" };

  tbody.innerHTML = sorted.map(d => {
    const amt = fmtAmount(d.amount_gbp_millions);
    const amtHtml = amt
      ? `<span class="amount">${amt}</span>`
      : `<span class="amount-undisclosed">Undisclosed</span>`;

    const sectorHtml = (d.company_sectors || [])
      .map(s => `<span class="sector-tag">${s}</span>`).join("");

    const others = (d.investors || []).filter(i => i !== d.lead_investor);
    const investHtml = [
      d.lead_investor ? `<span class="lead-investor">${d.lead_investor}</span>` : "",
      others.length ? `<div class="other-investors">${others.join(", ")}</div>` : "",
    ].filter(Boolean).join("");

    const conf = d.confidence || "medium";
    const confLabel = conf.charAt(0).toUpperCase() + conf.slice(1);
    const cc = confClass[conf] || "badge-medium";

    const srcHtml = d.source_url
      ? `<a href="${d.source_url}" target="_blank" rel="noopener" class="source-link" title="${d.headline}">↗</a>`
      : "";

    return `<tr>
      <td class="date">${fmtDate(d.announcement_date)}</td>
      <td>
        <div class="company-name">${d.company_name}</div>
      </td>
      <td class="location">${d.company_location}</td>
      <td>${sectorHtml}</td>
      <td><span class="badge badge-stage">${d.round_type}</span></td>
      <td>${amtHtml}</td>
      <td>${investHtml}</td>
      <td><span class="badge ${cc}">${confLabel}</span></td>
      <td>${srcHtml}</td>
    </tr>`;
  }).join("");
}

// ── wire up events ──
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    currentWindow = tab.dataset.window;
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === tab));
    render();
  });
});

document.getElementById("search").addEventListener("input", e => {
  searchQuery = e.target.value;
  render();
});

[["filter-stage",      v => filterStage      = v],
 ["filter-sector",     v => filterSector     = v],
 ["filter-location",   v => filterLocation   = v],
 ["filter-confidence", v => filterConfidence = v]].forEach(([id, setter]) => {
  document.getElementById(id).addEventListener("change", e => {
    setter(e.target.value);
    render();
  });
});

document.getElementById("btn-reset").addEventListener("click", () => {
  document.getElementById("search").value = "";
  ["filter-stage","filter-sector","filter-location","filter-confidence"]
    .forEach(id => document.getElementById(id).value = "");
  searchQuery = filterStage = filterSector = filterLocation = filterConfidence = "";
  render();
});

document.querySelectorAll("thead th[data-col]").forEach(th => {
  th.addEventListener("click", () => {
    const col = th.dataset.col;
    if (col === sortCol) {
      sortDir *= -1;
    } else {
      sortCol = col;
      sortDir = (col === "announcement_date" || col === "amount_gbp_millions") ? -1 : 1;
    }
    render();
  });
});

// ── bootstrap: fetch data then initialise ──
fetch("deals.json")
  .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
  .then(data => {
    DATA = data;
    document.title = "Scottish VC Deals — " + data.quarter_label + " / " + data.year + " YTD";
    document.getElementById("tab-quarter").textContent = data.quarter_label;
    document.getElementById("tab-ytd").textContent = data.year + " YTD";
    document.getElementById("generated-date").textContent = data.generated;
    document.getElementById("status-wrap").style.display = "none";
    document.getElementById("table-wrap").style.display = "";
    populateFilters();
    render();
  })
  .catch(err => {
    document.getElementById("status-wrap").textContent = "Failed to load deal data (" + err.message + ").";
  });
</script>
</body>
</html>"""


def run(date_str: str | None = None) -> None:
    run_date = date.fromisoformat(date_str) if date_str else date.today()
    data = _build_data(run_date)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    OUT_HTML.write_text(_SHELL, encoding="utf-8")

    q = data["quarter_label"]
    year = data["year"]
    print(f"Written: {OUT_JSON}  ({len(data['quarter_deals'])} {q} deals, {len(data['ytd_deals'])} {year} YTD)")
    print(f"Written: {OUT_HTML}  (shell)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Deal Table Generator (Stage 6)")
    ap.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default: today)")
    args = ap.parse_args()
    run(args.date)
