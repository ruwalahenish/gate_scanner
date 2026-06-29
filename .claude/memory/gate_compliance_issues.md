---
name: gate-compliance-issues
description: Complete list of 22 GATE Strategy compliance issues found in the codebase vs GATE_Strategy_clean_new.md, prioritized by severity for one-at-a-time fixing.
metadata:
  type: project
---

All 22 issues identified from comparing `docs/GATE_Strategy_clean_new.md` against the backend scanner (daily-timeframe scope). Fix one at a time; do not batch changes across files.

---

## SECTION A: MISSING IMPLEMENTATIONS (Issues not implemented at all)

### ISSUE-01: Entry Only on BREAKOUT_CONFIRMED — BUY_ZONE Must Be WATCH
- **Severity:** Critical
- **Category:** Missing
- **Strategy:** §6/§7 — "If A+B but C hasn't happened yet → Watch, not a buy. Don't anticipate."
- **Fix:** Removed `"BUY_ZONE"` from `ACTIONABLE_BREAKOUT_STATES`. `config.py`: `ACTIONABLE_BREAKOUT_STATES = ("BREAKOUT_CONFIRMED",)`.
- **Files:** `backend/app/core/config.py`, `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED

### ISSUE-02: Setup Expiry (5–7 Bar Timeout) Not Implemented
- **Severity:** High
- **Category:** Missing
- **Strategy:** §12 — "Breakout must happen within 5–7 bars after A+B. If not → setup failed, move to Ignore."
- **Fix:** `signal_engine.py`: counts consecutive bars where close is between EMA200 floor and `range_high`; returns `None` if `waiting > SETUP_EXPIRY_BARS` (7). `config.py`: `SETUP_EXPIRY_BARS = 7`.
- **Files:** `backend/app/core/analysis/signal_engine.py`, `backend/app/core/config.py`
- **Status:** ✅ FIXED

### ISSUE-03: Breakout Candle Range Expansion Not Checked
- **Severity:** High
- **Category:** Missing
- **Strategy:** §6C / §7 — "Price closes above gate top on a **bigger-than-usual candle**."
- **Fix:** `signal_engine.py`: `candle_range = High[-1] - Low[-1]; if candle_range < 1.5 * atr_val: return None`.
- **Files:** `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED

### ISSUE-04: 200 EMA Slope (Flat-to-Rising) Not Checked
- **Severity:** Medium
- **Category:** Missing
- **Strategy:** §17 — "The 200 EMA is flat-to-rising (for buys)."
- **Fix:** `ema_engine.py`: added `ema_200_slope()` (linear regression over last 20 bars, normalised by price); exposed in `analyze()`. `signal_engine.py`: `if sig_ema.get("ema_200_slope", 0.0) < 0: return None`.
- **Files:** `backend/app/core/analysis/ema_engine.py`, `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED

### ISSUE-05: Trailing Stop Behind 20 EMA Not Implemented
- **Severity:** High
- **Category:** Missing
- **Strategy:** §10 — "Trail the rest [of the position] behind the rising 20 EMA."
- **Fix:** `automation_service.py`: `auto_exit_positions()` rewritten. For `partially_closed` positions: fetches EMA20 via `_fetch_ema20_sync()`, calls `update_trailing_sl()`, exits if `price <= trailing_sl`. `_fetch_ema20_sync()` helper uses yfinance 60d daily data.
- **Files:** `backend/app/services/automation_service.py`
- **Status:** ✅ FIXED

### ISSUE-06: Total Open Risk ≤ 5% Not Tracked or Enforced
- **Severity:** Medium
- **Category:** Missing
- **Strategy:** §9 — "Total risk across all open trades never more than 5% of your account."
- **Fix:** `automation_service.py`: queries `SUM((avg_entry - stop_loss) * quantity)` before each new trade; skips if `total_open_risk + new_trade_risk > account_value * 0.05`. Updates running total after each successful trade.
- **Files:** `backend/app/services/automation_service.py`
- **Status:** ✅ FIXED

### ISSUE-07: Pyramiding Logic Not Implemented
- **Severity:** Low
- **Category:** Missing
- **Strategy:** §11 — "Add a new tranche each time a fresh, smaller gate forms as price climbs. Only add when earlier shares are already risk-free (stop at break-even or better)."
- **Fix:** Two changes: (1) `auto_exit_positions()`: on T1 partial exit, calls `update_trailing_sl(conn, position_id, avg_entry, "breakeven")` to set stop to break-even. (2) `auto_create_paper_trades()`: for held symbols, checks `status == "partially_closed" AND effective_sl >= avg_entry`; if risk-free, allows a pyramid tranche with `creation_source="scanner_pyramid"`.
- **Files:** `backend/app/services/automation_service.py`
- **Status:** ✅ FIXED

### ISSUE-08: Bad-Streak Circuit Breaker Not Implemented
- **Severity:** Low
- **Category:** Missing
- **Strategy:** §13 — "Stop after a bad streak (3 stops in a row, or 3% account loss in a day)."
- **Fix:** `_is_circuit_breaker_active()` added. Checks last N exits for consecutive `sl_hit` and today's `SUM(pnl_abs)` vs `−3%` of account. Called at top of `auto_create_paper_trades()` — returns 0 immediately if triggered. Config constants: `CIRCUIT_BREAKER_CONSECUTIVE_LOSSES=3`, `CIRCUIT_BREAKER_DAILY_DRAWDOWN_PCT=0.03`.
- **Files:** `backend/app/services/automation_service.py`, `backend/app/core/config.py`
- **Status:** ✅ FIXED

### ISSUE-09: Event-Based Skip Not Implemented
- **Severity:** Low
- **Category:** Missing
- **Strategy:** §13 — "Skip any stock with a big event (results/news) before your expected exit."
- **Fix:** `_has_upcoming_event_sync()` added — queries yfinance calendar for earnings dates within `EVENT_SKIP_DAYS` (14) calendar days; handles both dict (yfinance ≥ 0.2) and DataFrame formats; returns False on any error (never wrongly blocks). Called via `asyncio.to_thread()` in `auto_create_paper_trades()` before creating each trade. Config constant: `EVENT_SKIP_DAYS=14`.
- **Files:** `backend/app/services/automation_service.py`, `backend/app/core/config.py`
- **Status:** ✅ FIXED

---

## SECTION B: INCORRECT IMPLEMENTATIONS (Code exists but contradicts the strategy)

### ISSUE-10: Stop Loss Uses Structural SL Instead of Lower-TF 200 EMA
- **Severity:** Critical
- **Category:** Incorrect
- **Strategy:** §8 — "Stop at the 200 EMA of the timeframe one step smaller. Daily → 4h 200 EMA. Place it a small buffer below."
- **Fix:** `signal_engine.py`: `sl_tf = config.SL_TIMEFRAME_MAP.get(sig_tf)`; fetches `ind.ema(mtf_data[sl_tf], 200).iloc[-1]`; `sl = ema200 * (1 - 0.005)`. Returns `None` if SL unavailable or `sl >= entry`.
- **Files:** `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED

### ISSUE-11: Price at 200 EMA Is a Confidence Penalty, Not a Hard Condition
- **Severity:** Critical
- **Category:** Incorrect
- **Strategy:** §2/§6B — Check B is mandatory. "Price has pulled back and touched (or nearly touched) the 200 EMA."
- **Fix:** `signal_engine.py`: `if not correction_validated: return None`. `_confidence()` no longer receives `correction_validated`; removed `UNVALIDATED_CORRECTION_PENALTY` from config.
- **Files:** `backend/app/core/analysis/signal_engine.py`, `backend/app/core/config.py`
- **Status:** ✅ FIXED

