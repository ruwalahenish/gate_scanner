from fastapi import APIRouter, Depends, HTTPException
import asyncpg

from app.dependencies import db_conn

router = APIRouter(tags=["watchlist"])


@router.get("")
async def get_watchlist(conn: asyncpg.Connection = Depends(db_conn)):
    rows = await conn.fetch("SELECT * FROM watchlist ORDER BY added_at DESC")
    return [dict(r) for r in rows]


@router.post("")
async def add_to_watchlist(
    symbol: str,
    notes: str | None = None,
    conn: asyncpg.Connection = Depends(db_conn),
):
    sym = symbol.upper()
    existing = await conn.fetchrow("SELECT id FROM watchlist WHERE symbol=$1", sym)
    if existing:
        raise HTTPException(status_code=409, detail=f"{sym} already in watchlist")
    await conn.execute(
        "INSERT INTO watchlist(symbol, notes) VALUES($1, $2)", sym, notes
    )
    return {"symbol": sym, "added": True}


@router.delete("/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    conn: asyncpg.Connection = Depends(db_conn),
):
    result = await conn.execute(
        "DELETE FROM watchlist WHERE symbol=$1", symbol.upper()
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")
    return {"symbol": symbol.upper(), "removed": True}
