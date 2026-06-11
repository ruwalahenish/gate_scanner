"""
stock_master.py
===============
Raw asyncpg SQL for the stock_master table.
All functions follow the project pattern: asyncpg.Connection as first arg,
parameterized $1/$2 placeholders, no ORM.
"""
from __future__ import annotations

import asyncpg


# ---------------------------------------------------------------------------
# Upsert / Write
# ---------------------------------------------------------------------------

async def upsert_stocks_batch(conn: asyncpg.Connection, rows: list[dict]) -> int:
    """
    Bulk-upsert stock rows using asyncpg copy protocol (fast path).

    Sets sync_status='pending' on every upsert so the fundamentals queue
    picks up newly inserted *and* re-synced rows.
    """
    if not rows:
        return 0

    records = [
        (
            r["symbol"],
            r.get("exchange", "NSE"),
            r["company_name"],
            r.get("isin"),
            r.get("series"),
            r.get("face_value"),
            r.get("listing_date"),
            r.get("market_lot"),
        )
        for r in rows
    ]

    # Step 1: copy into a temp table
    await conn.execute("DROP TABLE IF EXISTS _sm_import")
    await conn.execute("""
        CREATE TEMP TABLE _sm_import (
            symbol       VARCHAR(20),
            exchange     VARCHAR(10),
            company_name VARCHAR(200),
            isin         VARCHAR(12),
            series       VARCHAR(10),
            face_value   NUMERIC(10,2),
            listing_date DATE,
            market_lot   INT
        )
    """)

    await conn.copy_records_to_table(
        "_sm_import",
        records=records,
        columns=["symbol", "exchange", "company_name", "isin", "series",
                 "face_value", "listing_date", "market_lot"],
    )

    # Step 2: upsert from temp into stock_master
    try:
        result = await conn.execute("""
            INSERT INTO stock_master
                (symbol, exchange, company_name, isin, series, face_value, listing_date,
                 market_lot, sync_status, updated_at)
            SELECT
                symbol, exchange, company_name, isin, series, face_value, listing_date,
                market_lot, 'pending', NOW()
            FROM _sm_import
            ON CONFLICT (symbol, exchange) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                isin         = COALESCE(EXCLUDED.isin, stock_master.isin),
                series       = COALESCE(EXCLUDED.series, stock_master.series),
                face_value   = COALESCE(EXCLUDED.face_value, stock_master.face_value),
                listing_date = COALESCE(EXCLUDED.listing_date, stock_master.listing_date),
                market_lot   = COALESCE(EXCLUDED.market_lot, stock_master.market_lot),
                sync_status  = 'pending',
                updated_at   = NOW()
        """)
    finally:
        await conn.execute("DROP TABLE IF EXISTS _sm_import")

    # result is "INSERT 0 N" — parse N
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return len(records)


async def reset_index_flags(conn: asyncpg.Connection) -> None:
    """Clear all index membership flags for NSE stocks before re-applying."""
    await conn.execute("""
        UPDATE stock_master
        SET in_nifty50 = FALSE, in_nifty_next50 = FALSE, in_nifty100 = FALSE,
            in_nifty500 = FALSE, in_midcap150 = FALSE, in_smallcap100 = FALSE,
            is_fno = FALSE, updated_at = NOW()
        WHERE exchange = 'NSE'
    """)


async def set_index_flag(
    conn: asyncpg.Connection, column: str, symbols: list[str]
) -> None:
    """Set a single index flag to TRUE for a list of symbols."""
    if not symbols:
        return
    _ALLOWED = {
        "in_nifty50", "in_nifty_next50", "in_nifty100", "in_nifty500",
        "in_midcap150", "in_smallcap100", "is_fno",
    }
    if column not in _ALLOWED:
        raise ValueError(f"Unknown index column: {column}")
    await conn.execute(
        f"UPDATE stock_master SET {column} = TRUE, updated_at = NOW() "
        "WHERE symbol = ANY($1) AND exchange = 'NSE'",
        symbols,
    )


