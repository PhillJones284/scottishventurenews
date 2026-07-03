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

// ── profile card HTML ─────────────────────────────────────────────────────────
function buildProfileCard(d, colSpan) {
  const narrative = renderProfile(d.profile);
  const dealsHtml = (d.deals || []).map(deal => {
    const amt   = deal.amount > 0 ? fmtMoney(deal.amount) : null;
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
  updateSortHeaders(sortCol, sortDir);

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
    const cap = d.capital_sum > 0 ? fmtMoney(d.capital_sum) : null;
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
    document.getElementById("stat-total-capital").textContent = data.total_capital > 0 ? fmtMoney(data.total_capital) : "—";
    document.getElementById("status-wrap").style.display    = "none";
    document.getElementById("table-wrap").style.display     = "";
    populateFilters();
    setStats();
    render();
    drawChart("chart-deals", data.chart_deals, v => v + (v === 1 ? " deal" : " deals"));
    drawChart("chart-capital", data.chart_capital, fmtMoney);
  })
  .catch(err => {
    document.getElementById("status-wrap").textContent = "Failed to load investor data (" + err.message + ").";
  });
