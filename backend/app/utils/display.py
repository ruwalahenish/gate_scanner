"""
display.py
==========
Category → user-facing display mappings, shared by the scans and dashboard
routers (previously duplicated in both).
"""
from __future__ import annotations

DISPLAY_STATUS = {
    "INVESTMENT": "BUY",
    "SWING":      "BUY",
    "POSITIONAL": "BUY",
    "WATCH":      "WATCH",
    "IGNORE":     "NO_ACTION",
}

DISPLAY_CATEGORY = {
    "INVESTMENT": "Long-Term Buy",
    "SWING":      "Swing Buy",
    "POSITIONAL": "Positional Buy",
    "WATCH":      "Watch",
    "IGNORE":     "No Action",
}


def enrich_signal_display(d: dict) -> dict:
    """Annotate a serialized signal dict with display_status / display_category."""
    cat = d.get("category", "IGNORE")
    d["display_status"] = DISPLAY_STATUS.get(cat, "NO_ACTION")
    d["display_category"] = DISPLAY_CATEGORY.get(cat, "No Action")
    return d
