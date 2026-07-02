"""
ema_engine.py
==============
Analyzes EMA structure per the GATE Strategy:

  * stack direction (bullish/bearish/mixed)
  * compression score (how tight are EMA20/50/100/200)
  * correction level (which EMA is price testing — 1st/2nd/3rd/major)
  * convergence detection (time correction completing)
  * bounce_sequence_valid (did corrections follow 20->50->100->200 order?)
  * correction_validated (did the last correction touch EMA200 before reversing?)

All functions are pure: input DataFrame -> output dict / Series.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.core import config
from app.core.analysis import indicators as ind


def _last(series: pd.Series) -> Optional[float]:
    if series is None or series.empty or pd.isna(series.iloc[-1]):
        return None
    return float(series.iloc[-1])


def compute_emas(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with EMA20/50/100/200 columns."""
    return ind.add_emas(df, periods=config.EMA_PERIODS)


def stack_state(df: pd.DataFrame) -> str:
    """
    Bullish stack: EMA20 > EMA50 > EMA100 > EMA200
    Bearish stack: reverse
    Otherwise: mixed
    """
    df = compute_emas(df)
    try:
        e20  = df["EMA20"].iloc[-1]
        e50  = df["EMA50"].iloc[-1]
        e100 = df["EMA100"].iloc[-1]
        e200 = df["EMA200"].iloc[-1]
    except (KeyError, IndexError):
        return "unknown"
    if any(pd.isna([e20, e50, e100, e200])):
        return "unknown"
    if e20 > e50 > e100 > e200:
        return "bullish"
    if e20 < e50 < e100 < e200:
        return "bearish"
    return "mixed"


def ema_200_slope(df: pd.DataFrame, bars: int = 20) -> float:
    """
    Linear slope of EMA200 over the last `bars` candles, normalised by price.
    Positive = rising, negative = declining, ~0 = flat.
    Used to enforce the strategy's §17 requirement: 200 EMA must be flat-to-rising.
    """
    df = compute_emas(df)
    try:
        series = df["EMA200"].dropna()
    except KeyError:
        return 0.0
    if len(series) < bars:
        return 0.0
    window = series.iloc[-bars:].values
    price  = float(df["Close"].iloc[-1])
    if price <= 0:
        return 0.0
    # Simple linear regression slope, normalised to price
    x = range(len(window))
    x_mean = (len(window) - 1) / 2
    y_mean = sum(window) / len(window)
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, window))
    den = sum((xi - x_mean) ** 2 for xi in x)
    if den == 0:
        return 0.0
    return float(num / den / price)


def compression_percentile(df: pd.DataFrame, lookback: int = 100) -> Dict:
    """
    Self-relative EMA-spread tightness (§6A: "unusually close *for this stock*",
    not a universal fixed threshold — a high-beta stock's normal spread is wider
    than a low-beta stock's). Percentile-ranks the current EMA20-200 spread
    against the stock's own trailing `lookback`-bar history.

    This is the single canonical "how tight is the ribbon" measure — both
    compression_score()/convergence_signal() here and contraction_engine's
    consolidation_strength() consume it, so the two engines never disagree
    about whether a stock's gate is shut.

    Returns {"percentile": 0..100 (lower = tighter), "score_0_1": 0..1 (1 = very tight)}.
    """
    df = compute_emas(df)
    cols = [f"EMA{p}" for p in config.EMA_PERIODS]
    if not all(c in df.columns for c in cols):
        return {"percentile": 100.0, "score_0_1": 0.0}
    ema_df = df[cols]
    price = df["Close"]
    spread_series = (ema_df.max(axis=1) - ema_df.min(axis=1)) / price.replace(0, pd.NA)
    spread_series = spread_series.dropna()
    if len(spread_series) < lookback:
        return {"percentile": 100.0, "score_0_1": 0.0}
    window = spread_series.iloc[-lookback:]
    current = window.iloc[-1]
    if pd.isna(current):
        return {"percentile": 100.0, "score_0_1": 0.0}
    pct = float((window < current).sum() / len(window) * 100)
    score = float(1.0 - (pct / config.BB_SQUEEZE_PERCENTILE)) if pct <= config.BB_SQUEEZE_PERCENTILE else 0.0
    return {"percentile": pct, "score_0_1": score}


