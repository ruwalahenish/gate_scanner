from uuid import uuid4, UUID
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import asyncpg

from app.dependencies import db_conn
from app.tasks.backtest_tasks import run_backtest_task

router = APIRouter(tags=["backtests"])


class RunBacktestRequest(BaseModel):
    universe: list[str] = []
    start_date: date
    end_date: Optional[date] = None   # None → defaults to today
    initial_capital: float = 1_000_000


@router.get("")
async def list_backtests(conn: asyncpg.Connection = Depends(db_conn)):
    rows = await conn.fetch(
        "SELECT * FROM backtests ORDER BY started_at DESC LIMIT 20"
    )
    return [_serialize(r) for r in rows]


@router.post("/run")
async def run_backtest(
    body: RunBacktestRequest,
    conn: asyncpg.Connection = Depends(db_conn),
):
    end = body.end_date or date.today()
    if end <= body.start_date:
        raise HTTPException(status_code=422, detail="end_date must be after start_date")

    bt_id = uuid4()
    await conn.execute(
        """INSERT INTO backtests(id, started_at, universe, start_date, end_date, initial_capital, status)
           VALUES($1, NOW(), $2, $3, $4, $5, 'pending')""",
        bt_id, body.universe, body.start_date, end, body.initial_capital,
    )
    run_backtest_task.delay(
        str(bt_id), body.universe,
        body.start_date.isoformat(), end.isoformat(),
        body.initial_capital,
    )
    return {"backtest_id": str(bt_id), "status": "pending"}


@router.get("/{backtest_id}")
async def get_backtest(
    backtest_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    row = await conn.fetchrow("SELECT * FROM backtests WHERE id=$1", backtest_id)
    if not row:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return _serialize(row)


@router.get("/{backtest_id}/trades")
async def get_backtest_trades(
    backtest_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await conn.fetch(
        "SELECT * FROM backtest_trades WHERE backtest_id=$1 ORDER BY entry_date", backtest_id
    )
    return [_serialize(r) for r in rows]


@router.get("/{backtest_id}/equity-curve")
async def get_equity_curve(
    backtest_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await conn.fetch(
        "SELECT * FROM backtest_equity_curve WHERE backtest_id=$1 ORDER BY curve_date",
        backtest_id,
    )
    return [_serialize(r) for r in rows]


async def get_trades_for_symbol(
    conn: asyncpg.Connection, symbol: str, limit: int = 50
) -> list[dict]:
    """Per-symbol backtest trade history across all completed backtests."""
    rows = await conn.fetch("""
        SELECT bt.symbol, bt.entry_date, bt.exit_date, bt.entry_price, bt.exit_price,
               bt.pnl_abs, bt.pnl_pct, bt.exit_reason, bt.holding_days, bt.rr_achieved,
               b.started_at AS backtest_date, b.id AS backtest_id
        FROM backtest_trades bt
        JOIN backtests b ON bt.backtest_id = b.id
        WHERE bt.symbol = $1 AND b.status = 'done'
        ORDER BY bt.entry_date DESC
        LIMIT $2
    """, symbol.upper(), limit)
    return [_serialize(r) for r in rows]


def _serialize(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif type(v).__name__ == "UUID":
            d[k] = str(v)
        elif type(v).__name__ == "Decimal":
            d[k] = float(v)
    return d
