"""
Celery task for running the walk-forward backtester.

Streaming mode (default for /run):
  Universe is split into STREAM_BATCH_SIZE-symbol batches.  After each batch
  completes, per-stock metrics are persisted to backtest_stock_results and a
  backtest.stock_complete WebSocket event is published so the browser can render
  results incrementally.

Single-stock mode (used by POST /api/stocks/{symbol}/backtest):
  _run_backtest_sync / _persist_backtest are kept unchanged for this path.
"""
import asyncio
import json
import sys
import traceback
from collections import Counter
from uuid import UUID

import structlog
from app.tasks.celery_app import celery_app

log = structlog.get_logger()

STREAM_BATCH_SIZE = 10


@celery_app.task(
    bind=True,
    name="app.tasks.backtest_tasks.run_backtest_task",
    max_retries=1,
    default_retry_delay=60,
    soft_time_limit=1800,
    time_limit=1860,
    queue="backtests",
)
def run_backtest_task(
    self,
    backtest_id: str,
    universe: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000,
    investment_per_stock: float | None = None,
):
    # asyncpg requires SelectorEventLoop on Windows (Celery defaults to ProactorEventLoop)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(
            _run_backtest_async(
                backtest_id, universe, start_date, end_date,
                initial_capital, investment_per_stock,
            )
        )
    except Exception as exc:
        tb = traceback.format_exc()
        log.error("backtest_failed", backtest_id=backtest_id, error=str(exc), traceback=tb)
        try:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(_mark_failed(backtest_id, tb))
        except Exception as mark_exc:
            log.error("backtest_mark_failed_error", backtest_id=backtest_id, error=str(mark_exc))
        raise exc


# ── Streaming batch-sequential runner ──────────────────────────────────────────