async def update_fundamentals(
    conn: asyncpg.Connection,
    symbol: str,
    exchange: str,
    sector: str | None,
    industry: str | None,
    market_cap: int | None,
    pe_ratio: float | None,
    pb_ratio: float | None,
    dividend_yield: float | None,
    eps: float | None,
    book_value: float | None,
) -> None:
    await conn.execute("""
        UPDATE stock_master SET
            sector         = $3,
            industry       = $4,
            market_cap     = $5,
            pe_ratio       = $6,
            pb_ratio       = $7,
            dividend_yield = $8,
            eps            = $9,
            book_value     = $10,
            sync_status    = 'enriched',
            last_synced_at = NOW(),
            sync_error     = NULL,
            updated_at     = NOW()
        WHERE symbol = $1 AND exchange = $2
    """, symbol, exchange, sector, industry, market_cap,
        _f(pe_ratio), _f(pb_ratio), _f(dividend_yield), _f(eps), _f(book_value))


async def mark_sync_failed(
    conn: asyncpg.Connection, symbol: str, exchange: str, error: str
) -> None:
    await conn.execute("""
        UPDATE stock_master SET
            sync_status    = 'failed',
            last_synced_at = NOW(),
            sync_error     = $3,
            updated_at     = NOW()
        WHERE symbol = $1 AND exchange = $2
    """, symbol, exchange, str(error)[:500])


# ---------------------------------------------------------------------------
# Read / Query
# ---------------------------------------------------------------------------

async def get_stock(
    conn: asyncpg.Connection, symbol: str, exchange: str = "NSE"
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT * FROM stock_master WHERE symbol = $1 AND exchange = $2",
        symbol.upper(), exchange,
    )


async def search_stocks(
    conn: asyncpg.Connection,
    q: str,
    limit: int = 20,
    exchange: str | None = None,
    index_filter: str | None = None,
    sector: str | None = None,
) -> list[asyncpg.Record]:
    """
    Trigram + prefix search across symbol and company_name.
    Exact symbol prefix match ranked first, then similarity score.
    """
    conditions = ["(symbol ILIKE $1 OR company_name % $2)"]
    params: list = [f"{q.upper()}%", q]
    idx = 3

    if exchange:
        conditions.append(f"exchange = ${idx}")
        params.append(exchange)
        idx += 1

    if index_filter:
        col = _index_filter_to_column(index_filter)
        conditions.append(f"{col} = TRUE")

    if sector:
        conditions.append(f"sector ILIKE ${idx}")
        params.append(f"%{sector}%")
        idx += 1

    conditions.append("sync_status != 'delisted'")

    where = " AND ".join(conditions)
    params.append(limit)

    return await conn.fetch(f"""
        SELECT * FROM stock_master
        WHERE {where}
        ORDER BY
            (symbol = upper($2)) DESC,
            (symbol ILIKE $1) DESC,
            similarity(company_name, $2) DESC
        LIMIT ${idx}
    """, *params)


