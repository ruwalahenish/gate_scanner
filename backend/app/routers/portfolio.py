from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
import asyncpg

from app.dependencies import db_conn, redis_client
from app.limiter import limiter
from app.models.portfolio import BuyRequest, SellRequest, PortfolioSummary
from app.queries import portfolio as q
from app.services.portfolio_service import execute_buy, execute_sell
from app.services.price_service import get_bulk_prices
from app.exceptions import InsufficientCapitalError, PositionNotFoundError
import redis.asyncio as aioredis

router = APIRouter(tags=["portfolio"])


class CapitalUpdate(BaseModel):
    amount: float = Field(..., gt=0, description="New capital amount in INR")


@router.get("/summary", response_model=PortfolioSummary)
async def get_summary(
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    summary = await q.get_portfolio_summary(conn)
    positions = await q.get_open_positions(conn)
    if positions:
        symbols = list({p["symbol"] for p in positions})
        prices = await get_bulk_prices(symbols, redis)
        unrealized = sum(
            (prices.get(p["symbol"], p["avg_entry"]) - float(p["avg_entry"])) * p["quantity"]
            for p in positions
        )
        summary["unrealized_pnl"] = round(unrealized, 2)
    return summary


@router.get("/positions")
async def get_positions(
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    positions = await q.get_open_positions(conn)
    if not positions:
        return []
    symbols = list({p["symbol"] for p in positions})
    prices = await get_bulk_prices(symbols, redis)

    result = []
    for p in positions:
        d = _serialize(p)
        current = prices.get(p["symbol"])
        if current:
            entry = float(p["avg_entry"])
            pnl_abs = (current - entry) * p["quantity"]
            d["current_price"] = current
            d["unrealized_pnl"] = round(pnl_abs, 2)
            d["unrealized_pnl_pct"] = round((current - entry) / entry * 100, 2)
        result.append(d)
    return result


@router.get("/trades")
async def get_trades(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows, total = await q.get_trade_history(conn, limit, offset)
    return {"total": total, "items": [_serialize(r) for r in rows]}


@router.post("/buy")
@limiter.limit("30/minute")
async def buy(
    request: Request,  # required by slowapi
    body: BuyRequest,
    conn: asyncpg.Connection = Depends(db_conn),
):
    try:
        signal_id = UUID(body.signal_id) if body.signal_id else None
        result = await execute_buy(
            conn, body.symbol.upper(), body.quantity, body.price,
            signal_id=signal_id,
            stop_loss=body.stop_loss,
            t1=body.t1, t2=body.t2, t3=body.t3,
            notes=body.notes,
        )
        return result
    except InsufficientCapitalError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/sell")
@limiter.limit("30/minute")
async def sell(
    request: Request,  # required by slowapi
    body: SellRequest,
    conn: asyncpg.Connection = Depends(db_conn),
):
    try:
        result = await execute_sell(
            conn,
            UUID(body.position_id),
            body.quantity,
            body.price,
            exit_reason=body.exit_reason,
            notes=body.notes,
        )
        return result
    except PositionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/capital")
@limiter.limit("10/minute")
async def set_capital(
    request: Request,  # required by slowapi
    body: CapitalUpdate,
    conn: asyncpg.Connection = Depends(db_conn),
):
    await q.reset_capital(conn, body.amount)
    return {"updated": True, "amount": body.amount}


@router.put("/positions/{position_id}/sl")
async def update_sl(
    position_id: UUID,
    sl: float,
    level: str = "manual",
    conn: asyncpg.Connection = Depends(db_conn),
):
    pos = await q.get_position(conn, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    await q.update_trailing_sl(conn, position_id, sl, level)
    return {"updated": True, "trailing_sl": sl}


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
