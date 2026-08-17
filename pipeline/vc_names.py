"""Single source of truth for resolving raw ledger investor-name strings to
canonical VC names from config/known_vcs.json.

Why this module exists: three different scripts (parser.py at write time,
vc_profile_stats.py and investor_page_generator.py at read time) each grew
their own investor-name matching rule independently — a case-sensitive exact
match, a hardcoded MERGE_TO dict plus alnum-normalised alias map, and a plain
``.lower().strip()`` dict lookup. Because the rules diverged, the same raw
string (e.g. "GU Holdings Ltd (University of Glasgow)") could resolve
differently — or not at all — depending on which script looked at it, which
silently undercounted deals in data/vc-profiles/*.md. Every consumer must
resolve through ``resolve_name()`` (backed by ``load_alias_map()``) so there
is exactly one matching rule in the whole pipeline.

``norm()`` is the strictest of the three former rules — it strips everything
but lowercase letters and digits — and strictly supersedes the parser's old
``.lower().strip()`` comparison, so no previously-matching pair stops
matching under the unified rule.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWN_VCS_PATH = ROOT / "config" / "known_vcs.json"

# Raw investor strings to drop entirely (descriptors / personal names, not
# actual firms) — moved verbatim from investor_page_generator.py. Callers
# match with ``raw.strip().lower() in SKIP_INVESTORS``.
SKIP_INVESTORS: frozenset[str] = frozenset({
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
})


def norm(s: str) -> str:
    """Strip everything but lowercase letters/digits. The strictest of the
    formerly-divergent matching rules — used as the single comparison key."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_alias_map(path: str | Path | None = None) -> dict[str, str]:
    """Return {norm(alias_or_canonical): canonical_name} for every known VC."""
    vcs_path = Path(path) if path else KNOWN_VCS_PATH
    raw = json.loads(vcs_path.read_text())
    alias_map: dict[str, str] = {}
    for vc in raw["known_vcs"]:
        canonical = vc["canonical_name"]
        alias_map[norm(canonical)] = canonical
        for alias in vc.get("aliases") or []:
            alias_map[norm(alias)] = canonical
    return alias_map


def resolve_name(raw: str, alias_map: dict[str, str]) -> str:
    """Map a raw investor name from the ledger to its canonical form, or
    return it stripped/unchanged if it matches no known VC."""
    if not raw:
        return raw
    canonical = alias_map.get(norm(raw))
    return canonical if canonical else raw.strip()


def load_known_vcs(path: str | Path | None = None) -> tuple[dict, dict]:
    """Return (vc_by_canonical, alias_map), matching the shape formerly
    returned by investor_page_generator.load_known_vcs()."""
    vcs_path = Path(path) if path else KNOWN_VCS_PATH
    raw = json.loads(vcs_path.read_text())
    vc_by_canonical: dict[str, dict] = {vc["canonical_name"]: vc for vc in raw["known_vcs"]}
    alias_map = load_alias_map(vcs_path)
    return vc_by_canonical, alias_map
