"""
accumulation.py
===============
Volume-based smart-money proxies (no NSE delivery data required).

Two scores, both 0–100 with 50 ≈ neutral:

  accumulation_score(df)  — is volume flowing IN? Blends OBV slope, A/D slope and
                            the up-volume / down-volume ratio over a recent window.

  volume_pattern(df)      — the GATE volume signature: volume DRIES UP during the
                            base, then BUILDS UP as price approaches breakout.
                            Returns (score, buildup_flag).
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from app.core import config
from app.core.analysis import indicators as ind

_RECENT = 20      # window for OBV / A-D slope and up/down volume ratio
_BUILDUP = 3      # very recent bars that should show expansion


def _slope_score(series: pd.Series, window: int) -> float:
    """Map the normalized linear slope of `series` over `window` bars to 0–100."""
    s = series.dropna()
    if len(s) < window:
        return 50.0
    y = s.iloc[-window:].to_numpy(dtype=float)
    x = np.arange(window, dtype=float)
    # Normalize by the magnitude of the series so slope is scale-free.
    denom = np.mean(np.abs(y)) or 1.0
    slope = np.polyfit(x, y, 1)[0] / denom
    # slope ~ +/-0.05 per bar saturates the score
    return float(max(0.0, min(100.0, 50.0 + slope / 0.05 * 50.0)))


def accumulation_score(df: pd.DataFrame) -> float:
    """Blend OBV slope, A/D slope and up/down volume ratio into a 0–100 score."""
    if df is None or df.empty or "Volume" not in df.columns or len(df) < _RECENT + 1:
        return config.SECTOR_NEUTRAL  # neutral 50.0

    obv_score = _slope_score(ind.obv(df), _RECENT)
    ad_score = _slope_score(ind.acc_dist(df), _RECENT)

    # Up/down volume ratio: volume on up-closes vs down-closes (recent window).
    recent = df.iloc[-_RECENT:]
    change = recent["Close"].diff().fillna(0.0)
    up_vol = recent["Volume"][change > 0].sum()
    down_vol = recent["Volume"][change < 0].sum()
    total = up_vol + down_vol
    if total > 0:
        ud_score = float(up_vol / total) * 100.0
    else:
        ud_score = 50.0

    return float(max(0.0, min(100.0, 0.4 * obv_score + 0.3 * ad_score + 0.3 * ud_score)))


def volume_pattern(df: pd.DataFrame) -> Tuple[float, bool]:
    """
    GATE volume signature: dry-up during the base then a buildup near breakout.

    Returns (score 0–100, buildup_flag). High score requires BOTH a quiet base
    (recent avg volume below the longer baseline) AND a fresh pickup in the last
    few bars (expansion starting) — this is what separates a real breakout from a
    low-volume fake.
    """
    if df is None or df.empty or "Volume" not in df.columns:
        return 50.0, False
    if len(df) < config.VOL_CONTRACTION_LOOKBACK_LONG:
        return 50.0, False

    vol = df["Volume"].fillna(0.0)
    short_avg = float(vol.iloc[-config.VOL_CONTRACTION_LOOKBACK_SHORT:].mean())
    long_avg = float(vol.iloc[-config.VOL_CONTRACTION_LOOKBACK_LONG:].mean())
    if long_avg <= 0:
        return 50.0, False

    # Dry-up: base volume below the longer baseline (ratio < 1 is good).
    dry_ratio = short_avg / long_avg
    dryup_score = max(0.0, min(1.0, (1.0 - dry_ratio) / 0.5))  # ratio 0.5 → full marks

    # Buildup: the most recent bars expanding above the base.
    recent_avg = float(vol.iloc[-_BUILDUP:].mean())
    base_avg = float(vol.iloc[-config.VOL_CONTRACTION_LOOKBACK_SHORT:-_BUILDUP].mean()) \
        if config.VOL_CONTRACTION_LOOKBACK_SHORT > _BUILDUP else short_avg
    buildup_ratio = recent_avg / base_avg if base_avg > 0 else 1.0
    buildup_flag = buildup_ratio >= 1.3
    buildup_score = max(0.0, min(1.0, (buildup_ratio - 1.0) / 0.5))  # +50% → full marks

    score = 100.0 * (0.5 * dryup_score + 0.5 * buildup_score)
    return float(max(0.0, min(100.0, score))), bool(buildup_flag)
