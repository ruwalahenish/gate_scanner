"""
indicators.py
==============
Pure-pandas/numpy technical indicators. No external TA library required.

All functions take a DataFrame with Open/High/Low/Close/Volume columns and
return a Series or DataFrame aligned with the input index.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Moving averages
# -----------------------------------------------------------------------------
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def add_emas(df: pd.DataFrame, periods=(20, 50, 100, 200)) -> pd.DataFrame:
    out = df.copy()
    for p in periods:
        out[f"EMA{p}"] = ema(out["Close"], p)
    return out


# -----------------------------------------------------------------------------
# True Range / ATR  (Wilder's smoothing — alpha = 1/period, adjust=False)
# -----------------------------------------------------------------------------
def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift()
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ATR — EWM with alpha=1/period matches the standard indicator."""
    return true_range(df).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


# -----------------------------------------------------------------------------
# Bollinger Bands
# -----------------------------------------------------------------------------
def bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0):
    mid = sma(df["Close"], period)
    std = df["Close"].rolling(period, min_periods=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def bb_width(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    upper, mid, lower = bollinger(df, period, std_dev)
    return (upper - lower) / mid


# -----------------------------------------------------------------------------
# ADX (trend strength) — full Wilder's smoothing throughout
# -----------------------------------------------------------------------------
def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder's ADX: DM smoothing, TR smoothing, and final DX smoothing all use
    EWM with alpha=1/period (adjust=False).  This matches TradingView / standard
    platforms and keeps the ADX_CONTRACTION_WEAK/STRONG thresholds calibrated.
    """
    alpha = 1.0 / period

    up_move   = df["High"].diff()
    down_move = -df["Low"].diff()

    plus_dm  = pd.Series(
        np.where((up_move > down_move) & (up_move > 0),  up_move.values,   0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move.values, 0.0),
        index=df.index,
    )

    atr_     = true_range(df).ewm(alpha=alpha, adjust=False, min_periods=period).mean()
    plus_di  = 100 * plus_dm.ewm(alpha=alpha,  adjust=False, min_periods=period).mean() / atr_.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean() / atr_.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()


# -----------------------------------------------------------------------------
# Fibonacci Retracement Levels
# (MISS-2 fix: strategy requires Fibonacci confirmation of correction ends)
# -----------------------------------------------------------------------------
def fibonacci_levels(
    swing_high: float,
    swing_low: float,
) -> Dict[str, float]:
    """
    Calculate standard Fibonacci retracement levels between a swing high and low.

    For a bullish correction (price pulled back from a high):
      levels are measured downward from the swing high.

    Returns a dict of { label: price_level } for 23.6%, 38.2%, 50%, 61.8%, 78.6%.
    Returns empty dict if inputs are invalid.
    """
    if swing_high <= swing_low or swing_high <= 0 or swing_low <= 0:
        return {}
    diff = swing_high - swing_low
    ratios = {
        "23.6": 0.236,
        "38.2": 0.382,
        "50.0": 0.500,
        "61.8": 0.618,
        "78.6": 0.786,
    }
    return {label: round(swing_high - ratio * diff, 4) for label, ratio in ratios.items()}


def fibonacci_extensions(
    base_low: float,
    base_high: float,
) -> Dict[str, float]:
    """
    Fibonacci extension levels projected upward from a consolidation base.

    Anchored to the base of the move (range_low → range_high):
      level = base_low + ratio × (base_high − base_low)

    Returns levels for 1.272 (first partial), 1.618 (main target), 2.618 (extended).
    Returns empty dict if inputs are invalid.
    """
    if base_high <= base_low or base_low <= 0:
        return {}
    height = base_high - base_low
    return {
        "1.272": round(base_low + 1.272 * height, 4),
        "1.618": round(base_low + 1.618 * height, 4),
        "2.618": round(base_low + 2.618 * height, 4),
    }


# -----------------------------------------------------------------------------
# Swing points (fractal-style)
# -----------------------------------------------------------------------------
def swing_highs(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.Series:
    """Boolean Series — True where a swing high occurs."""
    highs = df["High"]
    cond = pd.Series(True, index=df.index)
    for i in range(1, left + 1):
        cond &= highs > highs.shift(i)
    for i in range(1, right + 1):
        cond &= highs > highs.shift(-i)
    return cond.fillna(False)


def swing_lows(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.Series:
    lows = df["Low"]
    cond = pd.Series(True, index=df.index)
    for i in range(1, left + 1):
        cond &= lows < lows.shift(i)
    for i in range(1, right + 1):
        cond &= lows < lows.shift(-i)
    return cond.fillna(False)


def last_swing_levels(df: pd.DataFrame, left: int = 3, right: int = 3) -> dict:
    """Return last confirmed swing high & swing low prices."""
    sh = swing_highs(df, left, right)
    sl = swing_lows(df, left, right)
    last_high = df.loc[sh, "High"].iloc[-1] if sh.any() else None
    last_low  = df.loc[sl, "Low"].iloc[-1]  if sl.any() else None
    return {"last_swing_high": last_high, "last_swing_low": last_low}


# -----------------------------------------------------------------------------
# Volume-flow indicators (smart-money / accumulation proxies)
# -----------------------------------------------------------------------------
def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume — cumulative volume signed by close-to-close direction."""
    direction = np.sign(df["Close"].diff().fillna(0.0))
    return (direction * df["Volume"].fillna(0.0)).cumsum()


def acc_dist(df: pd.DataFrame) -> pd.Series:
    """Accumulation/Distribution line — volume weighted by close location in range."""
    rng = (df["High"] - df["Low"]).replace(0, np.nan)
    clv = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / rng
    clv = clv.fillna(0.0)
    return (clv * df["Volume"].fillna(0.0)).cumsum()


# -----------------------------------------------------------------------------
# Percentile helper
# -----------------------------------------------------------------------------
def rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    """Percentile rank (0-100) of each value within trailing `window` bars."""
    return series.rolling(window, min_periods=window).apply(
        lambda x: (x.argsort().argsort()[-1] + 1) / len(x) * 100,
        raw=False,
    )
