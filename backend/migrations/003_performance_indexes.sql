-- ============================================================
-- Migration 003 — Performance indexes for signals queries
-- Run: psql $DATABASE_URL -f 003_performance_indexes.sql
-- ============================================================

-- Composite index: dashboard "top signals" query (category + rank)
CREATE INDEX IF NOT EXISTS idx_signals_category_rank
    ON signals(category, rank_score DESC NULLS LAST);

-- Index: time-based pagination and "latest scan" joins
CREATE INDEX IF NOT EXISTS idx_signals_created_at
    ON signals(created_at DESC);

-- Index: symbol history lookups (used by /signals/{symbol}/history)
CREATE INDEX IF NOT EXISTS idx_signals_symbol_created
    ON signals(symbol, created_at DESC);

-- Index: scan_id + symbol for the unique constraint lookup
CREATE INDEX IF NOT EXISTS idx_signals_scan_symbol
    ON signals(scan_id, symbol);

-- Trigram index: fast ILIKE autocomplete on signals.symbol
-- Requires: CREATE EXTENSION IF NOT EXISTS pg_trgm;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
    ) THEN
        CREATE EXTENSION pg_trgm;
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_signals_symbol_trgm
    ON signals USING GIN (symbol gin_trgm_ops);

-- Index: backtest trades per symbol (used by stock detail page)
CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol
    ON backtest_trades(symbol, entry_date DESC);

-- Index: equity curve per backtest (used by /equity-curve endpoint)
CREATE INDEX IF NOT EXISTS idx_equity_curve_backtest_date
    ON backtest_equity_curve(backtest_id, curve_date);

-- Index: alerts by status (used by alert engine every 60s)
CREATE INDEX IF NOT EXISTS idx_alerts_status
    ON alerts(status) WHERE status = 'active';

-- Index: positions by status (used by portfolio summary)
CREATE INDEX IF NOT EXISTS idx_positions_status
    ON positions(status) WHERE status = 'open';
