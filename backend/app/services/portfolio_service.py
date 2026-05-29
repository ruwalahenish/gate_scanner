"""
Paper trading execution logic.
No broker APIs — all fills are instant at the provided price.
Capital is tracked in portfolio_config table.
"""
import asyncpg
from uuid import UUID
from app.queries import portfolio as q
from app.exceptions import InsufficientCapitalError, PositionNotFoundError


async def execute_buy(
    conn: asyncpg.Connection,
    symbol: str,
    quantity: int,
    price: float,
    signal_id: UUID | None = None,
    stop_loss: float | None = None,
    t1: float | None = None,
    t2: float | None = None,
    t3: float | None = None,
    notes: str | None = None,
) -> dict:
    """
    Simulated buy: deducts cost from current_capital and creates a position.
    Raises InsufficientCapitalError if capital is insufficient.
    """
    async with conn.transaction():
        config = await q.get_portfolio_config(conn)
        cost = quantity * price
        available = float(config["current_capital"])

        if cost > available:
            raise InsufficientCapitalError(
                f"Need ₹{cost:,.2f} but only ₹{available:,.2f} available"
            )

        await q.update_capital(conn, available - cost)
        position_id = await q.create_position(
            conn, symbol, "BUY", quantity, price,
            stop_loss=stop_loss, t1=t1, t2=t2, t3=t3,
            signal_id=signal_id, notes=notes,
        )
        trade_id = await q.record_trade(
            conn, position_id, symbol, "BUY", quantity, price, notes=notes
        )

    return {"position_id": str(position_id), "trade_id": str(trade_id), "cost": cost}


async def execute_sell(
    conn: asyncpg.Connection,
    position_id: UUID,
    quantity: int,
    price: float,
    exit_reason: str = "manual",
    notes: str | None = None,
) -> dict:
    """
    Simulated sell: closes/reduces position, credits P&L back to capital.
    """
    async with conn.transaction():
        position = await q.get_position(conn, position_id)
        if not position:
            raise PositionNotFoundError()

        sell_qty = min(quantity, position["quantity"])
        avg_entry = float(position["avg_entry"])
        pnl_abs = (price - avg_entry) * sell_qty
        pnl_pct = ((price - avg_entry) / avg_entry) * 100

        config = await q.get_portfolio_config(conn)
        proceeds = sell_qty * price
        await q.update_capital(conn, float(config["current_capital"]) + proceeds)

        new_qty = position["quantity"] - sell_qty
        new_status = "closed" if new_qty == 0 else "partially_closed"
        await q.update_position_quantity(conn, position_id, new_qty, new_status)

        trade_id = await q.record_trade(
            conn, position_id, position["symbol"], "SELL",
            sell_qty, price, exit_reason, pnl_abs, pnl_pct, notes,
        )

    return {
        "trade_id": str(trade_id),
        "pnl_abs": round(pnl_abs, 2),
        "pnl_pct": round(pnl_pct, 4),
        "exit_reason": exit_reason,
    }
