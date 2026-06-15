"""
range_engine.py
===============
Consolidation-range ("gate") detection and breakout-state classification — the
spine of the reworked GATE strategy.

A "gate" is the consolidation box price coils inside before an expansion. A valid
BUY opportunity exists only when price is APPROACHING the breakout (BUY_ZONE) or
has JUST broken out (BREAKOUT_CONFIRMED) — never once it is EXTENDED.

States
------
  NO_GATE            no valid consolidation box on the lookback window
  BROKEN_DOWN        close below the box → support failed
  ACCUMULATION       close inside the box but far below range_high
  BUY_ZONE           close within BUY_ZONE_MAX_PCT below range_high (coiling at the top)
  BREAKOUT_CONFIRMED close 0–BREAKOUT_CONFIRM_MAX_PCT above range_high (fresh breakout)
  EXTENDED           close > EXTENDED_PCT above range_high (already moved → reject)
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from app.core import config
from app.core.analysis import indicators as ind


def detect_consolidation(df: pd.DataFrame, lookback: Optional[int] = None) -> Dict:
    """
    Detect the consolidation box over the trailing `lookback` bars.

    Returns a dict with range_high, range_low, height_pct, duration_bars,
    tightness (0–1, higher = tighter coil) and `valid`.
    """
    lookback = lookback or config.RANGE_LOOKBACK
    invalid = {
        "range_high": None, "range_low": None, "height_pct": None,
        "duration_bars": 0, "tightness": 0.0, "valid": False,
    }
    if df is None or df.empty or len(df) < max(lookback, config.RANGE_MIN_DURATION):
        return invalid

    window = df.iloc[-lookback:]
    range_high = float(window["High"].max())
    range_low = float(window["Low"].min())
    if range_low <= 0 or range_high <= range_low:
        return invalid

    height_pct = (range_high - range_low) / range_low
    if height_pct > config.RANGE_MAX_HEIGHT_PCT:
        return invalid  # too tall to be a base — this is a trend leg, not a gate

    # Tightness: recent ATR small relative to the box height = a tight coil.
    atr_series = ind.atr(df, 14)
    last_atr = atr_series.iloc[-1] if not atr_series.dropna().empty else None
    box_abs = range_high - range_low
    if last_atr is None or pd.isna(last_atr) or box_abs <= 0:
        tightness = 0.0
    else:
        # atr <= box/RANGE_TIGHTNESS_ATR_MULT → fully tight (1.0)
        ref = box_abs / config.RANGE_TIGHTNESS_ATR_MULT
        tightness = float(max(0.0, min(1.0, ref / float(last_atr)))) if last_atr > 0 else 0.0

    return {
        "range_high": range_high,
        "range_low": range_low,
        "height_pct": float(height_pct),
        "duration_bars": int(len(window)),
        "tightness": tightness,
        "valid": True,
    }


def breakout_state(df: pd.DataFrame, box: Dict) -> Dict:
    """
    Classify where the latest close sits relative to the consolidation box.

    Returns state, breakout_level (anticipatory trigger), distance_to_breakout_pct
    (signed: positive = still below the trigger), and proximity_score (0–100).
    """
    neutral = {
        "state": "NO_GATE", "breakout_level": None,
        "distance_to_breakout_pct": None, "proximity_score": 0.0,
    }
    if not box or not box.get("valid") or df is None or df.empty:
        return neutral

    close = float(df["Close"].iloc[-1])
    range_high = box["range_high"]
    range_low = box["range_low"]
    breakout_level = range_high * (1.0 + config.BREAKOUT_TRIGGER_BUFFER_PCT)
    distance_to_breakout_pct = (breakout_level - close) / close

    if close < range_low:
        return {**neutral, "state": "BROKEN_DOWN", "breakout_level": breakout_level,
                "distance_to_breakout_pct": float(distance_to_breakout_pct)}

    if close <= range_high:
        below_pct = (range_high - close) / range_high
        if below_pct <= config.BUY_ZONE_MAX_PCT:
            state = "BUY_ZONE"
            # closer to the high → higher score (80 at band edge, 100 at the high)
            proximity = 80.0 + 20.0 * (1.0 - below_pct / config.BUY_ZONE_MAX_PCT)
        else:
            state = "ACCUMULATION"
            # deeper in the box → lower score (capped at the BUY_ZONE floor)
            span = max(config.RANGE_MAX_HEIGHT_PCT, config.BUY_ZONE_MAX_PCT)
            proximity = 70.0 * max(0.0, 1.0 - below_pct / span)
    else:
        above_pct = (close - range_high) / range_high
        if above_pct <= config.BREAKOUT_CONFIRM_MAX_PCT:
            state = "BREAKOUT_CONFIRMED"
            proximity = 100.0
        else:
            state = "EXTENDED"
            proximity = 10.0

    return {
        "state": state,
        "breakout_level": float(breakout_level),
        "distance_to_breakout_pct": float(distance_to_breakout_pct),
        "proximity_score": float(max(0.0, min(100.0, proximity))),
    }


def analyze_range(df: pd.DataFrame, lookback: Optional[int] = None) -> Dict:
    """Convenience: detect the box and classify the breakout state in one call."""
    box = detect_consolidation(df, lookback)
    state = breakout_state(df, box)
    return {**box, **state}