async def list_stocks(
    conn: asyncpg.Connection,
    exchange: str | None = None,
    index_filter: str | None = None,
    sector: str | None = None,
    sync_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    conditions = []
    params: list = []
    idx = 1

    if exchange:
        conditions.append(f"exchange = ${idx}")
        params.append(exchange)
        idx += 1

    if index_filter:
        col = _index_filter_to_column(index_filter)
        conditions.append(f"{col} = TRUE")

    if sector:
        conditions.append(f"sector ILIKE ${idx}")
        params.append(f"%{sector}%")
        idx += 1

    if sync_status:
        conditions.append(f"sync_status = ${idx}")
        params.append(sync_status)
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = await conn.fetchval(f"SELECT COUNT(*) FROM stock_master {where}", *params)

    params.extend([limit, offset])
    rows = await conn.fetch(f"""
        SELECT * FROM stock_master {where}
        ORDER BY
            CASE WHEN exchange = 'NSE' THEN 0 ELSE 1 END,
            COALESCE(market_cap, 0) DESC,
            symbol
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params)

    return list(rows), int(total)


async def get_sync_queue(
    conn: asyncpg.Connection,
    batch_size: int = 50,
) -> list[asyncpg.Record]:
    """Return next batch of symbols needing fundamentals enrichment."""
    return await conn.fetch("""
        SELECT symbol, exchange FROM stock_master
        WHERE sync_status = 'pending'
           OR (sync_status = 'failed'
               AND (last_synced_at IS NULL
                    OR last_synced_at < NOW() - INTERVAL '6 hours'))
        ORDER BY sync_status, last_synced_at NULLS FIRST
        LIMIT $1
    """, batch_size)


async def get_stats(conn: asyncpg.Connection) -> dict:
    row = await conn.fetchrow("""
        SELECT
            COUNT(*)                                        AS total,
            COUNT(*) FILTER (WHERE exchange = 'NSE')        AS nse_count,
            COUNT(*) FILTER (WHERE exchange = 'BSE')        AS bse_count,
            COUNT(*) FILTER (WHERE sync_status = 'pending') AS pending_count,
            COUNT(*) FILTER (WHERE sync_status = 'enriched') AS enriched_count,
            COUNT(*) FILTER (WHERE sync_status = 'failed')  AS failed_count,
            COUNT(*) FILTER (WHERE sync_status = 'delisted') AS delisted_count,
            COUNT(*) FILTER (WHERE in_nifty50)              AS nifty50_size,
            COUNT(*) FILTER (WHERE in_nifty_next50)         AS nifty_next50_size,
            COUNT(*) FILTER (WHERE in_nifty100)             AS nifty100_size,
            COUNT(*) FILTER (WHERE in_nifty500)             AS nifty500_size,
            COUNT(*) FILTER (WHERE in_midcap150)            AS midcap150_size,
            COUNT(*) FILTER (WHERE in_smallcap100)          AS smallcap100_size,
            COUNT(*) FILTER (WHERE is_fno)                  AS fno_size,
            MAX(last_synced_at)                             AS last_synced_at
        FROM stock_master
    """)
    if not row:
        return {}
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif type(v).__name__ == "Decimal":
            d[k] = int(v)
    return {
        "total": d["total"],
        "by_exchange": {"NSE": d["nse_count"], "BSE": d["bse_count"]},
        "by_sync_status": {
            "pending": d["pending_count"],
            "enriched": d["enriched_count"],
            "failed": d["failed_count"],
            "delisted": d["delisted_count"],
        },
        "index_sizes": {
            "nifty50": d["nifty50_size"],
            "nifty_next50": d["nifty_next50_size"],
            "nifty100": d["nifty100_size"],
            "nifty500": d["nifty500_size"],
            "midcap150": d["midcap150_size"],
            "smallcap100": d["smallcap100_size"],
            "fno": d["fno_size"],
        },
        "last_synced_at": d["last_synced_at"],
    }


# ---------------------------------------------------------------------------
# List with latest scan signal (LATERAL JOIN)
# ---------------------------------------------------------------------------

async def list_stocks_with_signals(
    conn: asyncpg.Connection,
    exchange: str | None = None,
    index_filter: str | None = None,
    sector: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    """
    Paginated stock list enriched with the latest scan signal per stock.
    Uses LATERAL JOIN to efficiently get one signal row per symbol.
    Signal columns are aliased with 'latest_' prefix to avoid collision.
    """
    conditions: list[str] = []
    params: list = []
    idx = 1

    if exchange:
        conditions.append(f"sm.exchange = ${idx}")
        params.append(exchange)
        idx += 1

    if index_filter:
        col = _index_filter_to_column(index_filter)
        conditions.append(f"sm.{col} = TRUE")

    if sector:
        conditions.append(f"sm.sector ILIKE ${idx}")
        params.append(f"%{sector}%")
        idx += 1

    if category:
        conditions.append(f"sig_lat.category = ${idx}")
        params.append(category)
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count query (no LATERAL needed)
    count_where = where.replace("sig_lat.category", "s_count.category") if category else where
    count_lateral = (
        """
        LEFT JOIN LATERAL (
            SELECT sig.category
            FROM signals sig JOIN scans sc ON sig.scan_id = sc.id
            WHERE sig.symbol = sm.symbol AND sc.status = 'done'
            ORDER BY sc.triggered_at DESC LIMIT 1
        ) s_count ON TRUE
        """
        if category else ""
    )
    total = await conn.fetchval(
        f"SELECT COUNT(*) FROM stock_master sm {count_lateral} {count_where}",
        *params[:idx - 1],   # exclude limit/offset params
    )

    params.extend([limit, offset])
    rows = await conn.fetch(f"""
        SELECT sm.*,
               sig_lat.category      AS latest_category,
               sig_lat.rank_score    AS latest_rank_score,
               sig_lat.gate_strength AS latest_gate_strength,
               sig_lat.confidence    AS latest_confidence,
               sig_lat.side          AS latest_side,
               sig_lat.signal_timeframe AS latest_signal_timeframe,
               sig_lat.entry         AS latest_entry,
               sig_lat.stop_loss     AS latest_stop_loss,
               sig_lat.t1            AS latest_t1,
               sig_lat.rr_t1         AS latest_rr_t1
        FROM stock_master sm
        LEFT JOIN LATERAL (
            SELECT sig.category, sig.rank_score, sig.gate_strength, sig.confidence,
                   sig.side, sig.signal_timeframe, sig.entry, sig.stop_loss,
                   sig.t1, sig.rr_t1
            FROM signals sig
            JOIN scans sc ON sig.scan_id = sc.id
            WHERE sig.symbol = sm.symbol AND sc.status = 'done'
            ORDER BY sc.triggered_at DESC
            LIMIT 1
        ) sig_lat ON TRUE
        {where}
        ORDER BY
            COALESCE(sig_lat.rank_score, -1) DESC,
            COALESCE(sm.market_cap, 0) DESC,
            sm.symbol
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params)

    return list(rows), int(total)


# ---------------------------------------------------------------------------
# Universe selection by mode (for scanner / backtester integration)
# ---------------------------------------------------------------------------

_MODE_TO_INDEX_FILTER: dict[str, str | None] = {
    "daily": "in_nifty500",
    "fno":   "is_fno",
    "full":  None,   # all NSE EQ stocks — no index filter
}


async def get_existing_isins(
    conn: asyncpg.Connection, exchange: str = "NSE"
) -> set[str]:
    """Return the set of non-null ISINs already stored for an exchange.
    Used to dedupe dual-listed BSE stocks against NSE rows by ISIN."""
    rows = await conn.fetch(
        "SELECT DISTINCT isin FROM stock_master "
        "WHERE exchange = $1 AND isin IS NOT NULL",
        exchange,
    )
    return {r["isin"] for r in rows}


async def get_master_universe(conn: asyncpg.Connection) -> list[str]:
    """
    Return the complete Master Stock List for the GATE scanner.

    This is every non-delisted stock in stock_master across ALL exchanges, with
    NO index-based filtering whatsoever (no Nifty 50 / 500 / F&O restriction).
    The scanner must always scan the full master list.

    BSE-only rows are returned with a ".BO" suffix so that config.yf_symbol() /
    data_fetcher route them to the correct Yahoo Finance feed; NSE symbols are
    returned bare (".NS" is appended downstream).
    """
    rows = await conn.fetch(
        """
        SELECT CASE WHEN exchange = 'BSE' AND symbol NOT LIKE '%.BO'
                    THEN symbol || '.BO'
                    ELSE symbol
               END AS sym
        FROM stock_master
        WHERE sync_status != 'delisted'
        ORDER BY sym
        """
    )
    return [r["sym"] for r in rows]


async def get_symbols_for_mode(conn: asyncpg.Connection, mode: str) -> list[str]:
    """
    Return NSE symbols from stock_master filtered by scan mode.
    Falls back to empty list if stock_master is not yet populated.
    """
    index_col = _MODE_TO_INDEX_FILTER.get(mode)
    extra = f"AND {index_col} = TRUE" if index_col else ""
    rows = await conn.fetch(
        f"SELECT symbol FROM stock_master "
        f"WHERE exchange = 'NSE' AND sync_status != 'delisted' {extra} "
        f"ORDER BY symbol",
    )
    return [r["symbol"] for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


_INDEX_FILTER_MAP = {
    "nifty50":      "in_nifty50",
    "nifty_next50": "in_nifty_next50",
    "nifty100":     "in_nifty100",
    "nifty500":     "in_nifty500",
    "midcap150":    "in_midcap150",
    "smallcap100":  "in_smallcap100",
    "fno":          "is_fno",
}


def _index_filter_to_column(index_filter: str) -> str:
    col = _INDEX_FILTER_MAP.get(index_filter)
    if not col:
        raise ValueError(f"Unknown index_filter: {index_filter}")
    return col
