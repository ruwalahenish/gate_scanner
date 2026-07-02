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
    range_high: float,
    range_low: float,
    signal_tf: str,
) -> Dict[str, float]:
    """
    Fibonacci extension targets anchored to the consolidation base (§10):

      T1 = range_low + 1.272 × box_height  (first partial — Fib 1.272 extension)
      T2 = range_low + 1.618 × box_height  (main target  — Fib 1.618 extension)
      T3 = range_low + 2.618 × box_height  (extended target)

    The per-TF expectancy table is used only as an UPPER sanity bound on T3.
    """
    exts = ind.fibonacci_extensions(range_low, range_high)
    if not exts:
        # Degenerate box — fall back to nominal multiples
        height = max(range_high - range_low, 0.0)
        return {
            "T1": float(range_low + 1.272 * height),
            "T2": float(range_low + 1.618 * height),
            "T3": float(range_low + 2.618 * height),
        }

    t1 = exts["1.272"]
    t2 = exts["1.618"]
    t3 = exts["2.618"]

    # Upper sanity bound from TF expectancy (prevents absurd targets on huge boxes).
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
) -> float:
    """Signal-level GATE strength = per-TF technical gate + MTF trend alignment."""
    w = config.GATE_WEIGHTS
    score = (
        w["technical_gate"]    * technical_gate
        + w["trend_alignment"] * alignment_pct
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
    bounce_sequence_valid: bool,
    fib_confluence: bool,
) -> float:
    """
    Composite 0..100 confidence with GATE Strategy adjustments:

      Base formula:
        30% gate strength + 25% alignment + 20% structure quality + 25% breakout prob

      Adjustments (applied as multipliers after the base):
        - invalid bounce sequence: -INVALID_SEQUENCE_PENALTY
        - Fibonacci confluence:    +FIB_CONFLUENCE_BOOST
        - HTF confirmed:           +10%

    Note: correction_validated is now a hard rejection in generate_signal(),
    so it never reaches here as False.
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
    if not bounce_sequence_valid:
        multiplier -= config.INVALID_SEQUENCE_PENALTY
    if fib_confluence:
        multiplier += config.FIB_CONFLUENCE_BOOST

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
    Returns a BUY trade signal dict or None if no actionable setup.

    A signal is emitted ONLY when state == BREAKOUT_CONFIRMED (price has closed
    above the gate top with volume). BUY_ZONE = price approaching the gate → WATCH,
    not a buy (§6/§7). Never emits on EXTENDED, BROKEN_DOWN, ACCUMULATION, or NO_GATE.
    """

    sig_tf = _signal_tf(mtf_sum, mtf_data)
    if not sig_tf or sig_tf not in mtf_data or mtf_data[sig_tf].empty:
        return None

    direction = mtf_sum["alignment"]["dominant_direction"]
    # Allow neutral overall alignment if the signal TF itself is bullish.
    # This handles the case where 4h is bearish and 1wk is neutral, tying the vote
    # at 1 up / 1 down / 1 neutral = "neutral", even though the daily is clearly up.
    sig_tf_dir = (mtf_sum.get("per_tf_direction") or {}).get(sig_tf, "neutral")
    if direction != "up" and sig_tf_dir != "up":
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

    # Require a real GATE formation: tight coil + volume dryup + accumulation.
    # is_gate = (GATE_TF_WEIGHTS composite >= 45). No contraction → no signal.
    if not bool((sig_analysis.get("gate", {}) or {}).get("is_gate", False)):
        return None

    range_high = float(rng["range_high"])
    range_low = float(rng["range_low"])
    breakout_level = float(rng.get("breakout_level") or range_high * (1 + config.BREAKOUT_TRIGGER_BUFFER_PCT))
    volume_buildup = bool((sig_analysis.get("gate", {}) or {}).get("volume_buildup", False))

    # Reject low-volume fake breakouts: a confirmed breakout must show a volume buildup.
    if state == "BREAKOUT_CONFIRMED" and not volume_buildup:
        return None

    # ---- Level freshness: reject breakouts at a level that has already failed
    # repeatedly nearby (chased/whipsawed resistance, not a fresh gate) ----
    # +1 because the box (duration_bars) excludes today's breakout bar itself.
    prior_failures = range_engine.count_level_tests(
        df_sig, range_high, config.LEVEL_FRESHNESS_LOOKBACK,
        config.LEVEL_FRESHNESS_TOLERANCE, exclude_bars=int(rng.get("duration_bars") or 0) + 1,
    )
    if prior_failures > config.LEVEL_FRESHNESS_MAX_FAILURES:
        return None

    # ---- Entry: current close, which is just above range_high for BREAKOUT_CONFIRMED ----
    entry = last_close

    # ---- §3 hard condition: GATE forms AT the 200 EMA ----
    # Price must be at or near EMA200 on the signal TF. A stock trading more than
    # GATE_PRICE_MIN_EMA200 below EMA200 is in a bear-market breakdown, not a
    # correction-to-EMA200 GATE setup. The EMA cluster spans the EMA200 level so a
    # small buffer (5%) is allowed for fresh breakouts from the cluster bottom.
    _ema_vals = (sig_analysis.get("ema") or {}).get("ema_values") or {}
    _ema200 = float(_ema_vals.get("EMA200") or 0)
    if _ema200 > 0 and entry < _ema200 * (1 - config.GATE_PRICE_MIN_EMA200):
        return None
    # Upper-bound: if the entire consolidation box is more than GATE_RANGE_MAX_ABOVE_EMA200
    # above EMA200, the stock has extended well past its correction-to-EMA200 phase and is
    # now forming a post-breakout base at a much higher level — not a GATE entry.
    if _ema200 > 0 and range_low > _ema200 * (1 + config.GATE_RANGE_MAX_ABOVE_EMA200):
        return None

    # ---- ATR ----
    atr_val = ind.atr(df_sig, 14).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        return None

    # ---- Breakout candle must be bigger-than-usual (§6C / §7) ----
    # "Contraction → expansion" signature: candle range > 1.2× ATR.
    # 1.5 was too strict — quiet breakouts on low-volatility stocks were filtered
    # even when all other GATE conditions were met; 1.2× still excludes dojis/pins.
    candle_range = float(df_sig["High"].iloc[-1]) - float(df_sig["Low"].iloc[-1])
    if candle_range < 1.2 * float(atr_val):
        return None  # doji or narrow candle on breakout = not convincing

    swing = sig_analysis["structure"]["swing_levels"]
    swing_high = swing.get("last_swing_high")
    swing_low  = swing.get("last_swing_low")

    # ---- Stop Loss: 200 EMA of the next-smaller timeframe (§8) ----
    # For a Daily breakout SL_TIMEFRAME_MAP["1d"] = "4h" → use 4h 200 EMA.
    sl_tf = config.SL_TIMEFRAME_MAP.get(sig_tf)
    sl = None
    if sl_tf and sl_tf in mtf_data and not mtf_data[sl_tf].empty:
        ema200_sl = ind.ema(mtf_data[sl_tf]["Close"], 200).iloc[-1]
        if not pd.isna(ema200_sl) and ema200_sl > 0:
            sl = float(ema200_sl) * (1 - 0.005)  # 0.5% buffer below the line
    if sl is None or sl >= entry:
        return None  # no lower-TF data or degenerate SL
    sl_distance_pct = abs(entry - sl) / entry
    if sl_distance_pct > config.MAX_SL_DISTANCE_PCT:
        return None

    # ---- Targets: measured move off the box ----
    targets = _measured_move_targets(entry, range_high, range_low, sig_tf)

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
    if not correction_validated:
        return None  # Check B mandatory: price must have touched 200 EMA (§2/§6B)

    # ---- 200 EMA must be flat-to-rising for buys (§17) ----
    if sig_ema.get("ema_200_slope", 0.0) < 0:
        return None  # declining 200 EMA = macro downtrend, do not buy

    # ---- Setup expiry: if price waited > SETUP_EXPIRY_BARS at the gate without
    #      breaking out, the setup is exhausted — reject (§12) ----
    ema200_val = (sig_ema.get("ema_values") or {}).get("EMA200")
    if ema200_val:
        floor = float(ema200_val) * (1 - config.EMA_TOUCH_TOLERANCE)
        waiting = 0
        for c in reversed(df_sig["Close"].iloc[:-1].tolist()):  # exclude today's breakout bar
            if floor <= c < range_high:
                waiting += 1
            else:
                break
        if waiting > config.SETUP_EXPIRY_BARS:
            return None  # setup loaded too long without breaking — expired

    bounce_seq_valid = sig_ema.get("bounce_sequence_valid", True)
    # Anchor Fib confluence to the SAME leg validated as touching EMA200 above
    # (§3: Fibonacci is "drawn on the last big up-move" — the one being corrected),
    # not an independently-detected fractal swing that may reference a different leg.
    fib_swing_high = sig_ema.get("correction_swing_high") or swing_high
    fib_swing_low = sig_ema.get("correction_swing_low") or swing_low
    fib_conf = _fib_confluence(entry, fib_swing_high, fib_swing_low)

    # ---- Composite GATE strength (technical gate + trend alignment) ----
    technical_gate = (sig_analysis.get("gate", {}) or {}).get("score", 0.0)
    gate_strength = _gate_composite(
        technical_gate, mtf_sum["alignment"]["alignment_pct"]
    )
    breakout_readiness = float(rng.get("proximity_score", 0.0))

    # ---- Confidence ----
    confidence = _confidence(
        gate_score_v         = gate_strength,
        alignment_pct        = mtf_sum["alignment"]["alignment_pct"],
        struct_q             = sig_analysis["structure"]["structure_quality"],
        htf_confirmed        = mtf_sum["htf_confirmed"],
        breakout_prob        = breakout_readiness,
        bounce_sequence_valid= bounce_seq_valid,
        fib_confluence       = fib_conf,
    )

    reasoning = _build_reasoning(
        symbol, side, sig_tf, rng, sig_analysis, mtf_sum, volume_buildup, fib_conf, prior_failures,
    )

    return {
        "symbol":                 symbol,
        "side":                   side,
        "signal_timeframe":       sig_tf,
        "sl_timeframe":           sl_tf or sig_tf,
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
        "volume_buildup":         volume_buildup,
        # diagnostic
        "atr":                    float(atr_val),
        "structure_quality":      sig_analysis["structure"]["structure_quality"],
        "phase":                  sig_analysis["structure"]["phase"],
        "prior_level_failures":   prior_failures,
    }


