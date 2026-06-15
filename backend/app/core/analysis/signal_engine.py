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
from app.core.analysis import indicators as ind
from app.core.analysis import range_engine


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _signal_tf(mtf_summary: Dict, mtf_data: Optional[Dict] = None) -> Optional[str]:
    """Build the signal on the leading (entry) TF — the daily chart.

    The breakout box, entry, SL and targets are all anchored to the daily
    consolidation; the confirmation TF (weekly) feeds htf_confirmed only, it is
    NOT where the trade is built. Falls back to confirmation TF only if the
    leading TF is somehow unavailable in mtf_data.
    """
    leading = mtf_summary.get("leading_tf")
    if leading and (mtf_data is None or leading in mtf_data):
        return leading
    conf = mtf_summary.get("confirmation_tf")
    if conf and (mtf_data is None or conf in mtf_data):
        return conf
    return leading


def _measured_move_targets(
    entry: float,
    breakout_level: float,
    range_high: float,
    range_low: float,
    signal_tf: str,
    swing_high: Optional[float],
) -> Dict[str, float]:
    """
    Targets anchored to the consolidation box (classic measured move):

      T1 = breakout_level + box_height                 (1x measured move)
      T2 = breakout_level + 1.5x box_height  (or next swing-high resistance)
      T3 = breakout_level + 2.0x box_height

    The per-TF expectancy table is used only as an UPPER sanity bound on T3 so a
    very tall box can't project an unrealistically far target.
    """
    height = max(range_high - range_low, 0.0)
    t1 = breakout_level + height
    t2 = breakout_level + config.MEASURED_MOVE_T2_MULT * height
    t3 = breakout_level + config.MEASURED_MOVE_T3_MULT * height

    # Prefer a real swing-high resistance for T2 when it sits in the projected path.
    if swing_high and t1 < swing_high < t3:
        t2 = swing_high

    # Upper sanity bound from TF expectancy (never the primary driver).
    _, high_pct = config.TARGET_EXPECTANCY.get(signal_tf, (0.20, 0.30))
    upper_cap = entry * (1 + high_pct)
    t3 = min(t3, max(upper_cap, t2 * 1.01))

    # Enforce strict ordering.
    t2 = max(t2, t1 * 1.005)
    t3 = max(t3, t2 * 1.005)
    return {"T1": float(t1), "T2": float(t2), "T3": float(t3)}


