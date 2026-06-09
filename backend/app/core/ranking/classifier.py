"""
classifier.py
==============
Assigns each scanned symbol to one of:

  INVESTMENT  — weekly + monthly strong stack, structurally aligned
  SWING       — daily/4h setup forming, good GATE + RR
  POSITIONAL  — 1h/30m short-term setup
  WATCH       — high contraction but no breakout yet
  IGNORE      — broken / exhausted / illiquid

Inputs are the same MTF analyses and (optional) signal that other modules produce.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.core import config


def _is_bullish_tf(tf_analysis: Dict) -> bool:
    if not tf_analysis or tf_analysis.get("data_points", 0) == 0:
        return False
    stack = tf_analysis["ema"]["stack"]
    trend = tf_analysis["structure"]["trend"]["direction"]
    return stack == "bullish" or trend == "up"


def _is_bearish_tf(tf_analysis: Dict) -> bool:
    if not tf_analysis or tf_analysis.get("data_points", 0) == 0:
        return False
    stack = tf_analysis["ema"]["stack"]
    trend = tf_analysis["structure"]["trend"]["direction"]
    return stack == "bearish" or trend == "down"


def classify(
    symbol: str,
    mtf_analysis: Dict[str, Dict],
    mtf_sum: Dict,
    signal: Optional[Dict],
) -> Dict:
    """
    Returns:
      {
        "category": "INVESTMENT" | "SWING" | "POSITIONAL" | "WATCH" | "IGNORE",
        "reasoning": str,
      }
    """
    weekly  = mtf_analysis.get("1wk", {})
    monthly = mtf_analysis.get("1mo", {})
    daily   = mtf_analysis.get("1d",  {})
    hourly  = mtf_analysis.get("60m", {})

    rank_score = signal.get("rank_score") if signal else 0.0

    # --- IGNORE first: broken or unaligned ---
    # If both weekly and monthly are bearish AND daily also bearish — distribution
    if _is_bearish_tf(weekly) and _is_bearish_tf(monthly) and _is_bearish_tf(daily):
        return {"category": "IGNORE", "reasoning": "Bearish across weekly/monthly/daily — broken structure."}

    # If we have a signal but RR/rank is too low, ignore
    if signal and signal.get("rr", {}).get("T1", 0) < config.MIN_RR_RATIO:
        return {"category": "IGNORE", "reasoning": "Signal exists but RR below threshold."}

    # --- INVESTMENT: weekly + monthly bullish, structurally aligned ---
    if _is_bullish_tf(weekly) and _is_bullish_tf(monthly):
        if rank_score >= config.CATEGORY_RULES["INVESTMENT"]["min_score"]:
            return {
                "category": "INVESTMENT",
                "reasoning": "Weekly & monthly bullish stack; high composite score — long-term position candidate.",
            }
        # Even without a fresh signal, a clean long-term structure can be investment-watch
        if not signal:
            return {
                "category": "INVESTMENT",
                "reasoning": "Weekly & monthly bullish; structurally clean even without fresh trigger.",
            }

    # --- SWING: daily bullish + GATE forming/broken ---
    if _is_bullish_tf(daily):
        gate_daily = daily.get("gate", {}).get("score", 0)
        if gate_daily >= config.CATEGORY_RULES["SWING"]["min_gate"]:
            if rank_score >= config.CATEGORY_RULES["SWING"]["min_score"] or signal:
                return {
                    "category": "SWING",
                    "reasoning": f"Daily bullish + GATE {gate_daily:.0f}; swing trade candidate.",
                }

    # --- POSITIONAL: hourly setup + reasonable alignment ---
    if _is_bullish_tf(hourly):
        gate_hour = hourly.get("gate", {}).get("score", 0)
        if gate_hour >= config.CATEGORY_RULES["POSITIONAL"]["min_gate"]:
            if signal or rank_score >= config.CATEGORY_RULES["POSITIONAL"]["min_score"]:
                return {
                    "category": "POSITIONAL",
                    "reasoning": f"1h bullish + GATE {gate_hour:.0f}; short-term positional.",
                }

    # --- WATCH: any TF has strong contraction but no breakout yet ---
    best_gate_tf = None
    best_gate = 0
    for tf, a in mtf_analysis.items():
        g = a.get("gate", {}).get("score", 0)
        if g > best_gate:
            best_gate = g
            best_gate_tf = tf
    if best_gate >= config.CATEGORY_RULES["WATCH"]["min_gate"] and not signal:
        return {
            "category": "WATCH",
            "reasoning": f"High contraction on {best_gate_tf} (GATE {best_gate:.0f}) — no breakout yet.",
        }

    return {"category": "IGNORE", "reasoning": "No qualifying setup."}
