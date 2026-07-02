"""
classifier.py
==============
Assigns each scanned symbol to one of:

  INVESTMENT  — weekly + monthly strong stack, structurally aligned
  SWING       — daily/4h setup forming, good GATE + RR
  POSITIONAL  — 1h/30m short-term setup
  WATCH       — daily gate is genuinely shut (same structural bar as an actionable
                gate — trend health, real prior correction, fresh level, favorable
                projected RR) but the breakout hasn't triggered yet
  IGNORE      — broken / exhausted / illiquid / below the quality bar

WATCH and the BUY categories share the same structural quality gates on purpose:
a WATCH candidate must already look like a Good/Perfect Gate reference setup, not
merely "less bad" than an IGNORE. Borderline/uncertain candidates land in IGNORE,
never WATCH or a BUY category — quality over quantity.

Inputs are the same MTF analyses and (optional) signal that other modules produce.
"""

from __future__ import annotations

from typing import Dict, Optional

from app.core import config
from app.core.analysis import signal_engine


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

    # --- No actionable breakout signal → WATCH (forming, high quality only) or IGNORE ---
    if not signal:
        daily_gate_d = daily.get("gate", {}) or {}
        daily_state = daily_rng.get("state")
        forming = daily_state in ("ACCUMULATION", "BUY_ZONE", "NO_GATE")
        if not forming:
            return {"category": "IGNORE", "reasoning": "No actionable breakout setup."}

        # WATCH must clear the SAME structural bar as an actionable gate — just
        # without the breakout having triggered yet. Each check maps to a recurring
        # disqualifying pattern from the Bad/Late/Wrong-breakout/Neutral reference charts.
        if not bool(daily_gate_d.get("is_gate")):
            return {"category": "IGNORE", "reasoning": "Consolidation not tight enough yet — not a real gate."}

        daily_ema = daily.get("ema", {}) or {}
        if not daily_ema.get("correction_validated", True):
            return {"category": "IGNORE", "reasoning": "No genuine prior trend corrected into this base — fake/insufficient correction."}

        if daily_ema.get("ema_200_slope", 0.0) < 0:
            return {"category": "IGNORE", "reasoning": "200 EMA still declining — this is a bounce inside a downtrend, not a completed correction."}

        prior_failures = int(daily_rng.get("prior_level_failures") or 0)
        if prior_failures > config.LEVEL_FRESHNESS_MAX_FAILURES:
            return {
                "category": "IGNORE",
                "reasoning": f"This level has already failed {prior_failures} time(s) recently — chased/whipsawed zone, not a fresh gate.",
            }

        # §3 gate-position check: the forming base must be at/near EMA200.
        # Consolidations far below EMA200 are bear-market bases, not GATE setups.
        _daily_ema200 = float(daily_ema.get("ema_values", {}).get("EMA200") or 0)
        _rng_high = float(daily_rng.get("range_high") or 0)
        _rng_low  = float(daily_rng.get("range_low")  or 0)
        if _daily_ema200 > 0 and _rng_high > 0:
            if _rng_high < _daily_ema200 * (1 - config.GATE_PRICE_MIN_EMA200):
                return {"category": "IGNORE", "reasoning": "Base forming below EMA200 — breakdown phase, not GATE."}
            # Upper-bound: box floor more than 10% above EMA200 → post-breakout base, not GATE.
            if _rng_low > 0 and _rng_low > _daily_ema200 * (1 + config.GATE_RANGE_MAX_ABOVE_EMA200):
                return {"category": "IGNORE", "reasoning": "Base forming too far above EMA200 — extended zone after prior breakout, not a new GATE correction."}
        elif _daily_ema200 > 0:
            # No valid range detected yet (NO_GATE) — use EMA20 as price proxy
            _ema20 = float(daily_ema.get("ema_values", {}).get("EMA20") or 0)
            if _ema20 > 0 and _ema20 < _daily_ema200 * (1 - config.GATE_PRICE_MIN_EMA200):
                return {"category": "IGNORE", "reasoning": "Price below EMA200 — breakdown phase, not GATE."}
            if _ema20 > 0 and _ema20 > _daily_ema200 * (1 + config.GATE_RANGE_MAX_ABOVE_EMA200):
                return {"category": "IGNORE", "reasoning": "Price too far above EMA200 — extended zone, not a GATE correction."}

        # Sufficient upside potential remaining + favorable RR, projected as if the
        # breakout triggered right now at range_high (the cleanest possible entry —
        # a later, higher realized entry only makes the actual RR worse than this).
        if _rng_high > 0 and _rng_low > 0:
            sl_tf = config.SL_TIMEFRAME_MAP.get("1d")  # "4h"
            sl_ema200 = float(
                (mtf_analysis.get(sl_tf, {}) or {}).get("ema", {}).get("ema_values", {}).get("EMA200") or 0
            )
            if sl_ema200 <= 0:
                return {"category": "IGNORE", "reasoning": "No lower-timeframe data to project a stop-loss / risk-reward."}
            projected_entry = _rng_high * (1 + config.BREAKOUT_TRIGGER_BUFFER_PCT)
            projected_sl = sl_ema200 * (1 - 0.005)
            if projected_sl >= projected_entry:
                return {"category": "IGNORE", "reasoning": "Degenerate projected stop-loss — SL would sit above the breakout trigger."}
            targets = signal_engine.measured_move_targets(projected_entry, _rng_high, _rng_low, "1d")
            projected_rr = signal_engine.compute_rr(projected_entry, projected_sl, targets["T2"], "BUY")
            if projected_rr < config.MIN_RR_RATIO:
                return {
                    "category": "IGNORE",
                    "reasoning": f"Projected RR ({projected_rr:.1f}x) below {config.MIN_RR_RATIO}x even at a clean breakout — insufficient upside for the risk.",
                }

        reason, critical = _watch_reason(daily, daily_rng)
        return {
            "category": "WATCH",
            "reasoning": f"Forming a high-quality GATE on daily (score {daily_gate_d.get('score', 0):.0f}). {reason}",
            "critical_level": critical,
        }

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

    # A confirmed breakout signal that still doesn't clear any category's quality
    # bar is exactly the "borderline/uncertain candidate" this scanner excludes
    # from both WATCH and BUY entirely — not silently downgraded to either.
    return {
        "category": "IGNORE",
        "reasoning": f"{ready} but below the quality bar for any BUY category (GATE {daily_gate:.0f}, rank {rank_score:.0f}).",
    }
