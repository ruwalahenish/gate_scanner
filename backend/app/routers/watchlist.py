from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from app.dependencies import db_conn

router = APIRouter(tags=["watchlist"])


@router.get("")
async def get_watchlist(
    status: str | None = Query(None),
    source: str | None = Query(None),
    conn: asyncpg.Connection = Depends(db_conn),
):
    """
    Returns all watchlist items with enriched signal data.
    Optional filters: status (active|buy_triggered|target_hit|sl_hit|closed),
                      source (manual|scanner).
    """
    conditions = []
    params: list = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if source:
        conditions.append(f"source = ${idx}")
        params.append(source)
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await conn.fetch(
        f"SELECT * FROM watchlist {where} ORDER BY added_at DESC",
        *params,
    )
    return [_serialize(r) for r in rows]


@router.get("/{symbol}/history")
async def get_watchlist_history(
    symbol: str,
    limit: int = Query(50, ge=1, le=200),
    conn: asyncpg.Connection = Depends(db_conn),
):
    """Timeline of status changes and GATE updates for a symbol."""
    rows = await conn.fetch(
        "SELECT * FROM watchlist_history WHERE symbol=$1 ORDER BY occurred_at DESC LIMIT $2",
        symbol.upper(), limit,
    )
    return [_serialize(r) for r in rows]


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
        "INSERT INTO watchlist(symbol, notes, source) VALUES($1, $2, 'manual')",
        sym, notes,
    )
    return {"symbol": sym, "added": True}


@router.delete("/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    conn: asyncpg.Connection = Depends(db_conn),
):
    sym = symbol.upper()
    result = await conn.execute("DELETE FROM watchlist WHERE symbol=$1", sym)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")
    # Record removal in history
    await conn.execute(
        """INSERT INTO watchlist_history(symbol, event, details)
           VALUES($1, 'removed', '{}')""",
        sym,
    )
    return {"symbol": sym, "removed": True}


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