### ISSUE-12: Target Levels Use Box-Height Multiples, Not Fibonacci Extensions
- **Severity:** High
- **Category:** Incorrect
- **Strategy:** §10 — "Book a first partial at the 1.272 / 1.618 Fibonacci extension of the breakout move."
- **Fix:** `signal_engine.py`: `_measured_move_targets()` rewritten to call `ind.fibonacci_extensions(range_low, range_high)`. `config.py`: added `FIB_EXT_T1=1.272`, `FIB_EXT_T2=1.618`, `FIB_EXT_T3=2.618`; removed `MEASURED_MOVE_T2_MULT`, `MEASURED_MOVE_T3_MULT`.
- **Files:** `backend/app/core/config.py`, `backend/app/core/analysis/signal_engine.py`, `backend/app/core/analysis/indicators.py`
- **Status:** ✅ FIXED

### ISSUE-13: Position Sizing Is 5% Capital, Not 1% Risk-Based
- **Severity:** Critical
- **Category:** Incorrect
- **Strategy:** §9 — "Shares = (Account × 1%) / (Entry − Stop). Risk exactly 1% per trade."
- **Fix:** `automation_service.py`: `risk_amount = account_value * 0.01; quantity = int(risk_amount / risk_per_share)`. Removed `AUTO_TRADE_POSITION_SIZE_PCT` from config.
- **Files:** `backend/app/services/automation_service.py`, `backend/app/core/config.py`
- **Status:** ✅ FIXED

### ISSUE-14: Maximum Single Position Size Cap (20–25%) Not Enforced
- **Severity:** Medium
- **Category:** Incorrect
- **Strategy:** §9 — "No single position bigger than ~20–25% of your account."
- **Fix:** Resolved together with ISSUE-13. `max_qty = int(account_value * 0.25 / entry_price); quantity = min(quantity, max_qty)`.
- **Files:** `backend/app/services/automation_service.py`
- **Status:** ✅ FIXED (resolved together with ISSUE-13)

### ISSUE-15: Max SL Distance Is 12%, Strategy Specifies 8% for Swing Trades
- **Severity:** Medium
- **Category:** Incorrect
- **Strategy:** §8 — "More than ~8% away on a swing trade → too risky, skip it."
- **Fix:** `config.py`: `MAX_SL_DISTANCE_PCT = 0.08`.
- **Files:** `backend/app/core/config.py`
- **Status:** ✅ FIXED

---

## SECTION C: PARTIALLY IMPLEMENTED LOGIC

### ISSUE-16: EMA Compression Uses Fixed 4% Threshold, Not Relative to Stock's Historical Normal
- **Severity:** Medium
- **Category:** Partial
- **Strategy:** §6A — "The EMAs are unusually close *for this stock*, compared to the stock's recent normal."
- **Fix:** `contraction_engine.py`: `_ema_compression_score()` rewritten to compute rolling 100-bar EMA-spread percentile. Score = 1.0 if current spread is in the bottom 20th percentile of stock's own history (same logic as `_bb_squeeze_score()`).
- **Files:** `backend/app/core/analysis/contraction_engine.py`
- **Status:** ✅ FIXED

### ISSUE-17: Fibonacci Covers Retracement Confirmation But Not Extension Targets
- **Severity:** Medium
- **Category:** Partial
- **Strategy:** §10 — 1.272/1.618 extension targets missing.
- **Fix:** Resolved together with ISSUE-12. Added `fibonacci_extensions()` to `indicators.py`; used in `_measured_move_targets()`.
- **Files:** `backend/app/core/analysis/indicators.py`, `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED (resolved together with ISSUE-12)

### ISSUE-18: Volume Confirmation Is Partial (Volume ✓ / Candle Size ✗)
- **Severity:** High
- **Category:** Partial
- **Strategy:** §6C — Breakout requires BOTH above-average volume AND bigger-than-usual candle.
- **Fix:** Resolved together with ISSUE-03. Candle range > 1.5×ATR check added in `signal_engine.py`.
- **Files:** `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED (resolved together with ISSUE-03)

