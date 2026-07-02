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


def _try_window(df: pd.DataFrame, lb: int) -> Dict:
    """
    Attempt to detect a consolidation box over the `lb` bars PRECEDING the
    latest bar.

    The box must exclude the current/latest bar: breakout_state() classifies
    that latest bar's Close against this box, and a candle's own High is
    always >= its own Close, so a box whose window included the current bar
    would make range_high >= current High >= current Close always — making
    "close > range_high" (BREAKOUT_CONFIRMED / EXTENDED) mathematically
    unreachable. The box represents the PRIOR range price is breaking out of.
    """
    invalid = {
        "range_high": None, "range_low": None, "height_pct": None,
        "duration_bars": 0, "tightness": 0.0, "valid": False,
    }
    if len(df) < max(lb, config.RANGE_MIN_DURATION) + 1:
        return invalid
    window = df.iloc[-(lb + 1):-1]
    range_high = float(window["High"].max())
    range_low = float(window["Low"].min())
    if range_low <= 0 or range_high <= range_low:
        return invalid
    height_pct = (range_high - range_low) / range_low
    if height_pct > config.RANGE_MAX_HEIGHT_PCT:
        return invalid
    atr_series = ind.atr(df, 14)
    # ATR as of the box's own last bar (not today's, which may already reflect
    # the breakout's own volatility expansion) — a like-for-like tightness read.
    last_atr = atr_series.iloc[-2] if len(atr_series.dropna()) >= 2 else None
    box_abs = range_high - range_low
    tightness = 0.0
    if last_atr is not None and not pd.isna(last_atr) and box_abs > 0 and last_atr > 0:
        ref = box_abs / config.RANGE_TIGHTNESS_ATR_MULT
        tightness = float(max(0.0, min(1.0, ref / float(last_atr))))
    return {
        "range_high": range_high,
        "range_low": range_low,
        "height_pct": float(height_pct),
        "duration_bars": int(len(window)),
        "tightness": tightness,
        "valid": True,
    }


def detect_consolidation(df: pd.DataFrame, lookback: Optional[int] = None) -> Dict:
    """
    Detect the consolidation box over the trailing bars.

    Tries the primary `lookback` first, then progressively shorter windows
    (RANGE_LOOKBACK_FALLBACKS). This allows the detector to find a recent tight
    base at EMA200 even when a prior correction leg is still inside the primary
    window (which would otherwise inflate the box height above RANGE_MAX_HEIGHT_PCT
    and cause the base to be missed entirely).
    """
    if df is None or df.empty:
        return {
            "range_high": None, "range_low": None, "height_pct": None,
            "duration_bars": 0, "tightness": 0.0, "valid": False,
        }
    primary = lookback or config.RANGE_LOOKBACK
    for lb in [primary] + list(config.RANGE_LOOKBACK_FALLBACKS):
        if lb < config.RANGE_MIN_DURATION:
            continue
        result = _try_window(df, lb)
        if result["valid"]:
            return result
    return {
        "range_high": None, "range_low": None, "height_pct": None,
        "duration_bars": 0, "tightness": 0.0, "valid": False,
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


def count_level_tests(
    df: pd.DataFrame,
    level: float,
    lookback: int,
    tolerance: float,
    exclude_bars: int = 0,
) -> int:
    """
    Count how many times price approached `level` (within `tolerance`) and failed
    to close decisively above it, in the `lookback` bars before the most recent
    `exclude_bars` (typically the current box's own duration, so the in-progress
    consolidation isn't miscounted as a failed test of its own high).

    This operationalizes "a weak poke above that closes back inside the gate does
    not count" (§7) applied to the *level itself*, not just the current candle:
    a breakout at a level that has already failed repeatedly nearby is a chased/
    whipsawed level, not a fresh gate — the dominant pattern behind the "too late"
    and "wrong breakout point" reference charts.
    """
    if df is None or df.empty or level is None or level <= 0:
        return 0
    n = len(df)
    end = max(0, n - exclude_bars)
    start = max(0, end - lookback)
    if end <= start:
        return 0

    highs = df["High"].values[start:end]
    closes = df["Close"].values[start:end]
    band_low = level * (1.0 - tolerance)

    tests = 0
    in_test = False
    broke_through = False
    for high, close in zip(highs, closes):
        if high >= band_low:
            if not in_test:
                in_test, broke_through = True, False
            if close > level:
                broke_through = True
        else:
            if in_test and not broke_through:
                tests += 1
            in_test = False
    if in_test and not broke_through:
        tests += 1
    return tests


def analyze_range(df: pd.DataFrame, lookback: Optional[int] = None) -> Dict:
    """
    Convenience: detect the box, classify the breakout state, and count prior
    failed tests of the box's range_high in one call.

    prior_level_failures is computed here (not just when a signal fires) so both
    signal_engine's BUY hard-gate and classifier's WATCH eligibility check can
    read it directly from the per-TF gate/range dict without recomputing it or
    needing raw OHLCV access.
    """
    box = detect_consolidation(df, lookback)
    state = breakout_state(df, box)
    prior_failures = 0
    if box.get("valid") and box.get("range_high"):
        # +1 because the box (duration_bars) already excludes the current bar.
        exclude_bars = int(box.get("duration_bars") or 0) + 1
        prior_failures = count_level_tests(
            df, box["range_high"], config.LEVEL_FRESHNESS_LOOKBACK,
            config.LEVEL_FRESHNESS_TOLERANCE, exclude_bars=exclude_bars,
        )
    return {**box, **state, "prior_level_failures": prior_failures}
