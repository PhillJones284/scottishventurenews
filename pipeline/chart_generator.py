"""Generates the report's charts (Stage 3.6) — pure Python, no LLM.

Reads `report_stats.json` (this run's computed figures) and writes two PNGs
to `data/reports/charts/`:

  - `YYYY-MM-DD_stage.png`  — deals by stage, two panels: quarter-to-date
    (left) vs. year-to-date (right)
  - `YYYY-MM-DD_sector.png` — deals by sector, 2x2: capital deployed vs. deal
    count, quarter-to-date vs. year-to-date

Charts are generated deterministically from the same numbers the reporter
narrates, for the same reason `report_stats.py` exists: an LLM should narrate
figures, not compute or hand-draw them.

Usage:
    python pipeline/chart_generator.py [--date YYYY-MM-DD]
"""
import argparse
import json
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

try:
    from chart_style import (
        EARTH_PALETTE,
        GREY,
        INK,
        ROUND_TYPE_TO_BUCKET,
        STAGE_BUCKET_COLOURS,
        STAGE_BUCKET_FALLBACK,
        STAGE_BUCKET_ORDER,
    )
except ImportError:
    from pipeline.chart_style import (
        EARTH_PALETTE,
        GREY,
        INK,
        ROUND_TYPE_TO_BUCKET,
        STAGE_BUCKET_COLOURS,
        STAGE_BUCKET_FALLBACK,
        STAGE_BUCKET_ORDER,
    )

# Visual gap (in x-axis units) separating "Unknown" from the funding-stage
# progression bars, since it isn't part of that progression.
UNKNOWN_GAP = 0.3

# Minimum pixel clearance an inside bar label needs from the bar's start edge
# before it's considered "fits inside" rather than cramped — measured against
# the label's actual rendered width, not a fixed text-length heuristic, since
# "£18.7m" and "9" take up very different space at the same font size.
SECTOR_LABEL_FIT_BUFFER_PX = 20

ROOT = Path(__file__).parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
STATS_PATH = PROCESSED_DIR / "report_stats.json"
CHARTS_DIR = ROOT / "data" / "reports" / "charts"


def _bucket_stage_mix(stage_mix):
    bucketed = {bucket: 0 for bucket in STAGE_BUCKET_ORDER}
    bucketed["Grant"] = 0
    for round_type, count in stage_mix.items():
        bucket = ROUND_TYPE_TO_BUCKET.get(round_type, STAGE_BUCKET_FALLBACK)
        bucketed[bucket] = bucketed.get(bucket, 0) + count
    return bucketed


def _stage_panel(ax, stage_mix, title_prefix):
    """Draws one centred/diverging bar panel, copying the style of Phill's
    linkedin_cohort_ceiling.py reference: each bar is centred on a zero
    baseline, height = % of this panel's deals, width fills its slot,
    coloured by stage bucket, with zero-aware label placement.

    "Grant" only appears on the axis when this panel actually has one —
    we've never seen one in any source we follow, so it stays off by
    default rather than sitting on the axis as a permanent boxed "0%".
    "Unknown" isn't part of the funding-stage progression, so it's offset
    by UNKNOWN_GAP to read as visually separate from the other bars.
    """
    bucketed = _bucket_stage_mix(stage_mix)
    total = sum(bucketed.values())

    progression = [s for s in STAGE_BUCKET_ORDER if s != "Unknown"]
    if bucketed.get("Grant", 0) > 0:
        progression = ["Grant"] + progression
    order = progression + ["Unknown"]
    positions = list(range(len(progression))) + [len(progression) - 1 + 1 + UNKNOWN_GAP]

    max_pct = 0
    for x, stage in zip(positions, order):
        n = bucketed[stage]
        pct = n / total * 100 if total else 0
        max_pct = max(max_pct, pct)
        half = pct / 2
        if n > 0:
            ax.bar(x, pct, bottom=-half, width=1.0, color=STAGE_BUCKET_COLOURS[stage], zorder=2)
        label = f"{n} ({pct:.0f}%)"
        if n == 0:
            ax.text(
                x, 0, label, ha="center", va="center", fontsize=10.5, color=GREY,
                fontweight="bold", zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", boxstyle="square,pad=0.3"),
            )
        elif pct >= 8:
            ax.text(x, 0, label, ha="center", va="center", fontsize=10.5, color="white",
                     fontweight="bold", zorder=3)
        else:
            ax.text(x, half + 1.5, label, ha="center", va="bottom", fontsize=10.5,
                     color=GREY, fontweight="bold", zorder=3)

    ax.set_title(
        f"{title_prefix} (n={total})", loc="left",
        fontsize=12, fontweight="bold", color=INK, pad=14,
    )
    tick_labels = [s.replace("/", "/\n", 1) if s == "Growth/Series A+" else s for s in order]
    ax.set_xticks(positions)
    ax.set_xticklabels(tick_labels, fontsize=10.5)
    ax.tick_params(axis="x", length=0, colors=INK)
    ax.set_xlim(-0.6, positions[-1] + 0.6)
    half_max = max(max_pct / 2, 5)
    ax.set_ylim(-half_max - 12, half_max + 12)
    ax.set_yticks([])
    ax.axhline(0, color=GREY, linewidth=0.5, zorder=1)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.grid(False)


