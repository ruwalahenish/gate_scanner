"""
automation_service.py
=====================
Post-scan automation: auto-create paper trades (BUY signals above rank threshold).

Called by scanner_tasks.py after every scan completes.
"""
from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
import structlog

from app.core.config import (
    AUTO_TRADE_MIN_RANK,
    AUTO_TRADE_MAX_POSITIONS,
    CIRCUIT_BREAKER_CONSECUTIVE_LOSSES,
    CIRCUIT_BREAKER_DAILY_DRAWDOWN_PCT,
    EVENT_SKIP_DAYS,
)
from app.queries import portfolio as q
from app.services.portfolio_service import execute_buy
from app.exceptions import InsufficientCapitalError

log = structlog.get_logger()

_BUY_CATEGORIES = {"INVESTMENT", "SWING", "POSITIONAL"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def _is_circuit_breaker_active(conn: asyncpg.Connection, account_value: float) -> bool:
    """§13: Return True when auto-trading should be suspended for the day.

    Conditions (either triggers the breaker):
      1. The last CIRCUIT_BREAKER_CONSECUTIVE_LOSSES exits are all SL hits.
      2. Today's total realized PnL across all trades ≤ −CIRCUIT_BREAKER_DAILY_DRAWDOWN_PCT × account.
    """
    import datetime

    # Consecutive SL hits — look at the last N+1 exits so we can spot a run cleanly.
    recent = await conn.fetch(
        """SELECT exit_reason FROM trades
           WHERE exit_reason IS NOT NULL
           ORDER BY executed_at DESC LIMIT $1""",
        CIRCUIT_BREAKER_CONSECUTIVE_LOSSES + 1,
    )
    consecutive = 0
    for row in recent:
        if row["exit_reason"] == "sl_hit":
            consecutive += 1
        else:
            break
    if consecutive >= CIRCUIT_BREAKER_CONSECUTIVE_LOSSES:
        log.warning("circuit_breaker_consecutive_losses", count=consecutive)
        return True

    # Daily drawdown: sum of all realized PnL recorded today
    daily_pnl = await conn.fetchval(
        """SELECT COALESCE(SUM(pnl_abs), 0.0) FROM trades
           WHERE executed_at::date = $1 AND pnl_abs IS NOT NULL""",
        datetime.date.today(),
    )
    if account_value > 0 and float(daily_pnl or 0) / account_value <= -CIRCUIT_BREAKER_DAILY_DRAWDOWN_PCT:
        log.warning(
            "circuit_breaker_daily_drawdown",
            pnl_pct=round(float(daily_pnl or 0) / account_value * 100, 2),
        )
        return True

    return False


async def auto_create_paper_trades(
    conn: asyncpg.Connection,
    signals: list[dict],
) -> int:
    """
    Auto-create paper positions for BUY-category signals that meet the rank
    threshold, provided capital and slot limits allow.
    Also updates the watchlist status to 'buy_triggered' for affected symbols.
    Returns the number of new positions created.
    """
    buy_signals = [
        s for s in signals
        if s.get("category") in _BUY_CATEGORIES
        and (s.get("rank_score") or 0) >= AUTO_TRADE_MIN_RANK
        and s.get("entry")
        and s.get("stop_loss")
    ]

    if not buy_signals:
        return 0

    # Sort highest rank first so we fill the best opportunities first
    buy_signals.sort(key=lambda s: s.get("rank_score") or 0, reverse=True)

    open_count = await conn.fetchval(
        "SELECT COUNT(*) FROM positions WHERE status IN ('open','partially_closed')"
    )
    if open_count >= AUTO_TRADE_MAX_POSITIONS:
        return 0

    config = await q.get_portfolio_config(conn)
    if config is None:
        return 0
    available_capital = float(config["current_capital"])
    account_value     = float(config["initial_capital"])
    created = 0

    # §13: Bad-streak circuit breaker — suspend for the day if triggered
    if await _is_circuit_breaker_active(conn, account_value):
        log.info("auto_trade_circuit_breaker_active")
        return 0

    candidate_symbols = [s["symbol"] for s in buy_signals if s.get("symbol")]

    # Prefetch held positions WITH entry/stop data so we can evaluate pyramid eligibility (§11)
    held_rows = await conn.fetch(
        """SELECT symbol, avg_entry, stop_loss, trailing_sl, status
           FROM positions
           WHERE symbol = ANY($1::text[]) AND status IN ('open','partially_closed')
             AND auto_created = TRUE""",
        candidate_symbols,
    )
    # First matching auto-position per symbol (duplicates are rare)
    held_positions: dict[str, asyncpg.Record] = {}
    for r in held_rows:
        if r["symbol"] not in held_positions:
            held_positions[r["symbol"]] = r
    held_symbols = set(held_positions.keys())

    # Current total open risk (§9: ≤ 5% of account)
    risk_row = await conn.fetchrow(
        """SELECT COALESCE(SUM((avg_entry - stop_loss) * quantity), 0) AS total_risk
           FROM positions
           WHERE status IN ('open','partially_closed') AND stop_loss IS NOT NULL"""
    )
    total_open_risk = float(risk_row["total_risk"]) if risk_row else 0.0
    max_total_risk  = account_value * 0.05

    for sig in buy_signals:
        if open_count >= AUTO_TRADE_MAX_POSITIONS:
            break

        symbol = sig.get("symbol")
        if not symbol:
            continue

        # §11: If we already hold this symbol, only allow a pyramid tranche when the
        # existing position is partially_closed (T1 hit) AND the stop is at break-even
        # or better — meaning earlier shares are already risk-free.
        is_pyramid = False
        if symbol in held_symbols:
            ex = held_positions[symbol]
            effective_sl  = float(ex["trailing_sl"] or ex["stop_loss"] or 0)
            avg_entry_ex  = float(ex["avg_entry"] or 0)
            is_pyramid = (
                ex["status"] == "partially_closed"
                and avg_entry_ex > 0
                and effective_sl >= avg_entry_ex
            )
            if not is_pyramid:
                continue  # not risk-free yet — no pyramid

        entry_price    = float(sig["entry"])
        stop_price     = float(sig["stop_loss"])
        risk_per_share = entry_price - stop_price
        if risk_per_share <= 0:
            continue

        # §13: Skip stocks with a corporate event (earnings, record date) within
        # EVENT_SKIP_DAYS calendar days — yfinance calendar, best-effort.
        if await asyncio.to_thread(_has_upcoming_event_sync, symbol, EVENT_SKIP_DAYS):
            log.info("auto_trade_skip_event", symbol=symbol)
            continue

        # 1% risk-based sizing (§9)
        risk_amount = account_value * 0.01
        quantity    = int(risk_amount / risk_per_share)
        max_qty     = int(account_value * 0.25 / entry_price)
        quantity    = min(quantity, max_qty)

        if quantity <= 0:
            continue

        # Total portfolio risk cap: ≤ 5% across all open trades (§9)
        new_trade_risk = risk_per_share * quantity
        if total_open_risk + new_trade_risk > max_total_risk:
            log.info("auto_trade_skip_risk_cap", symbol=symbol,
                     total_risk_pct=round(total_open_risk / account_value * 100, 2))
            continue

        cost = quantity * entry_price
        if cost > available_capital:
            continue

        signal_id = _to_uuid(sig.get("id"))
        source    = "scanner_pyramid" if is_pyramid else "scanner_auto"

        try:
            await execute_buy(
                conn,
                symbol=symbol,
                quantity=quantity,
                price=entry_price,
                signal_id=signal_id,
                stop_loss=_f(sig.get("stop_loss")),
                t1=_f(sig.get("t1")),
                t2=_f(sig.get("t2")),
                t3=_f(sig.get("t3")),
                auto_created=True,
                creation_source=source,
            )
            available_capital -= cost
            total_open_risk   += new_trade_risk
            open_count += 1
            created    += 1
            held_symbols.add(symbol)

            log.info("auto_trade_created", symbol=symbol, qty=quantity,
                     entry=entry_price, pyramid=is_pyramid)

        except InsufficientCapitalError:
            log.info("auto_trade_skip_capital", symbol=symbol)
            break
        except Exception as exc:
            log.warning("auto_trade_failed", symbol=symbol, error=str(exc))

    return created


async def auto_exit_positions(conn: asyncpg.Connection, redis) -> int:
    """
    Check all open/partially-closed auto-created positions against current prices.

    For open positions:   check static SL and targets T1/T2/T3.
      - T1 hit → partial exit (1/3 of quantity), remainder trails EMA20 (§10).
      - T2/T3/SL → full exit of remaining quantity.

    For partially_closed positions (T1 already taken):
      - Fetch daily EMA20, update trailing_sl, exit if price < trailing_sl.
    """
    from concurrent.futures import ThreadPoolExecutor
    from app.services.price_service import get_bulk_prices
    from app.services.portfolio_service import execute_sell
    from app.queries.portfolio import update_trailing_sl

    rows = await conn.fetch(
        "SELECT * FROM positions WHERE status IN ('open','partially_closed') AND auto_created=TRUE"
    )
    if not rows:
        return 0

    symbols = [r["symbol"] for r in rows]
    prices = await get_bulk_prices(symbols, redis)
    closed = 0

    loop = asyncio.get_running_loop()
    _pool = ThreadPoolExecutor(max_workers=4)

    for pos in rows:
        symbol    = pos["symbol"]
        price     = prices.get(symbol)
        if not price:
            continue

        position_id = pos["id"]
        qty         = int(pos["quantity"])
        status      = pos["status"]
        sl          = float(pos["stop_loss"])  if pos["stop_loss"]  else None
        t1          = float(pos["t1"])         if pos["t1"]         else None
        t2          = float(pos["t2"])         if pos["t2"]         else None
        t3          = float(pos["t3"])         if pos["t3"]         else None
        trailing_sl = float(pos["trailing_sl"]) if pos["trailing_sl"] else None

        try:
            if status == "partially_closed":
                # ---- Trail remaining position behind rising 20 EMA (§10) ----
                ema20 = await loop.run_in_executor(_pool, _fetch_ema20_sync, symbol)
                if ema20 is not None and ema20 > 0:
                    await update_trailing_sl(conn, position_id, ema20, "ema20")
                    trailing_sl = ema20

                effective_sl = trailing_sl or sl
                if effective_sl and price <= effective_sl:
                    await execute_sell(conn, position_id, qty, price, exit_reason="trailing_stop")
                    closed += 1
                    log.info("trailing_stop_triggered", symbol=symbol, price=price, ema20=ema20)

            else:
                # ---- Open position: static SL + target ladder ----
                exit_reason = None
                sell_qty    = qty

                if sl and price <= sl:
                    exit_reason = "sl_hit"
                elif t3 and price >= t3:
                    exit_reason = "t3_hit"
                elif t2 and price >= t2:
                    exit_reason = "t2_hit"
                elif t1 and price >= t1:
                    # Partial exit at T1: sell 1/3, trail the rest behind EMA20
                    exit_reason = "t1_hit"
                    sell_qty    = max(1, qty // 3)

                if exit_reason:
                    await execute_sell(conn, position_id, sell_qty, price, exit_reason=exit_reason)
                    # §11: on T1 partial exit, move the stop to break-even so the remaining
                    # shares are risk-free and a pyramid tranche becomes eligible next scan.
                    if exit_reason == "t1_hit" and pos["avg_entry"]:
                        await update_trailing_sl(conn, position_id, float(pos["avg_entry"]), "breakeven")
                    closed += 1
                    log.info("auto_exit_triggered", symbol=symbol, reason=exit_reason, price=price)

        except Exception as exc:
            log.warning("auto_exit_failed", symbol=symbol, error=str(exc))

    _pool.shutdown(wait=False)
    return closed


def _fetch_ema20_sync(symbol: str) -> float | None:
    """Fetch the latest daily 20-EMA value for a symbol via yfinance."""
    try:
        import yfinance as yf
        import pandas as pd
        ticker = yf.Ticker(symbol if "." in symbol else f"{symbol}.NS")
        df = ticker.history(period="60d", interval="1d", auto_adjust=True)
        if df is None or len(df) < 20:
            return None
        ema20 = df["Close"].ewm(span=20, adjust=False).mean().iloc[-1]
        return float(ema20) if not pd.isna(ema20) else None
    except Exception as exc:
        log.warning("ema20_fetch_failed", symbol=symbol, error=str(exc))
        return None


def _has_upcoming_event_sync(symbol: str, days: int) -> bool:
    """Return True if yfinance reports an earnings/event date within `days` calendar days.

    Best-effort: returns False on any error so the stock is never wrongly blocked.
    yfinance calendar coverage for NSE stocks is limited; treat a missing calendar as
    no known event.
    """
    try:
        import datetime
        import yfinance as yf
        cutoff = datetime.date.today() + datetime.timedelta(days=days)
        cal = yf.Ticker(symbol if "." in symbol else f"{symbol}.NS").calendar
        if not cal:
            return False
        # yfinance >= 0.2 returns a dict; older versions return a DataFrame
        if isinstance(cal, dict):
            for d in (cal.get("Earnings Date") or []):
                try:
                    ed = d.date() if hasattr(d, "date") else None
                    if ed and ed <= cutoff:
                        return True
                except Exception:
                    pass
        elif hasattr(cal, "columns"):
            for col in cal.columns:
                try:
                    if hasattr(col, "date") and col.date() <= cutoff:
                        return True
                except Exception:
                    pass
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(val) -> float | None:
    """Convert Decimal / int / str to float, or None."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_uuid(val) -> UUID | None:
    if val is None:
        return None
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        return None
