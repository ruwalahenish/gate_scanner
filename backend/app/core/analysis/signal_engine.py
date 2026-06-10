"""
signal_engine.py
=================
Produces concrete trade signals from MTF analysis.

Per the GATE Strategy:

  * Entry = current price (or breakout level) on the leading TF
  * Stop Loss = EMA200 of the *smaller* TF below the signal TF
                (rule: "smaller timeframe EMA200 acts as SL for larger timeframe breakout")
  * Targets = derived from per-TF expectancy table + ATR projection
              with swing-level sanity check
  * Confidence = composite of GATE strength, MTF alignment, structure quality,
                 with adjustments for:
                   - fake correction penalty   (MISS-1 / C-5 fix)
                   - invalid bounce sequence   (BUG-4 fix)
                   - Fibonacci confluence boost (MISS-2 fix)

Side: BUY only. The GATE strategy identifies corrections in uptrends; downtrend signals are discarded.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from app.core import config
from app.core.analysis import ema_engine
from app.core.analysis import indicators as ind


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _signal_tf(mtf_summary: Dict, mtf_data: Optional[Dict] = None) -> Optional[str]:
    """Use confirmation_tf when available in mtf_data, else fall back to leading_tf.
    The mtf_data guard prevents the backtest (single-TF) from picking a TF it never fetched."""
    conf = mtf_summary.get("confirmation_tf")
    if conf and (mtf_data is None or conf in mtf_data):
        return conf
    return mtf_summary.get("leading_tf")


def _sl_tf(signal_tf: str) -> str:
    return config.SL_TIMEFRAME_MAP.get(signal_tf, signal_tf)


def _ema200(df) -> Optional[float]:
    df_e = ema_engine.compute_emas(df)
    if "EMA200" not in df_e.columns or df_e["EMA200"].dropna().empty:
        return None
    v = df_e["EMA200"].iloc[-1]
    return float(v) if not pd.isna(v) else None


def _calc_targets(entry: float, side: str, signal_tf: str, atr_val: float,
                  swing_high: Optional[float], swing_low: Optional[float]) -> Dict[str, float]:
    """
    T1 = ATR-projected near target
    T2 = midpoint of expectancy range
    T3 = full expectancy
    Then clamp/extend using swing structure where sensible.
    """
    low_pct, high_pct = config.TARGET_EXPECTANCY.get(signal_tf, (0.20, 0.30))
    mid_pct = (low_pct + high_pct) / 2

    if side == "BUY":
        atr_target = entry + 2.0 * atr_val
        t1 = max(atr_target, entry * (1 + low_pct * 0.25))
        t2 = entry * (1 + mid_pct)
        t3 = entry * (1 + high_pct)
        if swing_high and t1 < swing_high < t2:
            t1 = swing_high
    else:
        atr_target = entry - 2.0 * atr_val
        t1 = min(atr_target, entry * (1 - low_pct * 0.25))
        t2 = entry * (1 - mid_pct)
        t3 = entry * (1 - high_pct)
        if swing_low and t2 < swing_low < t1:
            t1 = swing_low

    return {"T1": float(t1), "T2": float(t2), "T3": float(t3)}


def _rr(entry: float, sl: float, target: float, side: str) -> float:
    if side == "BUY":
        risk   = entry - sl
        reward = target - entry
    else:
        risk   = sl - entry
        reward = entry - target
    if risk <= 0:
        return 0.0
    return float(reward / risk)


# -----------------------------------------------------------------------------
# MISS-2 fix: Fibonacci confluence check
# -----------------------------------------------------------------------------
def _fib_confluence(
    entry: float,
    swing_high: Optional[float],
    swing_low: Optional[float],
) -> bool:
    """
    Returns True if any Fibonacci retracement level (38.2%, 50%, 61.8%) is
    within 2x EMA_TOUCH_TOLERANCE of the current entry price.

    Confluence of the EMA correction level with a Fibonacci level is a
    high-confidence confirmation that the correction has ended.
    """
    if not swing_high or not swing_low or swing_high <= swing_low:
        return False
    fib = ind.fibonacci_levels(swing_high, swing_low)
    if not fib:
        return False
    # Only use the primary confluence levels (38.2, 50, 61.8 — skip 23.6 and 78.6)
    primary_levels = {"38.2", "50.0", "61.8"}
    tol = config.EMA_TOUCH_TOLERANCE * 2.0
    for label, level_price in fib.items():
        if label in primary_levels and abs(entry - level_price) / entry <= tol:
            return True
    return False


# -----------------------------------------------------------------------------
# Confidence builder with new adjustments
# -----------------------------------------------------------------------------
def _confidence(
    gate_score_v: float,
    alignment_pct: float,
    struct_q: float,
    htf_confirmed: bool,
    breakout_prob: float,
    correction_validated: bool,
    bounce_sequence_valid: bool,
    fib_confluence: bool,
) -> float:
    """
    Composite 0..100 confidence with GATE Strategy adjustments:

      Base formula:
        30% gate strength + 25% alignment + 20% structure quality + 25% breakout prob

      Adjustments (applied as multipliers after the base):
        - fake correction (correction_validated=False): -UNVALIDATED_CORRECTION_PENALTY
        - invalid bounce sequence:                     -INVALID_SEQUENCE_PENALTY
        - Fibonacci confluence:                        +FIB_CONFLUENCE_BOOST
        - HTF confirmed:                               +10%
    """
    base = (
        0.30 * gate_score_v
        + 0.25 * alignment_pct
        + 0.20 * struct_q
        + 0.25 * breakout_prob
    )

    multiplier = 1.0
    if htf_confirmed:
        multiplier += 0.10
    if not correction_validated:
        multiplier -= config.UNVALIDATED_CORRECTION_PENALTY   # fake correction penalty
    if not bounce_sequence_valid:
        multiplier -= config.INVALID_SEQUENCE_PENALTY         # skipped EMA sequence penalty
    if fib_confluence:
        multiplier += config.FIB_CONFLUENCE_BOOST             # Fibonacci confluence bonus

    return float(min(100.0, max(0.0, base * multiplier)))


# -----------------------------------------------------------------------------
# Main signal generator
# -----------------------------------------------------------------------------
def generate_signal(
    symbol: str,
    mtf_data: Dict[str, "pd.DataFrame"],
    mtf_analysis: Dict[str, Dict],
    mtf_sum: Dict,
) -> Optional[Dict]:
    """
    Returns a trade signal dict or None if no actionable setup.

    Parameters
    ----------
    symbol : str
    mtf_data     : { tf: DataFrame }
    mtf_analysis : { tf: analyze_timeframe(...) result }
    mtf_sum      : mtf_summary(...) result
    """
    sig_tf = _signal_tf(mtf_sum, mtf_data)
    if not sig_tf or sig_tf not in mtf_data or mtf_data[sig_tf].empty:
        return None

    direction = mtf_sum["alignment"]["dominant_direction"]
    if direction != "up":
        return None
    side = "BUY"

    df_sig = mtf_data[sig_tf]
    entry = float(df_sig["Close"].iloc[-1])
    if entry < config.MIN_PRICE:
        return None

    # ---- Stop Loss: smaller-TF EMA200 ----
    sl_tf = _sl_tf(sig_tf)
    # Use ATR fallback when sl_tf maps to itself OR when sl_tf data isn't available
    # (e.g. backtest single-TF mode — avoids using the wrong TF's EMA200 as SL)
    df_sl = mtf_data.get(sl_tf)
    # Guard: empty dict {} passes "is not None" but crashes _ema200; require non-empty DataFrame
    sl = _ema200(df_sl) if (df_sl is not None and hasattr(df_sl, "__len__") and len(df_sl) > 0 and sl_tf != sig_tf) else None
    if sl is None:
        atr_sig = ind.atr(df_sig, 14).iloc[-1]
        if pd.isna(atr_sig):
            return None
        sl = entry - 2.0 * atr_sig if side == "BUY" else entry + 2.0 * atr_sig

    # Sanity: SL must be on correct side of entry
    if side == "BUY" and sl >= entry:
        atr_sig = ind.atr(df_sig, 14).iloc[-1]
        if pd.isna(atr_sig):
            return None
        sl = entry - 2.0 * atr_sig
    elif side == "SELL" and sl <= entry:
        atr_sig = ind.atr(df_sig, 14).iloc[-1]
        if pd.isna(atr_sig):
            return None
        sl = entry + 2.0 * atr_sig

    sl_distance_pct = abs(entry - sl) / entry
    if sl_distance_pct > config.MAX_SL_DISTANCE_PCT:
        return None

    # ---- Targets ----
    atr_val = ind.atr(df_sig, 14).iloc[-1]
    if pd.isna(atr_val):
        return None
    swing = mtf_analysis[sig_tf]["structure"]["swing_levels"]
    swing_high = swing.get("last_swing_high")
    swing_low  = swing.get("last_swing_low")
    targets = _calc_targets(entry, side, sig_tf, float(atr_val), swing_high, swing_low)

    # ---- RR ratios ----
    rr = {
        "T1": _rr(entry, sl, targets["T1"], side),
        "T2": _rr(entry, sl, targets["T2"], side),
        "T3": _rr(entry, sl, targets["T3"], side),
    }
    if rr["T1"] < config.MIN_RR_RATIO:
        return None

    # ---- New quality flags ----
    sig_ema = mtf_analysis[sig_tf]["ema"]
    correction_validated  = sig_ema.get("correction_validated", True)
    bounce_seq_valid      = sig_ema.get("bounce_sequence_valid", True)
    fib_conf              = _fib_confluence(entry, swing_high, swing_low)

    # ---- Confidence ----
    sig_analysis = mtf_analysis[sig_tf]
    confidence = _confidence(
        gate_score_v         = sig_analysis["gate"]["score"],
        alignment_pct        = mtf_sum["alignment"]["alignment_pct"],
        struct_q             = sig_analysis["structure"]["structure_quality"],
        htf_confirmed        = mtf_sum["htf_confirmed"],
        breakout_prob        = sig_analysis["breakout_prob"],
        correction_validated = correction_validated,
        bounce_sequence_valid= bounce_seq_valid,
        fib_confluence       = fib_conf,
    )

    # ---- Reasoning ----
    reasoning = _build_reasoning(
        symbol, side, sig_tf, sl_tf, sig_analysis, mtf_sum,
        correction_validated, bounce_seq_valid, fib_conf,
    )

    return {
        "symbol":                 symbol,
        "side":                   side,
        "signal_timeframe":       sig_tf,
        "sl_timeframe":           sl_tf,
        "trend_direction":        direction,
        "gate_strength":          sig_analysis["gate"]["score"],
        "volatility_compression": sig_analysis["ema"]["compression_score"],
        "breakout_probability":   sig_analysis["breakout_prob"],
        "entry":                  entry,
        "stop_loss":              float(sl),
        "sl_distance_pct":        float(sl_distance_pct * 100),
        "T1":                     targets["T1"],
        "T2":                     targets["T2"],
        "T3":                     targets["T3"],
        "rr":                     rr,
        "confidence":             confidence,
        "htf_confirmed":          mtf_sum["htf_confirmed"],
        "mtf_alignment_pct":      mtf_sum["alignment"]["alignment_pct"],
        "correction_validated":   correction_validated,
        "bounce_sequence_valid":  bounce_seq_valid,
        "fib_confluence":         fib_conf,
        "reasoning":              reasoning,
        # diagnostic
        "atr":                    float(atr_val),
        "structure_quality":      sig_analysis["structure"]["structure_quality"],
        "phase":                  sig_analysis["structure"]["phase"],
    }


def _build_reasoning(
    symbol, side, sig_tf, sl_tf, sig_analysis, mtf_sum,
    correction_validated, bounce_seq_valid, fib_conf,
) -> str:
    parts = []
    ema    = sig_analysis["ema"]
    gate   = sig_analysis["gate"]
    struct = sig_analysis["structure"]

    parts.append(
        f"{symbol} {side.upper()} on {sig_tf}: EMA stack is {ema['stack']}, "
        f"phase={struct['phase']}, trend strength={struct['trend']['strength']:.0f}."
    )
    if gate["is_gate"]:
        comps = ", ".join(f"{k}={v:.2f}" for k, v in gate["components"].items())
        parts.append(f"GATE detected (score={gate['score']:.1f}): {comps}.")
    else:
        parts.append(f"GATE score={gate['score']:.1f} (sub-threshold but actionable).")

    corr = struct["correction"]
    if corr["type"] != "none":
        parts.append(
            f"{corr['type'].title()} correction at EMA{corr['depth_ema']} "
            f"(confidence {corr['confidence']:.0f})."
        )

    # Quality flags
    if not correction_validated:
        parts.append("WARNING: Last correction did not touch EMA200 — possible fake correction.")
    if not bounce_seq_valid:
        parts.append("WARNING: EMA bounce sequence (20→50→100→200) not fully respected.")
    if fib_conf:
        parts.append("Fibonacci confluence confirmed at current correction level.")

    # Correction maturity
    corr_age = struct.get("correction_age", {})
    if corr_age.get("age_pct", 0) > 0:
        mature_str = "mature" if corr_age["mature"] else "early-stage"
        parts.append(
            f"Correction age: {corr_age['age_bars']} bars "
            f"({corr_age['age_pct']:.0f}% of expected — {mature_str})."
        )

    parts.append(
        f"MTF alignment {mtf_sum['alignment']['alignment_pct']:.0f}% "
        f"(dominant={mtf_sum['alignment']['dominant_direction']}); "
        f"HTF confirmed={mtf_sum['htf_confirmed']}. "
        f"SL anchored to {sl_tf} EMA200."
    )
    return " ".join(parts)
