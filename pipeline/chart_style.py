"""Shared minimalist consulting-report styling for matplotlib charts (Stage 3.6).

One look across every chart in the report: trimmed spines, muted single-accent
palette, no legend boxes, value labels instead of dense tick grids.
"""
import matplotlib as mpl

FONT_FAMILY = "DejaVu Sans"

NAVY = "#1F3B57"
SLATE = "#7C93A8"
GREY = "#9AA0A6"
LIGHT_GREY = "#D8DCE0"
INK = "#222222"

# Muted earth-tone palette, taken from Phill's linkedin_cohort_ceiling.py reference chart.
TAN = "#A89B8C"
BLUE = "#7B9EB9"
GREEN = "#6BA58A"
GOLD = "#C49A5A"
MAROON = "#A07878"

# Our round-type taxonomy, bucketed for the stage chart. Grant sits first when present
# (its own real stage, before Pre-Seed) but is omitted from the axis entirely in a
# quarter with none — we've never actually seen one in any source we follow. Series A,
# Series B/C+, and Growth all fold into one "Growth/Series A+" bucket since A and B are
# both rare on their own. "Unknown" is the catch-all for anything that isn't part of the
# funding-stage progression at all (including Bridge) — kept visually separate in the
# chart (a gap before it) rather than just another bar in the sequence.
STAGE_BUCKET_ORDER = ["Pre-Seed", "Seed", "Growth/Series A+", "Unknown"]
STAGE_BUCKET_COLOURS = {
    "Grant": TAN,
    "Pre-Seed": BLUE,
    "Seed": GREEN,
    "Growth/Series A+": MAROON,
    "Unknown": GREY,
}
ROUND_TYPE_TO_BUCKET = {
    "Grant": "Grant",
    "Pre-Seed": "Pre-Seed",
    "Seed": "Seed",
    "Series A": "Growth/Series A+",
    "Series B": "Growth/Series A+",
    "Series C+": "Growth/Series A+",
    "Growth": "Growth/Series A+",
}
# Anything not in ROUND_TYPE_TO_BUCKET (Bridge, Unknown, or any surprise value) falls
# back to this bucket — see STAGE_BUCKET_FALLBACK usage in chart_generator.py.
STAGE_BUCKET_FALLBACK = "Unknown"

# Cycling order for generic bar series (e.g. sector mix) that don't map onto stage buckets.
EARTH_PALETTE = [BLUE, GREEN, GOLD, MAROON, TAN]

mpl.rcParams["font.family"] = FONT_FAMILY


def apply_consulting_style(ax):
    """Strip chart junk: top/right spines, tick marks, heavy gridlines."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT_GREY)
    ax.tick_params(axis="both", length=0, colors=GREY, labelsize=9)
    ax.set_yticks([])
    ax.grid(False)