async def _run_backtest_async(
    backtest_id: str,
    universe: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    investment_per_stock: float | None,
):
    import asyncpg
    from app.config import get_settings
    import redis.asyncio as aioredis
    from concurrent.futures import ThreadPoolExecutor

    settings = get_settings()
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    bid = UUID(backtest_id)
    local_pool = None

    async def pub(channel: str, event_type: str, payload: dict):
        await redis_conn.publish(channel, json.dumps(
            {"type": event_type, "payload": payload, "timestamp": _now()}
        ))

    try:
        # Resolve universe using the same 3-tier fallback as the scanner service:
        #   1. stock_master WHERE in_nifty500=TRUE  (populated after index-flag sync)
        #   2. stock_master all NSE stocks          (master populated, flags not yet set)
        #   3. static hardcoded nse_universe list   (stock_master not populated at all)
        if not universe:
            _tmp = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=2)
            try:
                from app.queries.stock_master import get_symbols_for_mode
                async with _tmp.acquire() as c:
                    universe = await get_symbols_for_mode(c, "daily")   # in_nifty500=TRUE
                    if len(universe) < 10:
                        # Index flags not set yet — fall back to all master stocks
                        universe = await get_symbols_for_mode(c, "full")
            except Exception:
                universe = []
            finally:
                await _tmp.close()

            if len(universe) < 10:
                # stock_master empty — fall back to static hardcoded universe
                from app.core.scanner.universe.nse_universe import get_full_universe
                universe = get_full_universe(include_midcap=True, include_smallcap=False)
                log.warning(
                    "backtest_universe_fallback",
                    backtest_id=backtest_id,
                    hint="stock_master empty or unpopulated — using static nse_universe",
                    symbols=len(universe),
                )

        total = len(universe)
        # Per-stock capital: explicit override or evenly split (min ₹5,000)
        per_stock = investment_per_stock if investment_per_stock is not None \
                    else max(initial_capital / total if total else initial_capital, 5_000)

        # Fresh local pool — NeonDB closes idle connections after ~5 minutes.
        local_pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=3, command_timeout=30
        )
        async with local_pool.acquire() as conn:
            try:
                await conn.execute(
                    "UPDATE backtests SET status='running', total_symbols=$2 WHERE id=$1",
                    bid, total,
                )
            except Exception:
                # Fallback: migration 006 not yet applied — update status only
                await conn.execute(
                    "UPDATE backtests SET status='running' WHERE id=$1", bid
                )

        all_trades: list[dict] = []
        scanned = 0
        cancelled = False
        batches = [universe[i:i + STREAM_BATCH_SIZE] for i in range(0, total, STREAM_BATCH_SIZE)]
        loop = asyncio.get_running_loop()

        with ThreadPoolExecutor(max_workers=2) as ex:
            for batch in batches:
                # Announce which symbols are currently being scanned
                await pub("backtest:progress", "backtest.batch_scanning", {
                    "backtest_id": backtest_id,
                    "symbols": batch,
                    "completed": scanned,
                    "total": total,
                })
                try:
                    result = await loop.run_in_executor(
                        ex, _run_batch_sync, batch, start_date, end_date, per_stock
                    )

                    # Persist trades + per-stock summary to DB
                    async with local_pool.acquire() as conn:
                        if result["trades"]:
                            await conn.executemany(
                                """INSERT INTO backtest_trades
                                   (id, backtest_id, symbol, entry_date, entry_price, sl_price,
                                    t1, t2, t3, quantity, timeframe, category,
                                    exit_date, exit_price, exit_reason, pnl_abs, pnl_pct,
                                    holding_days, rr_achieved)
                                   VALUES (gen_random_uuid(),$1,$2,$3,$4,$5,
                                           $6,$7,$8,$9,$10,$11,
                                           $12,$13,$14,$15,$16,$17,$18)""",
                                [
                                    (
                                        bid,
                                        t["symbol"], t["entry_date"], t["entry_price"],
                                        t["sl_price"],
                                        t.get("t1"), t.get("t2"), t.get("t3"),
                                        t.get("quantity"), t.get("tf"), t.get("category"),
                                        t.get("exit_date"), t.get("exit_price"),
                                        t.get("exit_reason"),
                                        t.get("pnl_abs"), t.get("pnl_pct"),
                                        t.get("holding_days"), t.get("rr_achieved"),
                                    )
                                    for t in result["trades"]
                                ],
                            )

                        # Per-stock results table — requires migration 006
                        try:
                            for sr in result["stock_results"]:
                                m = sr["metrics"]
                                await conn.execute(
                                    """INSERT INTO backtest_stock_results
                                       (backtest_id, symbol, status,
                                        total_trades, winning_trades, win_rate,
                                        total_pnl_abs, avg_pnl_pct,
                                        best_trade_pct, worst_trade_pct,
                                        avg_holding_days, category)
                                       VALUES ($1,$2,'done',$3,$4,$5,$6,$7,$8,$9,$10,$11)
                                       ON CONFLICT (backtest_id, symbol) DO UPDATE SET
                                         total_trades     = EXCLUDED.total_trades,
                                         winning_trades   = EXCLUDED.winning_trades,
                                         win_rate         = EXCLUDED.win_rate,
                                         total_pnl_abs    = EXCLUDED.total_pnl_abs,
                                         avg_pnl_pct      = EXCLUDED.avg_pnl_pct,
                                         best_trade_pct   = EXCLUDED.best_trade_pct,
                                         worst_trade_pct  = EXCLUDED.worst_trade_pct,
                                         avg_holding_days = EXCLUDED.avg_holding_days,
                                         category         = EXCLUDED.category""",
                                    bid, sr["symbol"],
                                    m["total_trades"], m["winning_trades"], m["win_rate"],
                                    m["total_pnl_abs"], m["avg_pnl_pct"],
                                    m["best_trade_pct"], m["worst_trade_pct"],
                                    m["avg_holding_days"], m["category"],
                                )
                        except Exception as persist_err:
                            log.warning("backtest_stock_results_persist_failed",
                                        error=str(persist_err),
                                        hint="Run migration 006_backtest_streaming.sql")

                        scanned += len(batch)
                        try:
                            await conn.execute(
                                "UPDATE backtests SET scanned_symbols=$2 WHERE id=$1", bid, scanned
                            )
                        except Exception:
                            pass  # column added by migration 006 — non-critical

                    # Stream per-stock completion events
                    for sr in result["stock_results"]:
                        await pub("backtest:progress", "backtest.stock_complete", {
                            "backtest_id": backtest_id,
                            "symbol": sr["symbol"],
                            "status": "done",
                            "completed": scanned,
                            "total": total,
                            **sr["metrics"],
                        })

                    all_trades.extend(result["trades"])
                    log.info(
                        "backtest_batch_done",
                        backtest_id=backtest_id,
                        batch=batch,
                        scanned=scanned,
                        total=total,
                    )

                    # Check if the user cancelled between batches; if so stop immediately
                    # (revoke/SIGTERM is unreliable on Windows solo pool, so we poll the DB)
                    async with local_pool.acquire() as _cc:
                        if await _cc.fetchval("SELECT status FROM backtests WHERE id=$1", bid) == "cancelled":
                            cancelled = True
                            break

                except Exception as batch_err:
                    scanned += len(batch)
                    log.warning(
                        "backtest_batch_failed",
                        backtest_id=backtest_id,
                        batch=batch,
                        error=str(batch_err),
                    )
                    async with local_pool.acquire() as conn:
                        try:
                            for sym in batch:
                                await conn.execute(
                                    """INSERT INTO backtest_stock_results
                                       (backtest_id, symbol, status, total_trades,
                                        winning_trades, error_message)
                                       VALUES ($1,$2,'failed',0,0,$3)
                                       ON CONFLICT (backtest_id, symbol) DO UPDATE SET
                                         status = 'failed',
                                         error_message = EXCLUDED.error_message""",
                                    bid, sym, str(batch_err),
                                )
                        except Exception:
                            pass  # migration 006 not applied — skip per-stock persistence
                        try:
                            await conn.execute(
                                "UPDATE backtests SET scanned_symbols=$2 WHERE id=$1", bid, scanned
                            )
                        except Exception:
                            pass
                    for sym in batch:
                        await pub("backtest:progress", "backtest.stock_complete", {
                            "backtest_id": backtest_id,
                            "symbol": sym,
                            "status": "failed",
                            "error": str(batch_err),
                            "completed": scanned,
                            "total": total,
                            "total_trades": 0,
                            "winning_trades": 0,
                            "win_rate": 0.0,
                            "total_pnl_abs": 0.0,
                            "avg_pnl_pct": 0.0,
                            "best_trade_pct": 0.0,
                            "worst_trade_pct": 0.0,
                            "avg_holding_days": 0.0,
                            "category": None,
                        })

                    # Also check cancellation after a failed batch
                    async with local_pool.acquire() as _cc:
                        if await _cc.fetchval("SELECT status FROM backtests WHERE id=$1", bid) == "cancelled":
                            cancelled = True
                            break

        if cancelled:
            log.info("backtest_cancelled_by_user", backtest_id=backtest_id, scanned=scanned, total=total)
            return

        # Aggregate summary across all batches
        total_trades = len(all_trades)
        winning = sum(1 for t in all_trades if (t.get("pnl_abs") or 0) > 0)
        total_pnl = sum(t.get("pnl_abs") or 0 for t in all_trades)
        win_rate = winning / total_trades if total_trades else 0.0
        final_equity = initial_capital + total_pnl

        async with local_pool.acquire() as conn:
            await conn.execute(
                """UPDATE backtests SET
                       status='done', completed_at=NOW(),
                       final_equity=$2, total_trades=$3, winning_trades=$4, win_rate=$5
                   WHERE id=$1""",
                bid, final_equity, total_trades, winning, win_rate,
            )

        await pub("scan:complete", "backtest.complete", {"backtest_id": backtest_id})
        log.info(
            "backtest_completed",
            backtest_id=backtest_id,
            total_trades=total_trades,
            final_equity=final_equity,
        )

    finally:
        if local_pool is not None:
            await local_pool.close()
        await redis_conn.aclose()


