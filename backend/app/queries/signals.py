import json
from uuid import UUID, uuid4
import asyncpg


def _to_text(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return str(v)


async def insert_signals_batch(
    conn: asyncpg.Connection, scan_id: UUID, signals: list[dict]
) -> int:
    """Batch-insert signals using asyncpg copy protocol (fast path)."""
    if not signals:
        return 0

    rows = []
    for s in signals:
        signal = s.get("signal") or {}
        cls = s.get("classification") or {}
        mtf = s.get("mtf_summary") or {}

        # Daily breakout box context — present even for WATCH rows (no signal) so the
        # critical level / range still shows. Signal fields win when a signal exists.
        daily_rng = ((s.get("mtf_per_tf", {}) or {}).get("1d", {}) or {}).get("gate", {}) or {}
        daily_rng = daily_rng.get("range") or {}
        breakout_state = signal.get("breakout_state") or daily_rng.get("state")
        range_high = signal.get("range_high") if signal.get("range_high") is not None else daily_rng.get("range_high")
        range_low = signal.get("range_low") if signal.get("range_low") is not None else daily_rng.get("range_low")
        breakout_level = (signal.get("breakout_level")
                          if signal.get("breakout_level") is not None
                          else (cls.get("critical_level") or daily_rng.get("breakout_level")))

        rr = signal.get("rr") or {}
        rows.append((
            uuid4(), scan_id,
            signal.get("symbol") or s.get("symbol", ""),
            cls.get("category", "IGNORE"),
            signal.get("side"),
            signal.get("signal_timeframe"),
            signal.get("sl_timeframe"),
            signal.get("trend_direction"),
            _f(signal.get("entry")),
            _f(signal.get("stop_loss")),
            _f(signal.get("sl_distance_pct")),
            _f(signal.get("T1")),
            _f(signal.get("T2")),
            _f(signal.get("T3")),
            _f(rr.get("T1")),
            _f(rr.get("T2")),
            _f(rr.get("T3")),
            _f(signal.get("gate_strength")),
            _f(signal.get("volatility_compression")),
            _f(signal.get("breakout_probability")),
            _f(signal.get("confidence")),
            _f(signal.get("rank_score")),
            _f(signal.get("mtf_alignment_pct") or (mtf.get("alignment") or {}).get("alignment_pct")),
            _f(signal.get("structure_quality")),
            _f(signal.get("atr")),
            signal.get("htf_confirmed"),
            signal.get("correction_validated"),
            signal.get("bounce_sequence_valid"),
            signal.get("fib_confluence"),
            signal.get("phase"),
            json.dumps(signal.get("trailing_plan")) if signal.get("trailing_plan") else None,
            _to_text(signal.get("reasoning") or cls.get("reasoning")),
            # ---- strategy-rework columns (migration 008) ----
            breakout_state,
            _f(range_high),
            _f(range_low),
            _f(breakout_level),
            _f(signal.get("measured_move")),
            _f(signal.get("rs_score")),
            _f(signal.get("sector_momentum")),
            _f(signal.get("accumulation_score")),
            _f(signal.get("fundamental_score")),
            signal.get("volume_buildup"),
        ))

    await conn.copy_records_to_table(
        "signals",
        records=rows,
        columns=[
            "id", "scan_id", "symbol", "category", "side",
            "signal_timeframe", "sl_timeframe", "trend_direction",
            "entry", "stop_loss", "sl_distance_pct",
            "t1", "t2", "t3", "rr_t1", "rr_t2", "rr_t3",
            "gate_strength", "volatility_compression", "breakout_probability",
            "confidence", "rank_score", "mtf_alignment_pct", "structure_quality", "atr",
            "htf_confirmed", "correction_validated", "bounce_sequence_valid", "fib_confluence",
            "phase", "trailing_plan", "reasoning",
            "breakout_state", "range_high", "range_low", "breakout_level", "measured_move",
            "rs_score", "sector_momentum", "accumulation_score", "fundamental_score",
            "volume_buildup",
        ],
    )
    return len(rows)


def _f(v) -> float | None:
    """Safe float conversion."""
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


async def get_latest_signals(
    conn: asyncpg.Connection,
    category: str | None = None,
    min_rank: float = 0,
    min_gate: float = 0,
    side: str | None = None,
    timeframe: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    where = [
        "sc.status = 'done'",
        "sc.id = (SELECT id FROM scans WHERE status='done' ORDER BY triggered_at DESC LIMIT 1)",
        "s.rank_score >= $1",
        "COALESCE(s.gate_strength, 0) >= $2",
    ]
    params: list = [min_rank, min_gate]
    idx = 3

    if category:
        where.append(f"s.category = ${idx}")
        params.append(category)
        idx += 1
    if side:
        where.append(f"s.side = ${idx}")
        params.append(side)
        idx += 1
    if timeframe:
        where.append(f"s.signal_timeframe = ${idx}")
        params.append(timeframe)
        idx += 1

    where_clause = " AND ".join(where)
    enriched_base = f"""
        FROM signals s
        JOIN scans sc ON s.scan_id = sc.id
        LEFT JOIN stock_master sm ON s.symbol = sm.symbol AND sm.exchange = 'NSE'
        WHERE {where_clause}
    """
    plain_base = f"""
        FROM signals s
        JOIN scans sc ON s.scan_id = sc.id
        WHERE {where_clause}
    """

    try:
        total = await conn.fetchval(f"SELECT COUNT(*) {enriched_base}", *params)
        rows = await conn.fetch(
            f"""SELECT s.*,
                       sm.company_name,
                       sm.sector
                {enriched_base}
                ORDER BY s.rank_score DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
    except asyncpg.UndefinedTableError:
        # stock_master migration not yet applied — fall back to symbol-only query
        total = await conn.fetchval(f"SELECT COUNT(*) {plain_base}", *params)
        rows = await conn.fetch(
            f"SELECT s.* {plain_base} ORDER BY s.rank_score DESC LIMIT ${idx} OFFSET ${idx+1}",
            *params, limit, offset,
        )
    return rows, total


async def get_signal_history(
    conn: asyncpg.Connection, symbol: str, limit: int = 30
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """SELECT s.*, sc.triggered_at AS scan_date
           FROM signals s JOIN scans sc ON s.scan_id = sc.id
           WHERE s.symbol = $1 AND sc.status = 'done'
           ORDER BY sc.triggered_at DESC LIMIT $2""",
        symbol, limit,
    )