def _build_reasoning(
    symbol, side, sig_tf, rng, sig_analysis, mtf_sum, volume_buildup, fib_conf, prior_failures=0,
) -> str:
    parts = []
    ema    = sig_analysis["ema"]
    gate   = sig_analysis["gate"]
    struct = sig_analysis["structure"]

    parts.append(
        f"{symbol} {side.upper()} on {sig_tf}: price is on a fresh confirmed breakout "
        f"(box {rng.get('range_low'):.2f}–{rng.get('range_high'):.2f}, "
        f"trigger {rng.get('breakout_level'):.2f})."
    )

    parts.append(
        f"GATE {gate.get('score', 0):.0f} "
        f"(consolidation {gate.get('consolidation_strength', 0):.0f}, "
        f"breakout proximity {rng.get('proximity_score', 0):.0f}); "
        f"EMA stack {ema['stack']}, phase {struct['phase']}. "
        f"Volume buildup: {'yes' if volume_buildup else 'not yet'}."
    )

    if fib_conf:
        parts.append("Fibonacci confluence at the breakout level.")

    if prior_failures > 0:
        parts.append(f"Note: this level was tested {prior_failures} time(s) recently without breaking.")

    parts.append(
        f"MTF alignment {mtf_sum['alignment']['alignment_pct']:.0f}% "
        f"(dominant={mtf_sum['alignment']['dominant_direction']}); "
        f"HTF confirmed={mtf_sum['htf_confirmed']}. "
        f"SL = lower-TF 200 EMA with 0.5% buffer (§8)."
    )
    return " ".join(parts)