# ── Batch sync helpers (run inside ThreadPoolExecutor) ─────────────────────────

def _run_batch_sync(
    batch: list[str],
    start_date: str,
    end_date: str,
    investment_per_stock: float,
) -> dict:
    """Run BacktestEngine for a single batch; each stock gets its own isolated capital."""
    from app.core.backtester.engine import BacktestEngine

    n = len(batch)
    # Give each stock in the batch its own investment_per_stock capital.
    # total_capital = n * investment_per_stock, position_size = 1/n means each
    # position uses exactly investment_per_stock.  max_positions=n allows all
    # batch stocks to be open simultaneously — equivalent to running each stock
    # independently but in a single shared pass for performance.
    engine = BacktestEngine(
        universe=batch,
        start_date=start_date,
        end_date=end_date,
        initial_capital=investment_per_stock * n,
        position_size_pct=1.0 / n,
        max_positions=n,
    )
    portfolio = engine.run()
    closed = portfolio.closed_trades

    trades = [
        {
            "symbol":       t.symbol,
            "entry_date":   t.entry_date.date(),
            "entry_price":  float(t.entry_price),
            "sl_price":     float(t.sl_price),
            "t1":           float(t.t1),
            "t2":           float(t.t2),
            "t3":           float(t.t3),
            "quantity":     int(t.quantity),
            "tf":           t.tf,
            "category":     t.category,
            "exit_date":    t.exit_date.date() if t.exit_date else None,
            "exit_price":   float(t.exit_price) if t.exit_price is not None else None,
            "exit_reason":  t.exit_reason,
            "pnl_abs":      float(t.pnl_abs),
            "pnl_pct":      float(t.pnl_pct),   # decimal: 0.15 = 15%
            "holding_days": int(t.holding_days),
            "rr_achieved":  float(t.rr_achieved),
        }
        for t in closed
    ]

    stock_results = [
        {
            "symbol":  sym,
            "metrics": _symbol_metrics([t for t in trades if t["symbol"] == sym]),
        }
        for sym in batch
    ]

    return {"trades": trades, "stock_results": stock_results}