def compression_score(df: pd.DataFrame) -> float:
    """0 (wide) to 100 (tight) — compression_percentile() rescaled for display."""
    return compression_percentile(df)["score_0_1"] * 100.0


def correction_level(
    df: pd.DataFrame,
    timeframe: str = "",
    symbol: str = "",
) -> Dict:
    """
    Identify which EMA the current price is testing (correction depth).

    BUG-1 fix: On the monthly timeframe, NIFTY_50 blue-chip stocks correct only
    to EMA100 (not EMA200). This exception is applied when timeframe=="1mo"
    and symbol is in config.NIFTY_50.

    Returns:
      {
        "level": 1 | 2 | 3 | 4 | None,   # 1=EMA20 .. 4=EMA200
        "ema":   20 | 50 | 100 | 200 | None,
        "distance_pct": float,
        "phase": "at_ema" | "above" | "below" | "unknown",
        "monthly_exception_applied": bool,
      }
    """
    df = compute_emas(df)
    if df.empty:
        return {
            "level": None, "ema": None, "distance_pct": None,
            "phase": "unknown", "monthly_exception_applied": False,
        }
    price = df["Close"].iloc[-1]
    if pd.isna(price):
        return {
            "level": None, "ema": None, "distance_pct": None,
            "phase": "unknown", "monthly_exception_applied": False,
        }

    # BUG-1: monthly blue-chip exception — deepest correction level is EMA100
    is_bluechip_monthly = (
        timeframe == "1mo"
        and symbol in config.NIFTY_50
    )
    max_ema = config.MONTHLY_BLUECHIP_MAX_EMA if is_bluechip_monthly else 200

    best_level = None
    best_ema = None
    best_dist = float("inf")
    phase = "unknown"

    for level, p in config.EMA_CORRECTION_MAP.items():
        if p > max_ema:
            continue   # skip levels deeper than what's applicable for this symbol/TF
        col = f"EMA{p}"
        if col not in df.columns:
            continue
        v = df[col].iloc[-1]
        if pd.isna(v) or v <= 0:
            continue
        dist = abs(price - v) / v
        if dist < best_dist:
            best_dist = dist
            best_level = level
            best_ema = p
            phase = "above" if price >= v else "below"

    if best_dist > config.EMA_TOUCH_TOLERANCE:
        return {
            "level": best_level,
            "ema": best_ema,
            "distance_pct": best_dist,
            "phase": phase,
            "monthly_exception_applied": is_bluechip_monthly,
        }

    return {
        "level": best_level,
        "ema": best_ema,
        "distance_pct": best_dist,
        "phase": "at_ema",
        "monthly_exception_applied": is_bluechip_monthly,
    }


def convergence_signal(df: pd.DataFrame, lookback: int = 50) -> Dict:
    """
    Detects EMA convergence — proxy for *time correction* nearing completion.

    Returns:
      {
        "is_converging": bool,
        "spread_pct": float,             # current EMA max-min / price
        "spread_trend": "tightening" | "widening" | "flat",
      }
    """
    df = compute_emas(df)
    cols = [f"EMA{p}" for p in config.EMA_PERIODS]
    if not all(c in df.columns for c in cols) or len(df) < lookback + 5:
        return {"is_converging": False, "spread_pct": None, "spread_trend": "unknown"}

    ema_block = df[cols].dropna()
    if ema_block.empty:
        return {"is_converging": False, "spread_pct": None, "spread_trend": "unknown"}

    spread = (ema_block.max(axis=1) - ema_block.min(axis=1)) / df.loc[ema_block.index, "Close"]
    current_spread = spread.iloc[-1]
    if pd.isna(current_spread):
        return {"is_converging": False, "spread_pct": None, "spread_trend": "unknown"}

    # Compare last 5 bars vs prior 20 bars
    recent = spread.iloc[-5:].mean()
    prior  = spread.iloc[-25:-5].mean() if len(spread) >= 25 else spread.iloc[:-5].mean()

    if pd.isna(prior) or prior == 0:
        trend = "unknown"
    elif recent < prior * 0.85:
        trend = "tightening"
    elif recent > prior * 1.15:
        trend = "widening"
    else:
        trend = "flat"

    # Tightness is judged relative to the stock's own history (same measure the
    # actual BUY-gating GATE score uses), not a universal fixed threshold — see
    # compression_percentile().
    is_tight = compression_percentile(df)["percentile"] <= config.BB_SQUEEZE_PERCENTILE
    is_conv = is_tight and (trend == "tightening")
    return {
        "is_converging": bool(is_conv),
        "spread_pct": float(current_spread),
        "spread_trend": trend,
    }


