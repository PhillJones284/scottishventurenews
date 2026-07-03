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
from datetime import date
from pathlib import Path

from webgen.shell import render_shell

ROOT         = Path(__file__).resolve().parent.parent
LEDGER       = ROOT / "data" / "processed" / "ledger.json"
KNOWN_VCS    = ROOT / "config" / "known_vcs.json"
PROFILES_DIR = ROOT / "data" / "vc-profiles"
OUT_DIR      = ROOT / "docs" / "investors"
OUT_HTML     = OUT_DIR / "index.html"
OUT_JSON     = OUT_DIR / "investors.json"
TEMPLATE     = ROOT / "pipeline" / "webgen" / "templates" / "investors.html"

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
        "total_capital": round(total_capital, 3),
        "vcs": vc_list,
        "chart_deals":   [{"name": s["canonical_name"], "value": s["deal_count"]}
                          for s in top5_count],
        "chart_capital": [{"name": s["canonical_name"], "value": round(s["capital_sum"], 2)}
                          for s in top5_capital],
    }


# ── main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    today          = date.today().isoformat()
    ledger         = json.loads(LEDGER.read_text())
    vc_by_canonical, alias_map = load_known_vcs()
    stats          = aggregate(ledger, vc_by_canonical, alias_map)
    payload        = build_json(stats, ledger, today)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    html = render_shell(
        title="Scottish Venture News — Investor Directory",
        favicon_href="../favicon.ico",
        stylesheets=["../assets/style.css", "../assets/investors.css"],
        body=TEMPLATE.read_text(encoding="utf-8"),
        scripts=["../assets/common.js", "../assets/investors.js"],
    )

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    OUT_HTML.write_text(html, encoding="utf-8")

    active_count = sum(1 for s in stats.values() if s["deal_count"] > 0)
    print(f"Written: {OUT_JSON}  ({active_count} investors, {len(ledger)} deals)")
    print(f"Written: {OUT_HTML}  (shell)")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
