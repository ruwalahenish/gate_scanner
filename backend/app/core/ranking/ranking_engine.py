"""
ranking_engine.py
==================
Ranks generated signals by a weighted composite score.
"""

from __future__ import annotations

from typing import Dict, List

from app.core import config


def composite_score(signal: Dict) -> float:
    """
    Composite ranking score 0..100 blending the GATE strength composite with
    breakout readiness, structural RR, relative strength, sector momentum and
    fundamental quality (RANK_WEIGHTS). HTF confirmation adds a small bonus.
    """
    if not signal:
        return 0.0
    w = config.RANK_WEIGHTS
    # Cap RR contribution: anything beyond RR=5 doesn't keep adding linearly.
    # "or 0.0" guards against None stored under the "T2" key.
    rr_norm = min((signal.get("rr", {}).get("T2") or 0.0) / 5.0, 1.0) * 100

    score = (
        w["gate_strength"]       * signal.get("gate_strength", 0.0)
        + w["breakout_readiness"] * signal.get("breakout_readiness", 0.0)
        + w["rr_ratio"]          * rr_norm
        + w["relative_strength"] * signal.get("rs_score", config.RS_NEUTRAL)
        + w["sector_momentum"]   * signal.get("sector_momentum", config.SECTOR_NEUTRAL)
        + w["fundamental_score"] * signal.get("fundamental_score", config.FUNDAMENTAL_NEUTRAL)
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
