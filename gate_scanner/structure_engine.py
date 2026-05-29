"""
structure_engine.py
====================
Analyzes market structure:

  * Trend direction (uptrend / downtrend / range) using EMA slope + ADX
  * Correction TYPE — price correction (price moving to EMA) vs time correction
    (EMA moving to price, i.e. price ranges sideways while EMAs catch up)
  * Phase — "trending", "correcting", "transitioning"
  * Structure quality score
  * Correction age — how far along the current correction is (MISS-3 fix)
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from . import config
from . import indicators as ind
from . import ema_engine


def _slope(series: pd.Series, bars: int = 10) -> Optional[float]:
    """Average per-bar slope of `series` over last `bars` bars, normalized by price."""
    if len(series.dropna()) < bars + 1:
        return None
    seg = series.dropna().iloc[-bars:]
    if seg.iloc[0] == 0:
        return None
    return float((seg.iloc[-1] - seg.iloc[0]) / seg.iloc[0] / bars)


def trend_direction(df: pd.DataFrame) -> Dict:
    """
    Returns trend assessment using EMA slope hierarchy + ADX.
      direction: "up" | "down" | "range"
      strength:  0..100  (mostly ADX-based)
    """
    if df is None or df.empty or len(df) < 50:
        return {"direction": "range", "strength": 0.0, "adx": None}

    df = ema_engine.compute_emas(df)
    s50  = _slope(df["EMA50"], 10)
    s100 = _slope(df["EMA100"], 10)

    adx_series = ind.adx(df, 14)
    adx_val = adx_series.iloc[-1] if not adx_series.empty else None
    if pd.isna(adx_val):
        adx_val = None

    direction = "range"
    if s50 is not None and s100 is not None:
        if s50 > 0 and s100 > 0:
            direction = "up"
        elif s50 < 0 and s100 < 0:
            direction = "down"

    # Strength from ADX: <20 weak, 25-50 strong, >50 very strong
    if adx_val is None:
        strength = 0.0
    else:
        strength = float(min(100.0, max(0.0, adx_val * 1.5)))

    return {"direction": direction, "strength": strength, "adx": adx_val}


def correction_type(df: pd.DataFrame) -> Dict:
    """
    Distinguishes price correction vs time correction.

      * Price correction: price has moved toward an EMA (deepened pullback)
      * Time correction:  price drifts sideways while EMAs catch up (range + flat EMAs)

    Returns:
      {
        "type": "price" | "time" | "none",
        "depth_ema": which EMA price is testing (20/50/100/200),
        "confidence": 0..100,
      }
    """
    if df is None or df.empty or len(df) < 50:
        return {"type": "none", "depth_ema": None, "confidence": 0.0}

    ema = ema_engine.analyze(df)
    corr = ema["correction"]
    conv = ema["convergence"]

    # Time correction: convergence active AND recent range is narrow
    if conv.get("is_converging"):
        df_e = ema_engine.compute_emas(df)
        e50 = df_e["EMA50"].iloc[-1]
        if e50 and not pd.isna(e50):
            recent_std = df["Close"].iloc[-20:].std() / e50
            if recent_std < 0.02:
                return {"type": "time", "depth_ema": corr.get("ema"), "confidence": 75.0}
            return {"type": "time", "depth_ema": corr.get("ema"), "confidence": 55.0}

    # Price correction: price within tolerance of an EMA
    if corr.get("phase") == "at_ema" and corr.get("ema") is not None:
        ema_depth = corr["ema"]
        conf_map = {20: 50.0, 50: 65.0, 100: 80.0, 200: 90.0}
        return {
            "type": "price",
            "depth_ema": ema_depth,
            "confidence": conf_map.get(ema_depth, 50.0),
        }

    return {"type": "none", "depth_ema": None, "confidence": 0.0}


def phase(df: pd.DataFrame) -> str:
    """
    Returns one of:
      * "trending"      — strong directional move
      * "correcting"    — price or time correction active
      * "contracting"   — volatility squeeze (GATE forming)
      * "transitioning" — between phases
    """
    if df is None or df.empty:
        return "transitioning"

    t = trend_direction(df)
    c = correction_type(df)
    ema = ema_engine.analyze(df)

    if ema["convergence"].get("is_converging") or ema["compression_score"] >= 70:
        return "contracting"
    if c["type"] in ("price", "time"):
        return "correcting"
    if t["direction"] in ("up", "down") and t["strength"] >= 35:
        return "trending"
    return "transitioning"


def structure_quality(df: pd.DataFrame) -> float:
    """
    Composite structure quality score (0..100):

      * higher when stack is clean (bullish or bearish)
      * higher when trend strength is high
      * higher when price respects EMAs (low excursion)
    """
    if df is None or df.empty or len(df) < 50:
        return 0.0

    df_e = ema_engine.compute_emas(df)
    stack = ema_engine.stack_state(df)
    t = trend_direction(df)

    stack_score = 100.0 if stack in ("bullish", "bearish") else 40.0
    trend_score = t["strength"]

    # EMA respect: distance of last 20 closes from EMA50 normalized
    e50 = df_e["EMA50"].iloc[-20:]
    closes = df["Close"].iloc[-20:]
    if e50.isna().any() or e50.mean() == 0:
        respect = 50.0
    else:
        mean_dev = ((closes - e50).abs() / e50).mean()
        respect = max(0.0, min(100.0, 100.0 * (1.0 - mean_dev / 0.10)))

    composite = 0.4 * stack_score + 0.35 * trend_score + 0.25 * respect
    return float(composite)


def swing_levels(df: pd.DataFrame) -> Dict:
    """Last swing high / low — used by signal engine for targets/SL."""
    if df is None or df.empty or len(df) < 10:
        return {"last_swing_high": None, "last_swing_low": None}
    return ind.last_swing_levels(df, left=3, right=3)


# -----------------------------------------------------------------------------
# MISS-3 fix: Correction age estimation
# -----------------------------------------------------------------------------
def correction_age(df: pd.DataFrame, timeframe: str = "") -> Dict:
    """
    Estimates how far along the current correction is relative to the typical
    duration for this timeframe (from config.CORRECTION_DURATIONS).

    Methodology: count bars elapsed since the last confirmed swing high
    (approximate start of the correction) and express as a % of the midpoint
    of the expected correction duration range.

    Returns:
      {
        "age_bars":  int    — bars elapsed since the last swing high
        "age_pct":   float  — 0..100+, % of expected correction duration elapsed
        "mature":    bool   — True when >= 70% of the minimum expected duration
        "expected_min_bars": int
        "expected_max_bars": int
      }
    """
    empty = {
        "age_bars": 0,
        "age_pct": 0.0,
        "mature": False,
        "expected_min_bars": 0,
        "expected_max_bars": 0,
    }
    if df is None or df.empty or len(df) < 20:
        return empty

    min_bars, max_bars = config.CORRECTION_DURATIONS.get(timeframe, (50, 200))
    mid_bars = (min_bars + max_bars) / 2

    highs_mask = ind.swing_highs(df, left=3, right=3)
    if not highs_mask.any():
        return {**empty, "expected_min_bars": min_bars, "expected_max_bars": max_bars}

    last_high_pos = int(df.index.get_loc(highs_mask[highs_mask].index[-1]))
    bars_elapsed = len(df) - 1 - last_high_pos

    age_pct = min(150.0, (bars_elapsed / mid_bars) * 100) if mid_bars > 0 else 0.0
    mature = bars_elapsed >= int(min_bars * 0.7)

    return {
        "age_bars": bars_elapsed,
        "age_pct": float(age_pct),
        "mature": mature,
        "expected_min_bars": min_bars,
        "expected_max_bars": max_bars,
    }


def analyze(df: pd.DataFrame, timeframe: str = "") -> Dict:
    return {
        "trend":             trend_direction(df),
        "correction":        correction_type(df),
        "phase":             phase(df),
        "structure_quality": structure_quality(df),
        "swing_levels":      swing_levels(df),
        "correction_age":    correction_age(df, timeframe=timeframe),  # MISS-3
    }
