/* Shared helpers used across docs/*.html pages (deal table, investor directory). */

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtDate(d, fallback = "—") {
  if (!d) return fallback;
  const [y, m, day] = d.split("-");
  return `${parseInt(day)} ${MONTHS[+m - 1]} ${y}`;
}

function fmtMoney(m) {
  if (m === null || m === undefined) return null;
  if (m >= 1000) return "£" + (m / 1000).toFixed(1) + "bn";
  if (m >= 1) return "£" + m.toFixed(1) + "m";
  return "£" + Math.round(m * 1000) + "k";
}

function updateSortHeaders(sortCol, sortDir) {
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

function esc(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
