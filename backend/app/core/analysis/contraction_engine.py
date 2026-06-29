"""
contraction_engine.py
======================
The "GATE" detector.

A GATE is a confluence of volatility-contraction signals indicating that an
explosive expansion is statistically more likely. The strategy posits that
expansion *starts* on smaller timeframes and then ladders up — so this engine
must work on any TF, producing a score 0-100.

Components (each scored 0-1, then weighted):

  1. Bollinger Band Squeeze   — BB width in bottom percentile
  2. ATR Contraction          — ATR in bottom percentile (raw volatility low)
  3. EMA Compression          — EMAs bunched up (from ema_engine)
  4. Narrow Range Candles     — recent candle ranges small vs trailing ATR
  5. Volume Contraction       — recent vol < trailing vol
  6. ADX Contraction          — low ADX confirms sideways/contracting phase (C-2 fix)

The final score = weighted sum * 100, plus a directional bias inferred from
EMA stack and recent close vs. mid-BB.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from app.core import config
from app.core.analysis import indicators as ind
from app.core.analysis import ema_engine
from app.core.analysis import range_engine
from app.core.analysis import accumulation as accum


# -----------------------------------------------------------------------------
# Individual signals — each returns a [0, 1] score
# -----------------------------------------------------------------------------
def _bb_squeeze_score(df: pd.DataFrame) -> float:
    width = ind.bb_width(df, period=20, std_dev=2.0)
    if width.dropna().empty or len(width.dropna()) < config.BB_LOOKBACK:
        return 0.0
    window = width.iloc[-config.BB_LOOKBACK:]
    current = window.iloc[-1]
    if pd.isna(current):
        return 0.0
    # Percentile rank — lower = tighter
    pct = (window < current).sum() / len(window) * 100
    # If current width <= 20th percentile, score scales from 1.0 (at 0%) to 0 (at 20%)
    if pct <= config.BB_SQUEEZE_PERCENTILE:
        return float(1.0 - (pct / config.BB_SQUEEZE_PERCENTILE))
    return 0.0


def _atr_contraction_score(df: pd.DataFrame) -> float:
    atr_ = ind.atr(df, period=14)
    if atr_.dropna().empty or len(atr_.dropna()) < config.ATR_LOOKBACK:
        return 0.0
    window = atr_.iloc[-config.ATR_LOOKBACK:]
    current = window.iloc[-1]
    if pd.isna(current):
        return 0.0
    pct = (window < current).sum() / len(window) * 100
    if pct <= config.ATR_SQUEEZE_PERCENTILE:
        return float(1.0 - (pct / config.ATR_SQUEEZE_PERCENTILE))
    return 0.0


def _ema_compression_score(df: pd.DataFrame) -> float:
    """
    Percentile-rank of current EMA spread vs the stock's own rolling 100-bar history.
    Replaces the fixed 4% threshold so high-beta stocks can score correctly (§6A:
    "unusually close *for this stock*", not universally close).
    Score = 1.0 when current spread is in the bottom 20th percentile of its own history.
    """
    df = ema_engine.compute_emas(df)
    ema_cols = [f"EMA{p}" for p in config.EMA_PERIODS]
    if not all(c in df.columns for c in ema_cols):
        return 0.0
    ema_df = df[ema_cols]
    price   = df["Close"]
    spread_series = (ema_df.max(axis=1) - ema_df.min(axis=1)) / price.replace(0, pd.NA)
    spread_series = spread_series.dropna()
    lookback = config.BB_LOOKBACK  # reuse same 100-bar window
    if len(spread_series) < lookback:
        return 0.0
    window  = spread_series.iloc[-lookback:]
    current = window.iloc[-1]
    if pd.isna(current):
        return 0.0
    pct = (window < current).sum() / len(window) * 100
    if pct <= config.BB_SQUEEZE_PERCENTILE:  # bottom 20th percentile
        return float(1.0 - (pct / config.BB_SQUEEZE_PERCENTILE))
    return 0.0


def _narrow_range_score(df: pd.DataFrame) -> float:
    if len(df) < config.NR_LOOKBACK + 14:
        return 0.0
    atr_ = ind.atr(df, 14)
    last_n_range = (df["High"] - df["Low"]).iloc[-config.NR_LOOKBACK:].mean()
    last_atr = atr_.iloc[-1]
    if pd.isna(last_atr) or last_atr <= 0:
        return 0.0
    ratio = last_n_range / last_atr   # < 1 means recent candles narrower than trailing ATR
    # Map: ratio <= 0.6 -> 1.0; ratio >= 1.0 -> 0
    if ratio >= 1.0:
        return 0.0
    return float(max(0.0, min(1.0, (1.0 - ratio) / 0.4)))


def _volume_contraction_score(df: pd.DataFrame) -> float:
    if "Volume" not in df.columns or len(df) < config.VOL_CONTRACTION_LOOKBACK_LONG:
        return 0.0
    short_avg = df["Volume"].iloc[-config.VOL_CONTRACTION_LOOKBACK_SHORT:].mean()
    long_avg  = df["Volume"].iloc[-config.VOL_CONTRACTION_LOOKBACK_LONG:].mean()
    if long_avg <= 0 or pd.isna(long_avg):
        return 0.0
    ratio = short_avg / long_avg
    # ratio < 0.7 -> contracting; map 0.4..1.0 to 1.0..0
    if ratio >= 1.0:
        return 0.0
    return float(max(0.0, min(1.0, (1.0 - ratio) / 0.6)))


def _adx_contraction_score(df: pd.DataFrame) -> float:
    """
    C-2 fix: Low ADX confirms the market is in a non-trending / sideways phase,
    which is the hallmark of a GATE formation.

    ADX <= ADX_CONTRACTION_WEAK  (15) -> score = 1.0  (maximum contraction)
    ADX >= ADX_CONTRACTION_STRONG(35) -> score = 0.0  (strong trend, not a GATE)
    Linear interpolation in between.
    """
    adx_series = ind.adx(df, period=14)
    if adx_series.dropna().empty:
        return 0.0
    val = adx_series.iloc[-1]
    if pd.isna(val):
        return 0.0
    weak   = config.ADX_CONTRACTION_WEAK
    strong = config.ADX_CONTRACTION_STRONG
    if val <= weak:
        return 1.0
    if val >= strong:
        return 0.0
    return float(1.0 - (val - weak) / (strong - weak))


# -----------------------------------------------------------------------------
# Consolidation strength (the old 6-component contraction composite, 0–100)
# -----------------------------------------------------------------------------
def consolidation_strength(df: pd.DataFrame) -> Dict:
    """Weighted blend of the contraction sub-signals → {score 0–100, components}."""
    components = {
        "bb_squeeze":      _bb_squeeze_score(df),
        "atr_contraction": _atr_contraction_score(df),
        "ema_compression": _ema_compression_score(df),
        "narrow_range":    _narrow_range_score(df),
        "volume_contract": _volume_contraction_score(df),
        "adx_contraction": _adx_contraction_score(df),
    }
    weighted = sum(components[k] * config.CONTRACTION_WEIGHTS[k] for k in components)
    return {"score": float(weighted * 100), "components": {k: float(v) for k, v in components.items()}}


# -----------------------------------------------------------------------------
# Composite per-TF GATE  (technical gate: tightness + breakout proximity +
# volume pattern + accumulation — see GATE_TF_WEIGHTS)
# -----------------------------------------------------------------------------
def gate_score(df: pd.DataFrame) -> Dict:
    """
    Returns the per-timeframe technical GATE score:
      {
        "score": float [0, 100],            # the GATE_TF_WEIGHTS composite
        "components": {...},                 # contraction sub-signals + 4 TF components
        "consolidation_strength": float,
        "is_gate": bool,
        "direction_bias": "bullish" | "bearish" | "neutral",
        "range": {...},                      # box + breakout state (range_engine)
        "volume_buildup": bool,
      }
    """
    if df is None or df.empty or len(df) < 210:
        return {
            "score": 0.0,
            "components": {},
            "consolidation_strength": 0.0,
            "is_gate": False,
            "direction_bias": "neutral",
            "range": range_engine.analyze_range(df) if df is not None else {},
            "volume_buildup": False,
        }

    contraction = consolidation_strength(df)
    rng = range_engine.analyze_range(df)
    vol_pattern_score, buildup = accum.volume_pattern(df)
    accumulation_v = accum.accumulation_score(df)

    tf_components = {
        "consolidation_strength": contraction["score"],
        "breakout_proximity":     rng.get("proximity_score", 0.0),
        "volume_pattern":         vol_pattern_score,
        "accumulation":           accumulation_v,
    }
    score = sum(tf_components[k] * config.GATE_TF_WEIGHTS[k] for k in tf_components)

    # Directional bias
    stack = ema_engine.stack_state(df)
    _, mid, _ = ind.bollinger(df)
    last_close = df["Close"].iloc[-1]
    mid_last = mid.iloc[-1] if not mid.empty else None

    if stack == "bullish":
        bias = "bullish"
    elif stack == "bearish":
        bias = "bearish"
    elif mid_last is not None and not pd.isna(mid_last):
        bias = "bullish" if last_close > mid_last else "bearish"
    else:
        bias = "neutral"

    return {
        "score": float(score),
        "components": {**contraction["components"], **tf_components},
        "consolidation_strength": contraction["score"],
        "is_gate": score >= 55.0,
        "direction_bias": bias,
        "range": rng,
        "volume_buildup": bool(buildup),
    }


def breakout_probability(df: pd.DataFrame, gate: Optional[Dict] = None) -> float:
    """
    Probability that price expands within the next few bars (0..100).
    Heuristic: GATE strength * (volume confirmation factor) * (structure factor).
    """
    if df is None or df.empty:
        return 0.0
    gate = gate or gate_score(df)
    base = gate["score"]  # already 0..100

    # Volume confirmation: is the most recent bar showing volume pickup?
    vol_factor = 1.0
    if "Volume" in df.columns and len(df) >= 20:
        recent_vol = df["Volume"].iloc[-3:].mean()
        baseline   = df["Volume"].iloc[-20:].mean()
        if baseline > 0:
            ratio = recent_vol / baseline
            vol_factor = 1.0 + min(0.3, max(-0.2, (ratio - 1.0) * 0.5))

    # Structure factor: bullish/bearish stack adds confidence
    stack = ema_engine.stack_state(df)
    struct_factor = 1.1 if stack in ("bullish", "bearish") else 0.9

    prob = min(100.0, max(0.0, base * vol_factor * struct_factor))
    return float(prob)
