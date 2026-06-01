from fastapi import APIRouter, Depends, Query
import asyncio
from concurrent.futures import ThreadPoolExecutor

import asyncpg

from app.dependencies import db_conn

router = APIRouter(tags=["universe"])
_ex = ThreadPoolExecutor(max_workers=2)


def _get_universe_sync() -> list[str]:
    from app.core.scanner.universe import get_full_universe
    return get_full_universe()


def _search_sync(query: str) -> list[str]:
    from app.core.scanner.universe import get_full_universe
    q = query.upper()
    return [s for s in get_full_universe() if q in s][:20]


@router.get("")
async def get_universe():
    loop = asyncio.get_event_loop()
    symbols = await loop.run_in_executor(_ex, _get_universe_sync)
    return {"count": len(symbols), "symbols": symbols}


@router.get("/search")
async def search_universe(
    q: str = Query(..., min_length=1, max_length=20),
    conn: asyncpg.Connection = Depends(db_conn),
):
    """
    Search stocks by symbol or company name.
    Queries stock_master first (returns enriched results with company name and sector).
    Falls back to the static universe list if stock_master is empty or unavailable.
    """
    from app.queries.stock_master import search_stocks

    try:
        rows = await search_stocks(conn, q, limit=20)
        if rows:
            return {
                "results": [
                    {
                        "symbol": r["symbol"],
                        "company_name": r["company_name"],
                        "sector": r["sector"],
                        "in_nifty50": r["in_nifty50"],
                        "exchange": r["exchange"],
                    }
                    for r in rows
                ]
            }
    except Exception:
        pass  # stock_master not yet populated or table missing — fall through

    # Fallback: static symbol-only search
    loop = asyncio.get_event_loop()
    symbols = await loop.run_in_executor(_ex, _search_sync, q)
    return {
        "results": [
            {"symbol": s, "company_name": None, "sector": None,
             "in_nifty50": False, "exchange": "NSE"}
            for s in symbols
        ]
    }