def _symbol_metrics(trades: list[dict]) -> dict:
    """Compute per-symbol summary from a list of trade dicts."""
    closed = [t for t in trades if t.get("pnl_abs") is not None]
    wins   = [t for t in closed if t["pnl_abs"] > 0]
    pcts   = [t["pnl_pct"] * 100 for t in closed if t.get("pnl_pct") is not None]
    holds  = [t["holding_days"] for t in closed if t.get("holding_days") is not None]
    top_cat = Counter(
        t["category"] for t in trades if t.get("category")
    ).most_common(1)
    return {
        "total_trades":     len(trades),
        "winning_trades":   len(wins),
        "win_rate":         round(len(wins) / len(closed) * 100, 2) if closed else 0.0,
        "total_pnl_abs":    round(sum(t["pnl_abs"] for t in closed), 2),
        "avg_pnl_pct":      round(sum(pcts) / len(pcts), 4) if pcts else 0.0,
        "best_trade_pct":   round(max(pcts), 4) if pcts else 0.0,
        "worst_trade_pct":  round(min(pcts), 4) if pcts else 0.0,
        "avg_holding_days": round(sum(holds) / len(holds), 2) if holds else 0.0,
        "category":         top_cat[0][0] if top_cat else None,
    }


# ── Single-stock sync path (used by POST /api/stocks/{symbol}/backtest) ────────

