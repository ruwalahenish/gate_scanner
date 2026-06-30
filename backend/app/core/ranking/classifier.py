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


def _best_consolidation(mtf_analysis: Dict[str, Dict]) -> tuple[str | None, float]:
    """Return (tf, consolidation_strength) for the tightest base across TFs."""
    best_tf, best = None, 0.0
    for tf, a in mtf_analysis.items():
        cs = (a.get("gate", {}) or {}).get("consolidation_strength", 0.0)
        if cs > best:
            best_tf, best = tf, cs
    return best_tf, best


def _watch_reason(daily: Dict, rng: Dict) -> tuple[str, Optional[float]]:
    """
    Explain WHY a forming stock is only a WATCH (not yet a GATE buy) and return
    the critical level to watch (the breakout trigger).

    A stock is on the watchlist while it completes a price or time correction, or
    while it coils toward the breakout — it is NOT yet ready for a GATE buy.
    """
    state = rng.get("state")
    range_low = rng.get("range_low")
    breakout_level = rng.get("breakout_level")
    corr = ((daily.get("structure", {}) or {}).get("correction", {}) or {}).get("type", "none")
    comps = (daily.get("gate", {}) or {}).get("components", {}) or {}

    parts: list[str] = []
    if not rng.get("valid") or state == "NO_GATE":
        parts.append("Base still forming — no tight consolidation box yet; needs more time to coil.")
    elif state == "ACCUMULATION":
        if corr == "price":
            parts.append("Price correction in progress — waiting for the pullback to finish and the base to tighten.")
        elif corr == "time":
            parts.append("Time correction in progress — coiling sideways; waiting for the base to mature.")
        else:
            parts.append("Consolidating inside the range — not yet pressing the breakout trigger.")
        if comps.get("volume_pattern", 50.0) < 40.0:
            parts.append("Volume has not dried up / no buildup yet.")
    elif state == "BUY_ZONE":
        parts.append("At the breakout zone but the setup is not yet favorable (risk-reward / structure).")
    else:
        parts.append("Awaiting a valid GATE setup.")

    if breakout_level:
        lvl = f"Critical level: breakout above {breakout_level:.2f}"
        lvl += f" (support {range_low:.2f})." if range_low else "."
        parts.append(lvl)
    return " ".join(parts), breakout_level


def classify(
    symbol: str,
    mtf_analysis: Dict[str, Dict],
    mtf_sum: Dict,
    signal: Optional[Dict],
) -> Dict:
    """
    Assigns each symbol to one of the five GATE strategy lists (§14):

      INVESTMENT  — weekly + monthly bullish, high rank (long-horizon buy)
      SWING       — daily breakout confirmed, good GATE + rank
      POSITIONAL  — 1h breakout, good GATE + rank (requires 60m in SCAN_TIMEFRAMES)
      WATCH       — forming the GATE but breakout not yet happened
      IGNORE      — broken / extended / no setup
    """
    weekly  = mtf_analysis.get("1wk", {})
    monthly = mtf_analysis.get("1mo", {})
    daily   = mtf_analysis.get("1d",  {})
    hourly  = mtf_analysis.get("60m", {})
    daily_rng = (daily.get("gate", {}) or {}).get("range", {}) or {}

    # --- IGNORE: broken structure across the board ---
    if _is_bearish_tf(weekly) and _is_bearish_tf(monthly) and _is_bearish_tf(daily):
        return {"category": "IGNORE", "reasoning": "Bearish across weekly/monthly/daily — broken structure."}

    # --- No actionable breakout signal → WATCH (forming) or IGNORE ---
    if not signal:
        best_tf, best_cs = _best_consolidation(mtf_analysis)
        daily_state = daily_rng.get("state")
        forming = daily_state in ("ACCUMULATION", "BUY_ZONE", "NO_GATE")
        if best_cs >= config.CATEGORY_RULES["WATCH"]["min_gate"] and forming:
            reason, critical = _watch_reason(daily, daily_rng)
            return {
                "category": "WATCH",
                "reasoning": f"Forming GATE on {best_tf} (consolidation {best_cs:.0f}). {reason}",
                "critical_level": critical,
            }
        return {"category": "IGNORE", "reasoning": "No actionable breakout setup."}

    # --- A valid breakout signal exists from here on ---
    if signal.get("rr", {}).get("T2", 0) < config.MIN_RR_RATIO:
        return {"category": "IGNORE", "reasoning": "Breakout signal but RR below threshold."}

    # --- Route BREAKOUT_CONFIRMED signals into the appropriate buy category ---
    rank_score  = signal.get("rank_score", 0.0)
    daily_gate  = (daily.get("gate", {}) or {}).get("score", 0.0)
    hourly_gate = (hourly.get("gate", {}) or {}).get("score", 0.0)
    bl = signal.get("breakout_level")
    ready = f"broke out above {bl:.2f}" if bl else "broke out"

    inv = config.CATEGORY_RULES["INVESTMENT"]
    if (_is_bullish_tf(weekly) and _is_bullish_tf(monthly)
            and rank_score >= inv["min_score"]):
        return {
            "category": "INVESTMENT",
            "reasoning": f"Weekly & monthly bullish, {ready}, rank {rank_score:.0f} — long-term buy.",
        }

    swing = config.CATEGORY_RULES["SWING"]
    if _is_bullish_tf(daily) and daily_gate >= swing["min_gate"] and rank_score >= swing["min_score"]:
        return {
            "category": "SWING",
            "reasoning": f"Daily bullish, {ready} (GATE {daily_gate:.0f}), rank {rank_score:.0f} — swing buy.",
        }

    pos = config.CATEGORY_RULES["POSITIONAL"]
    if _is_bullish_tf(hourly) and hourly_gate >= pos["min_gate"] and rank_score >= pos["min_score"]:
        return {
            "category": "POSITIONAL",
            "reasoning": f"1h bullish, {ready} (GATE {hourly_gate:.0f}) — positional buy.",
        }

    # Signal exists but scores below category floors → SWING if daily bullish, else WATCH
    if _is_bullish_tf(daily):
        return {
            "category": "SWING",
            "reasoning": f"Daily bullish, {ready}; rank {rank_score:.0f} — swing buy.",
        }
    return {
        "category": "WATCH",
        "reasoning": f"{ready} without higher-TF confirmation — watching for daily breakout.",
    }
