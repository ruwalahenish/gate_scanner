"""
fundamentals.py
===============
Pure fundamental-quality scoring for the GATE scanner.

`fundamental_score(row)` turns the yfinance-derived fundamentals stored on
stock_master into a single 0–100 quality score. Each metric is mapped to 0–100
via piecewise-linear bands, then blended with FUNDAMENTAL_WEIGHTS over the
metrics that are actually present (weights renormalized). When too few metrics
are available the score degrades gracefully to FUNDAMENTAL_NEUTRAL.

yfinance conventions:
  roe / roce / revenue_growth / profit_growth / profit_margin → fractions (0.18 = 18%)
  debt_to_equity → percent-style number (45.3 ≈ 0.45x) → divided by 100 here
"""

from __future__ import annotations

from typing import Optional

from app.core import config


def _to_float(v) -> Optional[float]:
    """Coerce Decimal / str / None to float; None on failure."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # yfinance occasionally emits NaN — treat as missing
    return f if f == f else None


def _lerp_score(value: float, low: float, high: float,
                low_score: float, high_score: float) -> float:
    """Linear interpolation of `value` in [low, high] onto [low_score, high_score], clamped."""
    if high == low:
        return high_score
    t = (value - low) / (high - low)
    t = max(0.0, min(1.0, t))
    return low_score + t * (high_score - low_score)


def _score_roe(roe: float) -> float:
    if roe <= 0:
        return 0.0
    if roe <= 0.15:
        return _lerp_score(roe, 0.0, 0.15, 0.0, 60.0)
    if roe <= 0.25:
        return _lerp_score(roe, 0.15, 0.25, 60.0, 90.0)
    return 100.0


def _score_roce(roce: float) -> float:
    if roce <= 0:
        return 0.0
    if roce <= 0.08:
        return _lerp_score(roce, 0.0, 0.08, 0.0, 60.0)
    if roce <= 0.15:
        return _lerp_score(roce, 0.08, 0.15, 60.0, 90.0)
    return 100.0


def _score_growth(g: float) -> float:
    # Negative growth is penalized below neutral; strong growth saturates at 100.
    if g <= -0.10:
        return 0.0
    if g <= 0.0:
        return _lerp_score(g, -0.10, 0.0, 0.0, 40.0)
    if g <= 0.20:
        return _lerp_score(g, 0.0, 0.20, 40.0, 90.0)
    return 100.0


def _score_debt_to_equity(de_pct: float) -> float:
    # yfinance reports D/E as a percent (e.g. 45.3 → 0.45x). Lower is better.
    de = de_pct / 100.0
    if de <= 0:
        return 100.0
    if de <= 0.5:
        return _lerp_score(de, 0.0, 0.5, 100.0, 80.0)
    if de <= 1.0:
        return _lerp_score(de, 0.5, 1.0, 80.0, 50.0)
    if de <= 2.0:
        return _lerp_score(de, 1.0, 2.0, 50.0, 20.0)
    return 0.0


def _score_margin(m: float) -> float:
    if m <= 0:
        return 0.0
    if m <= 0.10:
        return _lerp_score(m, 0.0, 0.10, 0.0, 60.0)
    if m <= 0.20:
        return _lerp_score(m, 0.10, 0.20, 60.0, 90.0)
    return 100.0


_SCORERS = {
    "roe":            _score_roe,
    "roce":           _score_roce,
    "revenue_growth": _score_growth,
    "profit_growth":  _score_growth,
    "debt_to_equity": _score_debt_to_equity,
    "profit_margin":  _score_margin,
}


def fundamental_score(row: Optional[dict]) -> float:
    """
    Blend available fundamental metrics into a single 0–100 quality score.

    Returns FUNDAMENTAL_NEUTRAL when fewer than FUNDAMENTAL_MIN_FIELDS metrics
    are present, so sparsely-covered names are neither rewarded nor punished.
    """
    if not row:
        return config.FUNDAMENTAL_NEUTRAL

    weighted_sum = 0.0
    weight_total = 0.0
    used = 0

    for field, scorer in _SCORERS.items():
        value = _to_float(row.get(field))
        if value is None:
            continue
        weight = config.FUNDAMENTAL_WEIGHTS.get(field, 0.0)
        weighted_sum += weight * scorer(value)
        weight_total += weight
        used += 1

    if used < config.FUNDAMENTAL_MIN_FIELDS or weight_total <= 0:
        return config.FUNDAMENTAL_NEUTRAL

    return float(max(0.0, min(100.0, weighted_sum / weight_total)))
