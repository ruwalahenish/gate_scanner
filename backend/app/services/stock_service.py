"""
stock_service.py
================
Async service layer for stock_master operations.
Runs CPU/IO-bound sync logic in a ThreadPoolExecutor,
matching the pattern in scan_service.py and price_service.py.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor

import asyncpg

from app.queries import stock_master as q
from app.utils.serialization import serialize_row

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="stock_sync")


# ---------------------------------------------------------------------------
# Phase 1 — NSE equity upsert
# ---------------------------------------------------------------------------

async def sync_nse_equity_async(conn: asyncpg.Connection) -> dict:
    """
    Download EQUITY_L.csv and bulk-upsert all EQ-series stocks.
    Returns summary dict: {total: int}.
    """
    from app.core.scanner.universe.stock_master_sync import phase1_fetch_nse_equity

    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(_executor, phase1_fetch_nse_equity)

    count = await q.upsert_stocks_batch(conn, rows)
    logger.info("stock_service.sync_equity: upserted %d rows", count)
    return {"total": count, "source": "NSE EQUITY_L.csv"}


# ---------------------------------------------------------------------------
# Phase 2 — Index membership flags
# ---------------------------------------------------------------------------

async def sync_index_flags_async(conn: asyncpg.Connection) -> dict:
    """
    Download all 6 Nifty index CSVs and refresh index membership flags.
    Returns dict of {index_name: constituent_count}.
    """
    from app.core.scanner.universe.stock_master_sync import phase2_fetch_index_memberships
    from app.core.scanner.universe.nse_universe import FNO_STOCKS

    loop = asyncio.get_event_loop()
    symbol_sets = await loop.run_in_executor(_executor, phase2_fetch_index_memberships)

    # Add FNO set from the existing static list (NSE doesn't publish a clean CSV for this)
    symbol_sets["fno"] = set(FNO_STOCKS)

    await q.reset_index_flags(conn)

    column_map = {
        "nifty50":      "in_nifty50",
        "nifty_next50": "in_nifty_next50",
        "nifty100":     "in_nifty100",
        "nifty500":     "in_nifty500",
        "midcap150":    "in_midcap150",
        "smallcap100":  "in_smallcap100",
        "fno":          "is_fno",
    }

    summary: dict = {}
    for key, col in column_map.items():
        symbols = list(symbol_sets.get(key, set()))
        if symbols:
            await q.set_index_flag(conn, col, symbols)
        summary[key] = len(symbols)

    logger.info("stock_service.sync_index_flags: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Phase 3 — yfinance fundamentals enrichment
# ---------------------------------------------------------------------------

async def enrich_fundamentals_async(
    conn: asyncpg.Connection, batch_size: int = 50
) -> dict:
    """
    Fetch yfinance fundamentals for the next batch of pending/failed rows.
    Returns: {processed: int, succeeded: int, failed: int}.
    """
    from app.core.scanner.universe.stock_master_sync import phase3_enrich_fundamentals

    pending = await q.get_sync_queue(conn, batch_size=batch_size)
    if not pending:
        return {"processed": 0, "succeeded": 0, "failed": 0}

    pending_list = [dict(r) for r in pending]

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        _executor,
        functools.partial(
            phase3_enrich_fundamentals,
            pending_list,
            batch_size=10,
            delay_between_batches=2.0,
        ),
    )

    succeeded = failed = 0
    for r in results:
        if r["success"]:
            await q.update_fundamentals(
                conn,
                r["symbol"], r["exchange"],
                r.get("sector"), r.get("industry"),
                r.get("market_cap"),
                r.get("pe_ratio"), r.get("pb_ratio"),
                r.get("dividend_yield"), r.get("eps"), r.get("book_value"),
            )
            succeeded += 1
        else:
            await q.mark_sync_failed(conn, r["symbol"], r["exchange"], r.get("error", ""))
            failed += 1

    return {"processed": len(results), "succeeded": succeeded, "failed": failed}


# ---------------------------------------------------------------------------
# Read helpers (used by routers and other services)
# ---------------------------------------------------------------------------

async def get_company_name(conn: asyncpg.Connection, symbol: str) -> str | None:
    """
    Fast lookup of company_name for an NSE symbol.
    Used by signals router to enrich signal rows with display names.
    """
    row = await q.get_stock(conn, symbol.upper(), "NSE")
    return row["company_name"] if row else None


async def search_stocks_async(
    conn: asyncpg.Connection, search_q: str, **kwargs
) -> list[dict]:
    rows = await q.search_stocks(conn, search_q, **kwargs)
    return [_serialize(r) for r in rows]


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------

# Canonical implementation lives in app/utils/serialization.py
_serialize = serialize_row
