from uuid import UUID, uuid4
import asyncpg


async def get_portfolio_config(conn: asyncpg.Connection) -> asyncpg.Record:
    return await conn.fetchrow("SELECT * FROM portfolio_config LIMIT 1")


async def update_capital(conn: asyncpg.Connection, new_capital: float) -> None:
    await conn.execute(
        "UPDATE portfolio_config SET current_capital=$1, updated_at=NOW()",
        new_capital,
    )


async def create_position(
    conn: asyncpg.Connection,
    symbol: str,
    side: str,
    quantity: int,
    avg_entry: float,
    stop_loss: float | None = None,
    t1: float | None = None,
    t2: float | None = None,
    t3: float | None = None,
    signal_id: UUID | None = None,
    notes: str | None = None,
) -> UUID:
    pos_id = uuid4()
    await conn.execute(
        """INSERT INTO positions
           (id, symbol, side, quantity, avg_entry, stop_loss, t1, t2, t3, signal_id, notes)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
        pos_id, symbol, side, quantity, avg_entry,
        stop_loss, t1, t2, t3, signal_id, notes,
    )
    return pos_id


async def get_open_positions(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        "SELECT * FROM positions WHERE status IN ('open','partially_closed') ORDER BY opened_at DESC"
    )


async def get_position(conn: asyncpg.Connection, position_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM positions WHERE id=$1", position_id)


async def update_position_quantity(
    conn: asyncpg.Connection, position_id: UUID, new_quantity: int, new_status: str
) -> None:
    await conn.execute(
        "UPDATE positions SET quantity=$2, status=$3 WHERE id=$1",
        position_id, new_quantity, new_status,
    )


async def update_trailing_sl(
    conn: asyncpg.Connection, position_id: UUID, sl: float, level: str
) -> None:
    await conn.execute(
        "UPDATE positions SET trailing_sl=$2, current_sl_level=$3 WHERE id=$1",
        position_id, sl, level,
    )


async def record_trade(
    conn: asyncpg.Connection,
    position_id: UUID,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    exit_reason: str | None = None,
    pnl_abs: float | None = None,
    pnl_pct: float | None = None,
    notes: str | None = None,
) -> UUID:
    trade_id = uuid4()
    await conn.execute(
        """INSERT INTO trades
           (id, position_id, symbol, side, quantity, price, exit_reason, pnl_abs, pnl_pct, notes)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
        trade_id, position_id, symbol, side, quantity, price,
        exit_reason, pnl_abs, pnl_pct, notes,
    )
    return trade_id


async def get_trade_history(
    conn: asyncpg.Connection, limit: int = 50, offset: int = 0
) -> tuple[list[asyncpg.Record], int]:
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM trades WHERE pnl_abs IS NOT NULL"
    )
    rows = await conn.fetch(
        """SELECT * FROM trades WHERE pnl_abs IS NOT NULL
           ORDER BY executed_at DESC LIMIT $1 OFFSET $2""",
        limit, offset,
    )
    return rows, total


async def get_portfolio_summary(conn: asyncpg.Connection) -> dict:
    config = await get_portfolio_config(conn)
    trades = await conn.fetchrow(
        """SELECT
             COUNT(*) FILTER (WHERE pnl_abs IS NOT NULL) AS total_trades,
             COUNT(*) FILTER (WHERE pnl_abs > 0) AS winning_trades,
             COALESCE(SUM(pnl_abs) FILTER (WHERE pnl_abs IS NOT NULL), 0) AS realized_pnl
           FROM trades"""
    )
    positions = await conn.fetchrow(
        "SELECT COUNT(*) AS open_count FROM positions WHERE status IN ('open','partially_closed')"
    )
    invested = await conn.fetchval(
        "SELECT COALESCE(SUM(quantity * avg_entry), 0) FROM positions WHERE status IN ('open','partially_closed')"
    ) or 0.0

    total_trades = trades["total_trades"] or 0
    winning = trades["winning_trades"] or 0
    realized = float(trades["realized_pnl"] or 0)
    initial = float(config["initial_capital"])
    current = float(config["current_capital"])

    return {
        "initial_capital": initial,
        "current_capital": current,
        "invested_value": float(invested),
        "unrealized_pnl": 0.0,  # computed live with current prices
        "realized_pnl": realized,
        "total_pnl": current - initial + realized,
        "total_pnl_pct": ((current - initial + realized) / initial) * 100 if initial else 0,
        "open_positions": positions["open_count"],
        "total_trades": total_trades,
        "winning_trades": winning,
        "win_rate": (winning / total_trades * 100) if total_trades else 0.0,
    }
