"""
multi_timeframe.py
===================
Combines per-timeframe analyses into a multi-timeframe (MTF) picture.

Key concepts:

  * Alignment: do multiple TFs agree on direction?
  * Hierarchy: smaller TF expansion *leads* larger TF expansion
  * The "leading TF" is the smallest TF where a GATE has just broken or is
    breaking — this is the entry trigger TF.
  * The "confirmation TF" is the next-larger TF — must show same bias.

Outputs are designed to feed directly into signal_engine.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.core import config
from app.core.analysis import ema_engine
from app.core.analysis import contraction_engine
from app.core.analysis import structure_engine


def analyze_timeframe(df, timeframe: str = "", symbol: str = "") -> Dict:
    """
    Run all engines on a single timeframe.

    BUG-1 fix:  timeframe + symbol are passed through so ema_engine can apply
                the monthly blue-chip EMA100 exception correctly.
    MISS-3 fix: timeframe is passed to structure_engine for correction_age.
    """
    return {
        "ema":          ema_engine.analyze(df, timeframe=timeframe, symbol=symbol),
        "structure":    structure_engine.analyze(df, timeframe=timeframe),
        "gate":         contraction_engine.gate_score(df),
        "breakout_prob":contraction_engine.breakout_probability(df),
        "data_points":  int(len(df)) if df is not None else 0,
    }


def _direction(tf_analysis: Dict) -> str:
    """Coerce a TF's bias into 'up' | 'down' | 'neutral'."""
    stack    = tf_analysis["ema"]["stack"]
    trend    = tf_analysis["structure"]["trend"]["direction"]
    gate_bias = tf_analysis["gate"]["direction_bias"]

    votes = []
    if stack == "bullish":  votes.append("up")
    elif stack == "bearish": votes.append("down")
    if trend == "up":        votes.append("up")
    elif trend == "down":    votes.append("down")
    if gate_bias == "bullish":  votes.append("up")
    elif gate_bias == "bearish": votes.append("down")

    if not votes:
        return "neutral"
    ups   = votes.count("up")
    downs = votes.count("down")
    if ups > downs:   return "up"
    if downs > ups:   return "down"
    return "neutral"


def alignment_score(mtf: Dict[str, Dict]) -> Dict:
    """
    Across all TFs analyzed, compute:
      * dominant_direction
      * alignment_pct  (0..100) — fraction of TFs agreeing
      * aligned_tfs    list
      * disagreeing_tfs list
    """
    dirs = {tf: _direction(a) for tf, a in mtf.items() if a["data_points"] > 0}
    if not dirs:
        return {
            "dominant_direction": "neutral",
            "alignment_pct": 0.0,
            "aligned_tfs": [],
            "disagreeing_tfs": [],
        }

    ups   = [tf for tf, d in dirs.items() if d == "up"]
    downs = [tf for tf, d in dirs.items() if d == "down"]

    if len(ups) > len(downs):
        dom     = "up"
        aligned = ups
        disagree = [tf for tf, d in dirs.items() if d != "up"]
    elif len(downs) > len(ups):
        dom     = "down"
        aligned = downs
        disagree = [tf for tf, d in dirs.items() if d != "down"]
    else:
        dom      = "neutral"
        aligned  = []
        disagree = list(dirs.keys())

    pct = (len(aligned) / len(dirs)) * 100.0
    return {
        "dominant_direction": dom,
        "alignment_pct":      pct,
        "aligned_tfs":        aligned,
        "disagreeing_tfs":    disagree,
    }


def leading_timeframe(mtf: Dict[str, Dict]) -> Optional[str]:
    """
    The smallest TF that currently shows a GATE (score >= 55) or a fresh breakout.
    This is the entry-trigger TF in the GATE Strategy ("expansion begins on smaller TFs").
    """
    for tf in config.TIMEFRAME_ORDER:           # ascending — smallest first
        a = mtf.get(tf)
        if not a or a["data_points"] == 0:
            continue
        if a["gate"]["is_gate"]:
            return tf
        if a["breakout_prob"] >= 60:
            return tf
    return None


def confirmation_timeframe(leading_tf: str) -> Optional[str]:
    """The next-larger TF — provides HTF confirmation."""
    if leading_tf not in config.TIMEFRAME_ORDER:
        return None
    idx = config.TIMEFRAME_ORDER.index(leading_tf)
    if idx + 1 >= len(config.TIMEFRAME_ORDER):
        return None
    return config.TIMEFRAME_ORDER[idx + 1]


def mtf_summary(mtf: Dict[str, Dict]) -> Dict:
    """One-shot MTF summary for signal generation."""
    align   = alignment_score(mtf)
    lead    = leading_timeframe(mtf)
    confirm = confirmation_timeframe(lead) if lead else None

    confirmed = False
    if lead and confirm and confirm in mtf:
        lead_dir = _direction(mtf[lead])
        conf_dir = _direction(mtf[confirm])
        confirmed = (lead_dir != "neutral") and (lead_dir == conf_dir)

    return {
        "alignment":      align,
        "leading_tf":     lead,
        "confirmation_tf":confirm,
        "htf_confirmed":  confirmed,
        "per_tf_direction": {tf: _direction(a) for tf, a in mtf.items() if a["data_points"] > 0},
    }