def _gate_composite(
    technical_gate: float,
    alignment_pct: float,
    rs_score: float,
    sector_momentum: float,
) -> float:
    """Signal-level GATE strength = per-TF technical gate + cross-cutting context."""
    w = config.GATE_WEIGHTS
    score = (
        w["technical_gate"]    * technical_gate
        + w["trend_alignment"] * alignment_pct
        + w["relative_strength"] * rs_score
        + w["sector_momentum"] * sector_momentum
    )
    return float(max(0.0, min(100.0, score)))


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
    rs_score: Optional[float] = None,
    sector_momentum: Optional[float] = None,
    fundamental_score: Optional[float] = None,
) -> Optional[Dict]:
    """
    Returns a BUY trade signal dict or None if no actionable setup.

    The setup is anchored to the consolidation box: a signal is emitted ONLY when
    the latest close is in an actionable breakout state (BUY_ZONE just below the
    breakout, or a fresh BREAKOUT_CONFIRMED) — never once price is EXTENDED, broken
    down, still accumulating, or when no valid gate exists.

    Parameters
    ----------
    symbol            : str
    mtf_data          : { tf: DataFrame }
    mtf_analysis      : { tf: analyze_timeframe(...) result }
    mtf_sum           : mtf_summary(...) result
    rs_score          : relative strength vs index (0–100); defaults to neutral
    sector_momentum   : sector momentum (0–100); defaults to neutral
    fundamental_score : fundamental quality (0–100); defaults to neutral
    """
    rs_score = config.RS_NEUTRAL if rs_score is None else rs_score
    sector_momentum = config.SECTOR_NEUTRAL if sector_momentum is None else sector_momentum
    fundamental_score = config.FUNDAMENTAL_NEUTRAL if fundamental_score is None else fundamental_score

    sig_tf = _signal_tf(mtf_sum, mtf_data)
    if not sig_tf or sig_tf not in mtf_data or mtf_data[sig_tf].empty:
        return None

    direction = mtf_sum["alignment"]["dominant_direction"]
    if direction != "up":  # bigger-picture must be bullish
        return None
    side = "BUY"

    df_sig = mtf_data[sig_tf]
    last_close = float(df_sig["Close"].iloc[-1])
    if last_close < config.MIN_PRICE:
        return None

    # ---- Consolidation box + breakout state (reuse per-TF gate; recompute if absent) ----
    sig_analysis = mtf_analysis[sig_tf]
    rng = (sig_analysis.get("gate", {}) or {}).get("range") or range_engine.analyze_range(df_sig)
    state = rng.get("state")
    if state not in config.ACTIONABLE_BREAKOUT_STATES:
        return None  # NO_GATE / ACCUMULATION / EXTENDED / BROKEN_DOWN → no buy
    if not rng.get("valid") or not rng.get("range_high") or not rng.get("range_low"):
        return None

    range_high = float(rng["range_high"])
    range_low = float(rng["range_low"])
    breakout_level = float(rng.get("breakout_level") or range_high * (1 + config.BREAKOUT_TRIGGER_BUFFER_PCT))
    volume_buildup = bool((sig_analysis.get("gate", {}) or {}).get("volume_buildup", False))

    # Reject low-volume fake breakouts: a confirmed breakout must show a volume buildup.
    if state == "BREAKOUT_CONFIRMED" and not volume_buildup:
        return None

    # ---- Entry: the current close — in the BUY_ZONE this is still BELOW the
    #      breakout, giving favorable RR before the expansion (issue #5). ----
    entry = last_close

    # ---- Stop Loss: structural, just below the nearest support (ATR-buffered) ----
    # Prefer the most recent higher-low swing inside the box (a realistic breakout
    # stop) over the full box low — on a 20% base the box low is an unrealistically
    # wide stop, whereas the last higher-low keeps risk tight but still structural.
    atr_val = ind.atr(df_sig, 14).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        return None
    swing = sig_analysis["structure"]["swing_levels"]
    swing_high = swing.get("last_swing_high")
    swing_low = swing.get("last_swing_low")
    if swing_low is not None and range_low < float(swing_low) < entry:
        support = float(swing_low)
    else:
        support = range_low
    sl = support - config.SL_ATR_BUFFER_MULT * float(atr_val)
    if sl >= entry:
        return None  # degenerate support vs entry
    sl_distance_pct = abs(entry - sl) / entry
    if sl_distance_pct > config.MAX_SL_DISTANCE_PCT:
        return None

    # ---- Targets: measured move off the box ----
    targets = _measured_move_targets(entry, breakout_level, range_high, range_low, sig_tf, swing_high)

    # ---- RR ratios vs the structural SL ----
    # Gate on the primary measured-move target (T2): risk to box support must be
    # repaid at least MIN_RR_RATIO times by the 1.5x measured move. T1 (1x) is the
    # first scale-out and may sit below the threshold by design.
    rr = {
        "T1": _rr(entry, sl, targets["T1"], side),
        "T2": _rr(entry, sl, targets["T2"], side),
        "T3": _rr(entry, sl, targets["T3"], side),
    }
    if rr["T2"] < config.MIN_RR_RATIO:
        return None

    # ---- Quality flags ----
    sig_ema = sig_analysis["ema"]
    correction_validated = sig_ema.get("correction_validated", True)
    bounce_seq_valid = sig_ema.get("bounce_sequence_valid", True)
    fib_conf = _fib_confluence(entry, swing_high, swing_low)

    # ---- Composite GATE strength (technical gate + trend + RS + sector) ----
    technical_gate = (sig_analysis.get("gate", {}) or {}).get("score", 0.0)
    gate_strength = _gate_composite(
        technical_gate, mtf_sum["alignment"]["alignment_pct"], rs_score, sector_momentum
    )
    breakout_readiness = float(rng.get("proximity_score", 0.0))
    accumulation_score = float((sig_analysis.get("gate", {}) or {}).get(
        "components", {}).get("accumulation", config.SECTOR_NEUTRAL))

    # ---- Confidence ----
    confidence = _confidence(
        gate_score_v         = gate_strength,
        alignment_pct        = mtf_sum["alignment"]["alignment_pct"],
        struct_q             = sig_analysis["structure"]["structure_quality"],
        htf_confirmed        = mtf_sum["htf_confirmed"],
        breakout_prob        = breakout_readiness,
        correction_validated = correction_validated,
        bounce_sequence_valid= bounce_seq_valid,
        fib_confluence       = fib_conf,
    )

    reasoning = _build_reasoning(
        symbol, side, sig_tf, state, rng, sig_analysis, mtf_sum,
        rs_score, sector_momentum, fundamental_score, volume_buildup, fib_conf,
    )

    return {
        "symbol":                 symbol,
        "side":                   side,
        "signal_timeframe":       sig_tf,
        "sl_timeframe":           sig_tf,   # SL is now structural on the signal TF
        "trend_direction":        direction,
        "gate_strength":          gate_strength,
        "volatility_compression": sig_analysis["ema"]["compression_score"],
        "breakout_probability":   breakout_readiness,
        "entry":                  float(entry),
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
        # ---- strategy-rework fields ----
        "breakout_state":         state,
        "range_high":             range_high,
        "range_low":              range_low,
        "breakout_level":         breakout_level,
        "measured_move":          targets["T1"],
        "breakout_readiness":     breakout_readiness,
        "rs_score":               float(rs_score),
        "sector_momentum":        float(sector_momentum),
        "accumulation_score":     accumulation_score,
        "fundamental_score":      float(fundamental_score),
        "volume_buildup":         volume_buildup,
        # diagnostic
        "atr":                    float(atr_val),
        "structure_quality":      sig_analysis["structure"]["structure_quality"],
        "phase":                  sig_analysis["structure"]["phase"],
    }