def _run_backtest_sync(
    universe: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    investment_per_stock: float | None,
) -> dict:
    from app.core.backtester.engine import BacktestEngine
    from app.core.backtester.metrics import compute_metrics
    from app.core.scanner.universe.nse_universe import get_full_universe

    if not universe:
        universe = get_full_universe(include_midcap=True, include_smallcap=False)

    if investment_per_stock is not None:
        engine = BacktestEngine(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=investment_per_stock,
            position_size_pct=1.0,
            max_positions=1,
        )
    else:
        engine = BacktestEngine(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
        )

    portfolio = engine.run()
    raw = compute_metrics(portfolio)

    eq = portfolio.equity_curve
    final_equity = float(eq.iloc[-1]) if not eq.empty else initial_capital
    closed = portfolio.closed_trades
    winning = sum(1 for t in closed if t.is_winner)

    trades = [
        {
            "symbol":       t.symbol,
            "entry_date":   t.entry_date.date(),
            "entry_price":  float(t.entry_price),
            "sl_price":     float(t.sl_price),
            "t1":           float(t.t1),
            "t2":           float(t.t2),
            "t3":           float(t.t3),
            "quantity":     int(t.quantity),
            "tf":           t.tf,
            "category":     t.category,
            "exit_date":    t.exit_date.date() if t.exit_date else None,
            "exit_price":   float(t.exit_price) if t.exit_price is not None else None,
            "exit_reason":  t.exit_reason,
            "pnl_abs":      float(t.pnl_abs),
            "pnl_pct":      float(t.pnl_pct),
            "holding_days": int(t.holding_days),
            "rr_achieved":  float(t.rr_achieved),
        }
        for t in closed
    ]

    equity_curve = [
        (ts.date(), float(val))
        for ts, val in portfolio._equity_history
    ]

    return {
        "metrics": {
            "final_equity":   final_equity,
            "total_trades":   int(raw["total_trades"]),
            "winning_trades": winning,
            "win_rate":       float(raw["win_rate"]),
            "cagr":           float(raw["cagr"]),
            "sharpe_ratio":   float(raw["sharpe_ratio"]),
            "max_drawdown":   float(raw["max_drawdown"]),
        },
        "trades":       trades,
        "equity_curve": equity_curve,
    }


async def _persist_backtest(conn, backtest_id: UUID, result: dict):
    metrics = result.get("metrics", {})

    await conn.execute(
        """UPDATE backtests SET
               status='done', completed_at=NOW(),
               final_equity=$2, total_trades=$3, winning_trades=$4,
               win_rate=$5, cagr=$6, sharpe_ratio=$7, max_drawdown=$8
           WHERE id=$1""",
        backtest_id,
        metrics.get("final_equity"),
        metrics.get("total_trades"),
        metrics.get("winning_trades"),
        metrics.get("win_rate"),
        metrics.get("cagr"),
        metrics.get("sharpe_ratio"),
        metrics.get("max_drawdown"),
    )

    trades = result.get("trades", [])
    if trades:
        await conn.executemany(
            """INSERT INTO backtest_trades
               (id, backtest_id, symbol, entry_date, entry_price, sl_price,
                t1, t2, t3, quantity, timeframe, category,
                exit_date, exit_price, exit_reason, pnl_abs, pnl_pct, holding_days, rr_achieved)
               VALUES (gen_random_uuid(), $1, $2, $3, $4, $5,
                       $6, $7, $8, $9, $10, $11,
                       $12, $13, $14, $15, $16, $17, $18)""",
            [
                (
                    backtest_id,
                    t["symbol"],
                    t["entry_date"],
                    t["entry_price"],
                    t["sl_price"],
                    t.get("t1"),
                    t.get("t2"),
                    t.get("t3"),
                    t.get("quantity"),
                    t.get("tf"),
                    t.get("category"),
                    t.get("exit_date"),
                    t.get("exit_price"),
                    t.get("exit_reason"),
                    t.get("pnl_abs"),
                    t.get("pnl_pct"),
                    t.get("holding_days"),
                    t.get("rr_achieved"),
                )
                for t in trades
            ],
        )

    equity_curve = result.get("equity_curve", [])
    if equity_curve:
        await conn.executemany(
            """INSERT INTO backtest_equity_curve (backtest_id, curve_date, equity)
               VALUES ($1, $2, $3)
               ON CONFLICT (backtest_id, curve_date) DO NOTHING""",
            [(backtest_id, date_str, equity) for date_str, equity in equity_curve],
        )


async def _mark_failed(backtest_id: str, error: str):
    import asyncpg
    from app.config import get_settings
    settings = get_settings()
    local_pool = await asyncpg.create_pool(
        dsn=settings.database_url, min_size=1, max_size=2, command_timeout=30
    )
    try:
        async with local_pool.acquire() as conn:
            await conn.execute(
                "UPDATE backtests SET status='failed', completed_at=NOW(), error_message=$2 WHERE id=$1",
                UUID(backtest_id),
                error,
            )
    finally:
        await local_pool.close()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
