let DATA = null;
let currentWindow = "quarter";
let sortCol = "announcement_date";
let sortDir = -1;
let searchQuery = "";
let filterStage = "";
let filterSector = "";
let filterLocation = "";
let filterConfidence = "";

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
  document.getElementById("stat-capital").textContent = disclosed.length ? fmtMoney(capital) : "—";
  document.getElementById("stat-disclosed").textContent = disclosed.length + " / " + filtered.length;
  document.getElementById("stat-investors").textContent = investors.size;
}

function render() {
  const deals = getDeals();
  const filtered = applyFilters(deals);
  const sorted = applySort(filtered);

  updateStats(filtered);
  updateSortHeaders(sortCol, sortDir);

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
    const amt = fmtMoney(d.amount_gbp_millions);
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
      <td class="date">${fmtDate(d.announcement_date, "")}</td>
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
