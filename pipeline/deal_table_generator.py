"""Stage 6 — Deal Table Generator.

Reads ledger.json, filters to the current quarter and YTD, and writes:
  docs/deals/deals.json   — data payload (fetched by the browser at runtime)
  docs/deals/index.html   — static HTML shell (JS fetches deals.json on load)

No backend needed: all filtering, sorting, and search runs in vanilla JS.
"""
import argparse
import calendar
import json
from datetime import date
from pathlib import Path

from webgen.shell import render_shell

ROOT     = Path(__file__).resolve().parent.parent
LEDGER   = ROOT / "data" / "processed" / "ledger.json"
OUT_DIR  = ROOT / "docs" / "deals"
OUT_HTML = OUT_DIR / "index.html"
OUT_JSON = OUT_DIR / "deals.json"
TEMPLATE = ROOT / "pipeline" / "webgen" / "templates" / "deals.html"


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


def run(date_str: str | None = None) -> None:
    run_date = date.fromisoformat(date_str) if date_str else date.today()
    data = _build_data(run_date)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    html = render_shell(
        title="Scottish Venture News — Deal Table",
        favicon_href="../favicon.ico",
        stylesheets=["../assets/style.css", "../assets/deals.css"],
        body=TEMPLATE.read_text(encoding="utf-8"),
        scripts=["../assets/common.js", "../assets/deals.js"],
    )

    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    OUT_HTML.write_text(html, encoding="utf-8")

    q = data["quarter_label"]
    year = data["year"]
    print(f"Written: {OUT_JSON}  ({len(data['quarter_deals'])} {q} deals, {len(data['ytd_deals'])} {year} YTD)")
    print(f"Written: {OUT_HTML}  (shell)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Deal Table Generator (Stage 6)")
    ap.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default: today)")
    args = ap.parse_args()
    run(args.date)
