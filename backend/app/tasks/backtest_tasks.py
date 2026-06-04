"""
Celery task for running the walk-forward backtester.
"""
import asyncio
import json
import sys
import time
import traceback
from uuid import UUID

import structlog
from app.tasks.celery_app import celery_app

log = structlog.get_logger()


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
            # Log but don't re-raise — we still want the task to complete
            log.error("backtest_mark_failed_error", backtest_id=backtest_id, error=str(mark_exc))
        raise exc


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

    settings = get_settings()
    # Do NOT touch the global pool — NeonDB closes idle connections after ~5 minutes,
    # so a 10+ minute backtest needs a fresh, local pool created just before the DB write.
    # Using a local pool means we never overwrite the FastAPI app's global _pool.
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    bid = UUID(backtest_id)
    t0 = time.perf_counter()
    local_pool = None

    try:
        # Resolve universe from stock_master when caller passes an empty list.
        # This happens before the thread pool to stay in the async context where
        # we can create a short-lived DB connection.
        if not universe:
            import asyncpg as _apg
            from app.config import get_settings as _gs
            _settings = _gs()
            _tmp_pool = await _apg.create_pool(dsn=_settings.database_url, min_size=1, max_size=2)
            try:
                from app.queries.stock_master import get_symbols_for_mode
                async with _tmp_pool.acquire() as _conn:
                    universe = await get_symbols_for_mode(_conn, "daily")
            except Exception:
                universe = []
            finally:
                await _tmp_pool.close()

        loop = asyncio.get_running_loop()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as ex:
            result = await loop.run_in_executor(
                ex,
                _run_backtest_sync,
                universe, start_date, end_date, initial_capital, investment_per_stock,
            )

        duration = time.perf_counter() - t0

        # Create a fresh local pool immediately before the DB write.
        local_pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=3,
            command_timeout=30,
        )
        async with local_pool.acquire() as conn:
            await _persist_backtest(conn, bid, result)

        await redis.publish("scan:complete", json.dumps({
            "type": "backtest.complete",
            "payload": {"backtest_id": backtest_id},
            "timestamp": _now(),
        }))
        log.info("backtest_completed", backtest_id=backtest_id, duration=round(duration, 1))
    finally:
        if local_pool is not None:
            await local_pool.close()
        await redis.aclose()


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

    # Empty universe means "use the default" — same behaviour as run_scan()
    if not universe:
        universe = get_full_universe(include_midcap=True, include_smallcap=False)

    # Per-symbol mode: use investment_per_stock as total capital, single position, 100% sizing.
    # This ensures each trade buys floor(investment_per_stock / entry_price) shares.
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
            "symbol": t.symbol,
            "entry_date": t.entry_date.date(),
            "entry_price": float(t.entry_price),
            "sl_price": float(t.sl_price),
            "t1": float(t.t1),
            "t2": float(t.t2),
            "t3": float(t.t3),
            "quantity": int(t.quantity),
            "tf": t.tf,
            "category": t.category,
            "exit_date": t.exit_date.date() if t.exit_date else None,
            "exit_price": float(t.exit_price) if t.exit_price is not None else None,
            "exit_reason": t.exit_reason,
            "pnl_abs": float(t.pnl_abs),
            "pnl_pct": float(t.pnl_pct),   # decimal (0.15 = 15%)
            "holding_days": int(t.holding_days),
            "rr_achieved": float(t.rr_achieved),
        }
        for t in closed
    ]

    equity_curve = [
        (ts.date(), float(val))
        for ts, val in portfolio._equity_history
    ]

    return {
        "metrics": {
            "final_equity": final_equity,
            "total_trades": int(raw["total_trades"]),
            "winning_trades": winning,
            "win_rate": float(raw["win_rate"]),
            "cagr": float(raw["cagr"]),
            "sharpe_ratio": float(raw["sharpe_ratio"]),
            "max_drawdown": float(raw["max_drawdown"]),
        },
        "trades": trades,
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
    local_pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=2, command_timeout=30)
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
