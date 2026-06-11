-- ============================================================
-- Migration 007 — Optimization indexes
-- Covers hot query paths identified during profiling/optimization:
--   • Dashboard aggregation queries
--   • Scan status lookups & timeline
--   • Signal filtering (category+rank+gate covering index)
--   • Watchlist status lifecycle
--   • Auto-exit position scan
--   • Trade history timeline
-- Run: psql $DATABASE_URL -f backend/migrations/007_optimization_indexes.sql
-- Safe to re-run (all operations are idempotent).
-- ============================================================

-- ── Dashboard ──────────────────────────────────────────────────
-- The dashboard "latest done scan" query filters status='done'
-- and sorts by triggered_at DESC. A partial index keeps it lean.
CREATE INDEX IF NOT EXISTS idx_scans_done_triggered
    ON scans(triggered_at DESC)
    WHERE status = 'done';

-- Signal counts per scan — the dashboard COUNT(*) FILTER queries
-- benefit from a btree on (scan_id, category) so Postgres can
-- use an index-only scan instead of a full sequential scan.
CREATE INDEX IF NOT EXISTS idx_signals_scan_category
    ON signals(scan_id, category);

-- ── Signals list (GET /api/signals, GET /api/scans/latest/signals) ──
-- Covering index for the most common filter: category + rank + gate.
-- Includes entry, stop_loss, t1, rr_t1, symbol as payload columns
-- so Postgres can serve the 50-row page from the index alone.
CREATE INDEX IF NOT EXISTS idx_signals_category_rank_gate
    ON signals(category, rank_score DESC NULLS LAST, gate_strength DESC NULLS LAST)
    INCLUDE (symbol, entry, stop_loss, t1, rr_t1, signal_timeframe);

-- ── Watchlist ──────────────────────────────────────────────────
-- The watchlist list endpoint filters by status and orders by
-- added_at DESC. A composite index avoids a sort step.
CREATE INDEX IF NOT EXISTS idx_watchlist_status_added
    ON watchlist(status, added_at DESC);

-- ── Positions (auto-exit scan) ────────────────────────────────
-- automation_service.auto_exit_positions selects all open auto-
-- created positions. A partial index keeps the scan instant.
CREATE INDEX IF NOT EXISTS idx_positions_open_auto
    ON positions(status)
    WHERE status = 'open' AND auto_created = TRUE;

-- ── Trades (recent trades on dashboard) ───────────────────────
-- Dashboard fetches the 5 most recent closed trades sorted by
-- executed_at DESC. A partial index avoids scanning all trades.
CREATE INDEX IF NOT EXISTS idx_trades_closed_recent
    ON trades(executed_at DESC)
    WHERE pnl_abs IS NOT NULL;

-- ── Backtests ─────────────────────────────────────────────────
-- The backtest list endpoint sorts by started_at DESC.
CREATE INDEX IF NOT EXISTS idx_backtests_started
    ON backtests(started_at DESC);

-- Per-stock results used by the backtest detail page.
CREATE INDEX IF NOT EXISTS idx_backtest_stock_results_bt
    ON backtest_stock_results(backtest_id);

-- ── Stock master ──────────────────────────────────────────────
-- The stocks list endpoint joins stock_master with the latest
-- signal per symbol. An index on (symbol, exchange) already
-- exists as a unique constraint; add a covering index for the
-- signals JOIN used by list_stocks_with_signals.
CREATE INDEX IF NOT EXISTS idx_signals_latest_per_symbol
    ON signals(symbol, created_at DESC)
    INCLUDE (category, gate_strength, rank_score, entry, stop_loss, t1, rr_t1);