def _stage_chart(stats, out_path):
    """Two independent panels side by side — QTD (left) vs. YTD (right) —
    each an independent diverging-bar breakdown for its own window, the same
    "each panel ranks its own metric/window independently" approach as the
    sector chart's 2x2 grid.
    """
    fig = Figure(figsize=(13, 4.6))
    FigureCanvasAgg(fig)
    ax_qtd = fig.add_subplot(1, 2, 1)
    ax_ytd = fig.add_subplot(1, 2, 2)

    run_year = stats["run_date"][:4]
    _stage_panel(ax_qtd, stats["stage_mix"], f"Deals by stage — QTD {stats['quarter_label']}")
    _stage_panel(ax_ytd, stats["ytd_stage_mix"], f"Deals by stage — YTD {run_year}")

    fig.tight_layout(w_pad=4)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")


def _sector_panel(ax, canvas, data, value_fmt, title, max_bars):
    items = sorted(data.items(), key=lambda kv: -kv[1])[:max_bars][::-1]

    if not items:
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", color=INK, pad=10)
        ax.text(0.5, 0.5, "No deals yet", ha="center", va="center", transform=ax.transAxes,
                 fontsize=10.5, color=GREY)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    labels = [k for k, _ in items]
    values = [v for _, v in items]
    colours = [EARTH_PALETTE[i % len(EARTH_PALETTE)] for i in range(len(items))]

    y = list(range(len(labels)))
    ax.barh(y, values, color=colours, height=0.82, zorder=2)
    ax.set_xlim(0, max(values) * 1.25)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color=INK)
    ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", color=INK, pad=10)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    ax.grid(False)

    canvas.draw()
    renderer = canvas.get_renderer()
    pad_frac = max(values) * 0.02

    for yi, v in zip(y, values):
        label = value_fmt(v)
        txt = ax.text(
            v - pad_frac, yi, label, va="center", ha="right",
            fontsize=10.5, color="white", fontweight="bold", zorder=3,
        )
        bbox = txt.get_window_extent(renderer=renderer)
        bar_start_disp = ax.transData.transform((0, yi))[0]
        if bbox.x0 < bar_start_disp + SECTOR_LABEL_FIT_BUFFER_PX:
            txt.remove()
            ax.text(
                v + pad_frac, yi, label, va="center", ha="left",
                fontsize=10.5, color=INK, fontweight="bold", zorder=3,
            )


def _sector_chart(stats, out_path, max_bars=5):
    """2x2 grid: capital deployed (top row) vs. deal count (bottom row),
    quarter-to-date (left column) vs. year-to-date (right column). Each panel
    is an independent top-N ranking for its own metric/window — a sector that
    leads by deal count needn't lead by capital, and that's the point of
    showing both rather than picking one.

    Capital panels are labelled with a plain £ amount; count panels with a
    plain deal count — no combined "n (pct%)" style here, since each panel is
    already one metric. Labels go inside the bar in white when they fit,
    determined by actually measuring the rendered text against the bar's
    pixel width (see SECTOR_LABEL_FIT_BUFFER_PX) rather than a fixed
    percentage threshold, since label width varies a lot between a short
    count and a longer capital figure.
    """
    run_year = stats["run_date"][:4]
    quarter_label = stats["quarter_label"]

    fig = Figure(figsize=(12, 8.5))
    canvas = FigureCanvasAgg(fig)
    axes = [[fig.add_subplot(2, 2, r * 2 + c + 1) for c in range(2)] for r in range(2)]

    panels = [
        (axes[0][0], stats["sector_capital_mix"], lambda v: f"£{v:.1f}m", f"Capital deployed — QTD {quarter_label}"),
        (axes[0][1], stats["ytd_sector_capital_mix"], lambda v: f"£{v:.1f}m", f"Capital deployed — YTD {run_year}"),
        (axes[1][0], stats["sector_mix"], lambda v: f"{int(v)}", f"Deal count — QTD {quarter_label}"),
        (axes[1][1], stats["ytd_sector_mix"], lambda v: f"{int(v)}", f"Deal count — YTD {run_year}"),
    ]
    for ax, data, fmt, title in panels:
        _sector_panel(ax, canvas, data, fmt, title, max_bars)

    fig.tight_layout(h_pad=3.5, w_pad=4)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")


def run(date_str=None):
    if not STATS_PATH.exists():
        raise RuntimeError(f"{STATS_PATH} not found — run pipeline/report_stats.py first")
    stats = json.loads(STATS_PATH.read_text())
    run_date = date_str or stats["run_date"]

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = CHARTS_DIR / f"{run_date}_stage.png"
    sector_path = CHARTS_DIR / f"{run_date}_sector.png"

    _stage_chart(stats, stage_path)
    _sector_chart(stats, sector_path)

    return {
        "stage_chart": str(stage_path),
        "sector_chart": str(sector_path),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="Run date in YYYY-MM-DD format (default: today)")
    args = ap.parse_args()
    paths = run(date_str=args.date)
    print(json.dumps(paths, indent=2))


if __name__ == "__main__":
    main()
