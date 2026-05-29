"""
ranking_engine.py
==================
Ranks generated signals by a weighted composite score.
"""

from __future__ import annotations

from typing import Dict, List

from . import config


def composite_score(signal: Dict) -> float:
    """
    Composite ranking score 0..100 — heavier-weighted on GATE strength and
    MTF alignment per RANK_WEIGHTS.
    """
    if not signal:
        return 0.0
    w = config.RANK_WEIGHTS
    # Cap RR contribution: anything beyond RR=5 doesn't keep adding linearly
    rr_norm = min(signal.get("rr", {}).get("T2", 0.0) / 5.0, 1.0) * 100

    score = (
        w["gate_strength"]        * signal.get("gate_strength", 0.0)
        + w["mtf_alignment"]      * signal.get("mtf_alignment_pct", 0.0)
        + w["structure_quality"]  * signal.get("structure_quality", 0.0)
        + w["breakout_probability"] * signal.get("breakout_probability", 0.0)
        + w["rr_ratio"]           * rr_norm
    )
    # HTF confirmation bonus
    if signal.get("htf_confirmed"):
        score *= 1.08
    return float(min(100.0, max(0.0, score)))


def rank(signals: List[Dict]) -> List[Dict]:
    """Attach `rank_score` to each signal and return them sorted desc."""
    for s in signals:
        s["rank_score"] = composite_score(s)
    return sorted(signals, key=lambda x: x["rank_score"], reverse=True)