### ISSUE-19: Correction Validation Detection Is Correct But Enforcement Is Wrong
- **Severity:** Critical
- **Category:** Partial
- **Strategy:** §2/§6B — Price touching 200 EMA before reversal is a mandatory gate condition.
- **Fix:** Resolved together with ISSUE-11. Hard rejection added in `signal_engine.py`.
- **Files:** `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED (resolved together with ISSUE-11)

---

## SECTION D: UNNECESSARY / LEGACY LOGIC

### ISSUE-20: POSITIONAL Category Out of Scope for Daily-Only Strategy
- **Severity:** Low
- **Category:** Legacy
- **Strategy:** Current scope is Daily timeframe only. POSITIONAL = "1h–2h setups" which is a separate mode.
- **Fix:** `config.py`: `DAILY_ONLY_MODE = True`. `classifier.py`: POSITIONAL block gated with `if not config.DAILY_ONLY_MODE:`; default fallback changed from `"POSITIONAL"` → `"WATCH"`.
- **Files:** `backend/app/core/config.py`, `backend/app/core/ranking/classifier.py`
- **Status:** ✅ FIXED

### ISSUE-21: SL_TIMEFRAME_MAP Defined in Config but Never Used
- **Severity:** High
- **Category:** Legacy (dead configuration)
- **Fix:** Resolved together with ISSUE-10. `SL_TIMEFRAME_MAP` is now actively used in `generate_signal()`.
- **Files:** `backend/app/core/config.py`, `backend/app/core/analysis/signal_engine.py`
- **Status:** ✅ FIXED (resolved together with ISSUE-10)

### ISSUE-22: BUY_ZONE in ACTIONABLE_BREAKOUT_STATES Is an Architectural Misclassification
- **Severity:** Critical
- **Category:** Legacy
- **Strategy:** §8 — BUY_ZONE = pre-breakout = WATCH, not BUY.
- **Fix:** Resolved together with ISSUE-01. `ACTIONABLE_BREAKOUT_STATES = ("BREAKOUT_CONFIRMED",)`.
- **Files:** `backend/app/core/config.py`
- **Status:** ✅ FIXED (resolved together with ISSUE-01)

---

## Fix Order Summary

| Priority | Issue IDs | Severity | Status |
|----------|-----------|----------|--------|
| 1st | ISSUE-01, ISSUE-22 | Critical — same fix (`config.py` constant) | ✅ FIXED |
| 2nd | ISSUE-11, ISSUE-19 | Critical — same fix (`signal_engine.py` hard rejection) | ✅ FIXED |
| 3rd | ISSUE-10, ISSUE-21 | Critical — same fix (activate 4h 200 EMA SL) | ✅ FIXED |
| 4th | ISSUE-13, ISSUE-14 | Critical — same fix (1% risk-based sizing) | ✅ FIXED |
| 5th | ISSUE-03, ISSUE-18 | High — candle range expansion check | ✅ FIXED |
| 6th | ISSUE-12, ISSUE-17 | High — Fibonacci extension targets | ✅ FIXED |
| 7th | ISSUE-05 | High — 20 EMA trailing stop | ✅ FIXED |
| 8th | ISSUE-02 | High — setup expiry 5–7 bars | ✅ FIXED |
| 9th | ISSUE-04 | Medium — 200 EMA slope check | ✅ FIXED |
| 10th | ISSUE-16 | Medium — relative EMA compression | ✅ FIXED |
| 11th | ISSUE-15 | Medium — SL cap 12%→8% | ✅ FIXED |
| 12th | ISSUE-06 | Medium — total open risk | ✅ FIXED |
| 13th | ISSUE-20 | Low — POSITIONAL suppression | ✅ FIXED |
| 14th | ISSUE-07, ISSUE-08, ISSUE-09 | Low — pyramiding, circuit breaker, events | ✅ FIXED |

## Rule: Fix one issue group at a time. Read target file before every change. Run the dev stack after every fix. Never batch edits across unrelated issues.