# -----------------------------------------------------------------------------
# BUG-4 fix: Bounce sequence validation (20 -> 50 -> 100 -> 200)
# -----------------------------------------------------------------------------
def bounce_sequence_valid(df: pd.DataFrame, current_ema: Optional[int] = None) -> bool:
    """
    Returns True if the corrections leading up to the current EMA level followed
    the expected sequence: EMA20 -> EMA50 -> EMA100 -> EMA200.

    If price is currently at EMA200 without prior touches of EMA20/50/100,
    the sequence is invalid (higher-risk unvalidated setup).
    """
    if current_ema is None:
        corr = correction_level(df)
        current_ema = corr.get("ema")

    if current_ema is None or current_ema == 20:
        return True  # first bounce has no prior sequence requirement

    sequence: List[int] = [20, 50, 100, 200]
    try:
        current_idx = sequence.index(current_ema)
    except ValueError:
        return True

    required_prior = sequence[:current_idx]
    df = compute_emas(df)

    # Look back up to 500 bars (excluding current bar) for historical touches
    lookback = min(500, len(df) - 1)
    df_look = df.iloc[-lookback:-1] if lookback > 0 else df.iloc[:-1]

    close_vals = df_look["Close"].values
    # Slightly wider tolerance (2x) for historical touches — bars may not close exactly at EMA
    tol = config.EMA_TOUCH_TOLERANCE * 2.0

    for prior_ema in required_prior:
        col = f"EMA{prior_ema}"
        if col not in df_look.columns:
            return False
        ema_vals = df_look[col].values
        touched = any(
            (e > 0 and not np.isnan(e) and abs(c - e) / e <= tol)
            for c, e in zip(close_vals, ema_vals)
        )
        if not touched:
            return False

    return True


# -----------------------------------------------------------------------------
# G-4: Verify a genuine prior trend exists to correct from
# -----------------------------------------------------------------------------
def _has_genuine_prior_trend(df: pd.DataFrame, high_pos: int) -> bool:
    """
    Every reference "perfect gate" chart shows a real impulsive up-leg before the
    correction (§1: "Trend -> Correction -> Trend") — there must be something to
    correct FROM. Without this check a choppy stock whose tiny swings happen to
    graze EMA200 could pass Check B with no real prior trend.

    Requires the up-move from the swing low preceding `high_pos` to the swing
    high at `high_pos` to span at least MIN_PRIOR_TREND_ATR_MULT x ATR(14),
    measured at the swing high — an ATR-relative (not fixed-%) bar so it scales
    correctly for both low- and high-beta stocks.

    Returns True (assume valid) whenever there isn't enough history to check —
    consistent with the rest of this module's "insufficient data -> don't block"
    philosophy.
    """
    df_before_high = df.iloc[:high_pos]
    if len(df_before_high) < 20:
        return True
    prior_lows_mask = ind.swing_lows(df_before_high, left=3, right=3)
    if not prior_lows_mask.any():
        return True
    prior_low_pos = int(df.index.get_loc(prior_lows_mask[prior_lows_mask].index[-1]))
    prior_low = float(df["Low"].iloc[prior_low_pos])
    high_price = float(df["High"].iloc[high_pos])
    if prior_low <= 0:
        return True
    atr_series = ind.atr(df, 14)
    atr_at_high = atr_series.iloc[high_pos] if high_pos < len(atr_series) else None
    if atr_at_high is None or pd.isna(atr_at_high) or atr_at_high <= 0:
        return True
    return (high_price - prior_low) >= config.MIN_PRIOR_TREND_ATR_MULT * float(atr_at_high)


