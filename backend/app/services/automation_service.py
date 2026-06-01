"""
automation_service.py
=====================
Post-scan automation: auto-populate watchlist (WATCH signals) and
auto-create paper trades (BUY signals above rank threshold).

Called by scanner_tasks.py after every scan completes.
"""
from __future__ import annotations

import json
from uuid import UUID

import asyncpg
import structlog

from app.core.config import (
    AUTO_TRADE_MIN_RANK,
    AUTO_TRADE_MAX_POSITIONS,
    AUTO_TRADE_POSITION_SIZE_PCT,
)
from app.queries import portfolio as q
from app.services.portfolio_service import execute_buy
from app.exceptions import InsufficientCapitalError

log = structlog.get_logger()

_BUY_CATEGORIES = {"INVESTMENT", "SWING", "POSITIONAL"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def auto_update_watchlist(
    conn: asyncpg.Connection,
    signals: list[dict],
) -> int:
    """
    Upsert WATCH-category signals into the watchlist.
    - New symbols get an 'added' history event.
    - Existing symbols get a 'gate_update' history event with new GATE data.
    Returns the number of new symbols added.
    """
    watch_signals = [s for s in signals if s.get("category") == "WATCH"]
    added = 0

    for sig in watch_signals:
        symbol = sig.get("symbol")
        if not symbol:
            continue

        gate = _f(sig.get("gate_strength"))
        rank = _f(sig.get("rank_score"))
        entry = _f(sig.get("entry"))
        sl = _f(sig.get("stop_loss"))
        t1 = _f(sig.get("t1"))
        signal_id_raw = sig.get("id")
        signal_id = _to_uuid(signal_id_raw)

        existing = await conn.fetchrow(
            "SELECT id FROM watchlist WHERE symbol=$1", symbol
        )

        if existing:
            await conn.execute(
                """UPDATE watchlist
                   SET gate_strength=$1, rank_score=$2, entry=$3, stop_loss=$4,
                       t1=$5, last_checked_at=NOW(), signal_id=$6, source='scanner'
                   WHERE symbol=$7""",
                gate, rank, entry, sl, t1, signal_id, symbol,
            )
            await conn.execute(
                """INSERT INTO watchlist_history(symbol, event, details)
                   VALUES($1, 'gate_update', $2::jsonb)""",
                symbol,
                json.dumps({"gate_strength": gate, "rank_score": rank}),
            )
        else:
            await conn.execute(
                """INSERT INTO watchlist
                   (symbol, source, status, gate_strength, rank_score, entry, stop_loss, t1, signal_id)
                   VALUES($1,'scanner','active',$2,$3,$4,$5,$6,$7)
                   ON CONFLICT (symbol) DO UPDATE SET
                       gate_strength=EXCLUDED.gate_strength,
                       rank_score=EXCLUDED.rank_score,
                       entry=EXCLUDED.entry,
                       stop_loss=EXCLUDED.stop_loss,
                       t1=EXCLUDED.t1,
                       last_checked_at=NOW(),
                       signal_id=EXCLUDED.signal_id,
                       source='scanner'""",
                symbol, gate, rank, entry, sl, t1, signal_id,
            )
            await conn.execute(
                """INSERT INTO watchlist_history(symbol, event, to_status, details)
                   VALUES($1,'added','active',$2::jsonb)""",
                symbol,
                json.dumps({"source": "scanner", "gate_strength": gate}),
            )
            added += 1

    return added


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
    created = 0

    for sig in buy_signals:
        if open_count >= AUTO_TRADE_MAX_POSITIONS:
            break

        symbol = sig.get("symbol")
        if not symbol:
            continue

        # Skip if we already hold this symbol
        existing_pos = await conn.fetchrow(
            "SELECT id FROM positions WHERE symbol=$1 AND status IN ('open','partially_closed')",
            symbol,
        )
        if existing_pos:
            continue

        entry_price = float(sig["entry"])
        position_capital = available_capital * AUTO_TRADE_POSITION_SIZE_PCT
        quantity = max(1, int(position_capital / entry_price))
        cost = quantity * entry_price

        if cost > available_capital:
            continue

        signal_id = _to_uuid(sig.get("id"))

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
                creation_source="scanner_auto",
            )
            available_capital -= cost
            open_count += 1
            created += 1

            # Promote watchlist status if symbol was being watched
            wl = await conn.fetchrow(
                "SELECT id, status FROM watchlist WHERE symbol=$1", symbol
            )
            if wl and wl["status"] == "active":
                await conn.execute(
                    "UPDATE watchlist SET status='buy_triggered' WHERE symbol=$1",
                    symbol,
                )
                await conn.execute(
                    """INSERT INTO watchlist_history
                       (symbol, event, from_status, to_status, details)
                       VALUES($1,'status_change','active','buy_triggered',$2::jsonb)""",
                    symbol,
                    json.dumps({"auto_created": True, "entry": entry_price}),
                )

            log.info("auto_trade_created", symbol=symbol, qty=quantity, entry=entry_price)

        except InsufficientCapitalError:
            log.info("auto_trade_skip_capital", symbol=symbol)
            break
        except Exception as exc:
            log.warning("auto_trade_failed", symbol=symbol, error=str(exc))

    return created


async def auto_exit_positions(conn: asyncpg.Connection, redis) -> int:
    """
    Check all open auto-created positions against current prices.
    Triggers stop-loss or target exits automatically.
    Returns the number of positions closed.
    """
    from app.services.price_service import get_bulk_prices
    from app.services.portfolio_service import execute_sell

    rows = await conn.fetch(
        "SELECT * FROM positions WHERE status='open' AND auto_created=TRUE"
    )
    if not rows:
        return 0

    symbols = [r["symbol"] for r in rows]
    prices = await get_bulk_prices(symbols, redis)
    closed = 0

    for pos in rows:
        symbol = pos["symbol"]
        price = prices.get(symbol)
        if not price:
            continue

        position_id = pos["id"]
        entry = float(pos["avg_entry"])
        sl = float(pos["stop_loss"]) if pos["stop_loss"] else None
        t1 = float(pos["t1"]) if pos["t1"] else None
        t2 = float(pos["t2"]) if pos["t2"] else None
        t3 = float(pos["t3"]) if pos["t3"] else None

        exit_reason = None
        if sl and price <= sl:
            exit_reason = "sl_hit"
        elif t3 and price >= t3:
            exit_reason = "t3_hit"
        elif t2 and price >= t2:
            exit_reason = "t2_hit"
        elif t1 and price >= t1:
            exit_reason = "t1_hit"

        if exit_reason:
            try:
                await execute_sell(
                    conn, position_id, pos["quantity"], price,
                    exit_reason=exit_reason,
                )
                # Update watchlist status
                new_wl_status = "sl_hit" if exit_reason == "sl_hit" else "target_hit"
                await conn.execute(
                    "UPDATE watchlist SET status=$1 WHERE symbol=$2",
                    new_wl_status, symbol,
                )
                await conn.execute(
                    """INSERT INTO watchlist_history
                       (symbol, event, from_status, to_status, details)
                       VALUES($1,'status_change','buy_triggered',$2,$3::jsonb)""",
                    symbol, new_wl_status,
                    json.dumps({"exit_reason": exit_reason, "exit_price": price}),
                )
                closed += 1
                log.info("auto_exit_triggered", symbol=symbol, reason=exit_reason, price=price)
            except Exception as exc:
                log.warning("auto_exit_failed", symbol=symbol, error=str(exc))

    return closed


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