def _build_reasoning(
    symbol, side, sig_tf, state, rng, sig_analysis, mtf_sum,
    rs_score, sector_momentum, fundamental_score, volume_buildup, fib_conf,
) -> str:
    parts = []
    ema    = sig_analysis["ema"]
    gate   = sig_analysis["gate"]
    struct = sig_analysis["structure"]

    state_label = "in the BUY ZONE just below breakout" if state == "BUY_ZONE" \
        else "on a fresh confirmed breakout"
    parts.append(
        f"{symbol} {side.upper()} on {sig_tf}: price is {state_label} "
        f"(box {rng.get('range_low'):.2f}–{rng.get('range_high'):.2f}, "
        f"trigger {rng.get('breakout_level'):.2f})."
    )

    parts.append(
        f"GATE {gate.get('score', 0):.0f} "
        f"(consolidation {gate.get('consolidation_strength', 0):.0f}, "
        f"breakout proximity {rng.get('proximity_score', 0):.0f}); "
        f"EMA stack {ema['stack']}, phase {struct['phase']}."
    )

    parts.append(
        f"Relative strength {rs_score:.0f} vs Nifty, sector momentum {sector_momentum:.0f}, "
        f"fundamental score {fundamental_score:.0f}. "
        f"Volume buildup: {'yes' if volume_buildup else 'not yet'}."
    )

    if fib_conf:
        parts.append("Fibonacci confluence at the breakout level.")

    parts.append(
        f"MTF alignment {mtf_sum['alignment']['alignment_pct']:.0f}% "
        f"(dominant={mtf_sum['alignment']['dominant_direction']}); "
        f"HTF confirmed={mtf_sum['htf_confirmed']}. "
        f"SL structural below box support."
    )
    return " ".join(parts)
