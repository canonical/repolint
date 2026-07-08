# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Product catalog loading for gold/silver/bronze service-level classification.

The catalog is an optional JSON file (typically ``catalog.json``) produced by
``scripts/fetch_catalog.py``.  When present, its ``service_levels`` mapping is
used to group repositories by tier in the quality report.  When absent the
report falls back to its default flat layout.
"""

import json
from pathlib import Path

TIER_ORDER: dict[str, int] = {"gold": 0, "silver": 1, "bronze": 2}
TIER_LABELS: dict[str, str] = {
    "gold": "🥇 Gold",
    "silver": "🥈 Silver",
    "bronze": "🥉 Bronze",
}
ALL_TIERS: list[str] = ["gold", "silver", "bronze"]


def load_catalog(path: Path) -> dict[str, str]:
    """Load the catalog JSON and return ``{repo_slug: service_level}``.

    Returns an empty dict when *path* does not exist, printing a notice so
    callers do not need to handle the absence as an error.
    """
    if not path.exists():
        print(f"Notice: catalog file not found at {path} — tier grouping disabled.")
        return {}

    with path.open() as fh:
        data = json.load(fh)

    service_levels: dict[str, str] = data.get("service_levels", {})
    known = set(TIER_ORDER)
    invalid = {v for v in service_levels.values() if v not in known}
    if invalid:
        print(f"Warning: catalog contains unknown service levels: {invalid!r} — ignored.")
        service_levels = {k: v for k, v in service_levels.items() if v in known}

    return service_levels