# -----------------------------------------------------------------------------
# C-5 / MISS-1 fix: Validate that the last correction touched EMA200
# G-4:              ... and that it corrected a genuine prior trend
# G-5:              exposes the validated leg's swing prices so signal_engine's
#                   Fibonacci-confluence check confirms the SAME up-move, not an
#                   independently-detected fractal swing (§3: "Fibonacci ... drawn
#                   on the last big up-move").
# -----------------------------------------------------------------------------
def validate_correction_leg(df: pd.DataFrame) -> Dict:
    """
    Returns:
      {
        "validated":  bool,           # did the last correction touch EMA200 (and
                                       # correct a genuine prior trend)?
        "swing_high": float | None,   # price of the leg's swing high
        "swing_low":  float | None,   # price of the leg's swing low
      }

    A reversal without an EMA200 touch, or without a real prior trend, is a
    'fake correction' per the GATE Strategy. Only meaningful when the stack has
    returned to bullish after a pullback. Assumes valid (validated=True, no
    swing prices) when data is insufficient to determine.
    """
    empty_valid = {"validated": True, "swing_high": None, "swing_low": None}

    df = compute_emas(df)
    if "EMA200" not in df.columns or len(df) < 50:
        return empty_valid

    if stack_state(df) != "bullish":
        return empty_valid  # still in correction or bearish — nothing to validate yet

    # Find the most recent swing low (bottom of the last correction)
    lows_mask = ind.swing_lows(df, left=3, right=3)
    if not lows_mask.any():
        return empty_valid

    last_low_pos = int(df.index.get_loc(lows_mask[lows_mask].index[-1]))

    # Find the swing high that preceded it (start of that correction)
    df_before_low = df.iloc[:last_low_pos]
    highs_mask = ind.swing_highs(df_before_low, left=3, right=3)
    if not highs_mask.any():
        return empty_valid

    last_high_pos = int(df.index.get_loc(highs_mask[highs_mask].index[-1]))

    if last_low_pos <= last_high_pos:
        return empty_valid

    swing_high_price = float(df["High"].iloc[last_high_pos])
    swing_low_price = float(df["Low"].iloc[last_low_pos])

    if not _has_genuine_prior_trend(df, last_high_pos):
        return {"validated": False, "swing_high": swing_high_price, "swing_low": swing_low_price}

    # During the correction window (swing high → swing low), check for EMA200 touch
    df_corr = df.iloc[last_high_pos : last_low_pos + 1]
    e200_vals = df_corr["EMA200"].values
    low_vals  = df_corr["Low"].values
    close_vals = df_corr["Close"].values
    tol = config.EMA_TOUCH_TOLERANCE * 2.0

    for i in range(len(df_corr)):
        e = e200_vals[i]
        if e <= 0 or np.isnan(e):
            continue
        # Touch: bar's low came within 2x tolerance of EMA200 from above
        if abs(low_vals[i] - e) / e <= tol:
            return {"validated": True, "swing_high": swing_high_price, "swing_low": swing_low_price}
        # Touch: bar closed at or below EMA200 (price passed through it)
        if close_vals[i] <= e:
            return {"validated": True, "swing_high": swing_high_price, "swing_low": swing_low_price}

    return {"validated": False, "swing_high": swing_high_price, "swing_low": swing_low_price}


def analyze(
    df: pd.DataFrame,
    timeframe: str = "",
    symbol: str = "",
) -> Dict:
    """Full EMA analysis for the latest bar — used by orchestrators."""
    if df is None or df.empty or len(df) < 210:
        return {
            "stack": "unknown",
            "compression_score": 0.0,
            "correction": {
                "level": None, "ema": None, "distance_pct": None,
                "phase": "unknown", "monthly_exception_applied": False,
            },
            "convergence": {"is_converging": False, "spread_pct": None, "spread_trend": "unknown"},
            "ema_values": {},
            "bounce_sequence_valid": True,
            "correction_validated": True,
            "correction_swing_high": None,
            "correction_swing_low": None,
        }
    df = compute_emas(df)
    corr = correction_level(df, timeframe=timeframe, symbol=symbol)
    ema_values = {f"EMA{p}": _last(df[f"EMA{p}"]) for p in config.EMA_PERIODS}
    corr_leg = validate_correction_leg(df)
    return {
        "stack": stack_state(df),
        "compression_score": compression_score(df),
        "ema_200_slope": ema_200_slope(df),
        "correction": corr,
        "convergence": convergence_signal(df),
        "ema_values": ema_values,
        "bounce_sequence_valid": bounce_sequence_valid(df, current_ema=corr.get("ema")),
        "correction_validated": corr_leg["validated"],
        "correction_swing_high": corr_leg["swing_high"],
        "correction_swing_low": corr_leg["swing_low"],
    }
