-- ============================================================
-- GATE Trading Intelligence Platform — Architecture v2 Migration
-- Migration 004: Remove alerts, enhance watchlist, add auto-trade
--                tracking, and scan schedule config.
-- Run: psql $DATABASE_URL -f backend/migrations/004_architecture_v2.sql
-- Safe to re-run (all operations are idempotent).
-- ============================================================

-- ============================================================
-- 1. REMOVE ALERTS
--    Drop index from migration 003 first (it references alerts.status),
--    then drop the table, then drop the enum types.
-- ============================================================

DROP INDEX  IF EXISTS idx_alerts_status;
DROP INDEX  IF EXISTS idx_alerts_symbol;
DROP TABLE  IF EXISTS alerts CASCADE;
DROP TYPE   IF EXISTS alert_type_enum CASCADE;
DROP TYPE   IF EXISTS alert_status_enum CASCADE;

-- ============================================================
-- 2. ENHANCE WATCHLIST
--    Add status lifecycle, GATE signal data, and source tracking.
--    All new columns have defaults so existing rows are unaffected.
-- ============================================================

ALTER TABLE watchlist
    ADD COLUMN IF NOT EXISTS signal_id      UUID        REFERENCES signals(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status         TEXT        NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'buy_triggered', 'target_hit', 'sl_hit', 'closed')),
    ADD COLUMN IF NOT EXISTS gate_strength  NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS rank_score     NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS entry          NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS stop_loss      NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS t1             NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source         TEXT        NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'scanner'));

CREATE INDEX IF NOT EXISTS idx_watchlist_status ON watchlist(status);
CREATE INDEX IF NOT EXISTS idx_watchlist_source ON watchlist(source);

-- ============================================================
-- 3. WATCHLIST SIGNAL HISTORY
--    Tracks every status change and GATE update for each symbol.
--    Powers the status-timeline view in the Watchlist UI (Milestone 8).
-- ============================================================

CREATE TABLE IF NOT EXISTS watchlist_history (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol      VARCHAR(20) NOT NULL,
    event       TEXT        NOT NULL,   -- 'added' | 'status_change' | 'gate_update' | 'removed'
    from_status TEXT,
    to_status   TEXT,
    details     JSONB       NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_history_symbol
    ON watchlist_history(symbol, occurred_at DESC);

-- ============================================================
-- 4. ENHANCE POSITIONS (paper trading)
--    Mark auto-created positions so automation_service can manage
--    their lifecycle without touching manually opened positions.
-- ============================================================

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS auto_created     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS creation_source  TEXT    NOT NULL DEFAULT 'manual'
        CHECK (creation_source IN ('manual', 'scanner_auto'));

CREATE INDEX IF NOT EXISTS idx_positions_auto_created
    ON positions(auto_created) WHERE auto_created = TRUE;

-- ============================================================
-- 5. SCAN SCHEDULE CONFIG (singleton table, id always = 1)
--    Stores user-configurable daily scan schedule.
--    Celery Beat reads this at startup and after PUT /api/scan-schedule.
-- ============================================================

CREATE TABLE IF NOT EXISTS scan_schedule (
    id                  INT         PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    enabled             BOOLEAN     NOT NULL DEFAULT TRUE,
    cron_expression     TEXT        NOT NULL DEFAULT '0 16 * * 1-5',  -- 4:00 PM IST weekdays
    last_triggered_at   TIMESTAMPTZ,
    next_scheduled_at   TIMESTAMPTZ,
    mode                TEXT        NOT NULL DEFAULT 'nifty500',
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the single config row (idempotent)
INSERT INTO scan_schedule (id, enabled, cron_expression, mode)
VALUES (1, TRUE, '0 16 * * 1-5', 'nifty500')
ON CONFLICT (id) DO NOTHING;
