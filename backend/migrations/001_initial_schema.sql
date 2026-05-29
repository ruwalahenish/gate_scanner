-- ============================================================
-- GATE Trading Intelligence Platform — Initial Schema
-- Target: NeonDB (PostgreSQL 16)
-- Run: psql $DATABASE_URL -f 001_initial_schema.sql
-- ============================================================

-- Enable UUID generation (built-in on NeonDB)
-- gen_random_uuid() is available natively in PostgreSQL 13+

-- ============================================================
-- SCAN HISTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS scans (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    mode            VARCHAR(20) NOT NULL DEFAULT 'daily',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    universe_size   INT,
    passed_filter   INT,
    signals_found   INT,
    duration_sec    NUMERIC(8,2),
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_scans_triggered ON scans(triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_status    ON scans(status);

-- ============================================================
-- SIGNALS
-- ============================================================
CREATE TABLE IF NOT EXISTS signals (
    id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id                UUID        NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    symbol                 VARCHAR(20) NOT NULL,
    category               VARCHAR(20) NOT NULL,
    side                   VARCHAR(10),
    signal_timeframe       VARCHAR(10),
    sl_timeframe           VARCHAR(10),
    trend_direction        VARCHAR(10),
    entry                  NUMERIC(12,2),
    stop_loss              NUMERIC(12,2),
    sl_distance_pct        NUMERIC(6,3),
    t1                     NUMERIC(12,2),
    t2                     NUMERIC(12,2),
    t3                     NUMERIC(12,2),
    rr_t1                  NUMERIC(6,2),
    rr_t2                  NUMERIC(6,2),
    rr_t3                  NUMERIC(6,2),
    gate_strength          NUMERIC(6,2),
    volatility_compression NUMERIC(6,2),
    breakout_probability   NUMERIC(6,2),
    confidence             NUMERIC(6,2),
    rank_score             NUMERIC(6,2),
    mtf_alignment_pct      NUMERIC(6,2),
    structure_quality      NUMERIC(6,2),
    atr                    NUMERIC(12,4),
    htf_confirmed          BOOLEAN,
    correction_validated   BOOLEAN,
    bounce_sequence_valid  BOOLEAN,
    fib_confluence         BOOLEAN,
    phase                  VARCHAR(30),
    trailing_plan          JSONB,
    reasoning              TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_scan_symbol ON signals(scan_id, symbol);
CREATE INDEX IF NOT EXISTS idx_signals_symbol   ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_category ON signals(category);
CREATE INDEX IF NOT EXISTS idx_signals_rank     ON signals(rank_score DESC NULLS LAST);

-- ============================================================
-- PER-TIMEFRAME ANALYSIS (for MTF heatmap)
-- ============================================================
CREATE TABLE IF NOT EXISTS timeframe_analyses (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id          UUID        NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    symbol           VARCHAR(20) NOT NULL,
    timeframe        VARCHAR(10) NOT NULL,
    ema_stack        VARCHAR(20),
    ema_compression  NUMERIC(6,2),
    correction_ema   SMALLINT,
    correction_type  VARCHAR(10),
    correction_depth SMALLINT,
    trend_direction  VARCHAR(10),
    trend_strength   NUMERIC(6,2),
    gate_score       NUMERIC(6,2),
    breakout_prob    NUMERIC(6,2),
    gate_components  JSONB,
    data_points      INT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tf_analyses ON timeframe_analyses(scan_id, symbol, timeframe);

-- ============================================================
-- PAPER PORTFOLIO — CONFIG (single row)
-- ============================================================
CREATE TABLE IF NOT EXISTS portfolio_config (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    initial_capital NUMERIC(14,2) NOT NULL DEFAULT 1000000,
    current_capital NUMERIC(14,2) NOT NULL DEFAULT 1000000,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the single config row
INSERT INTO portfolio_config(id, initial_capital, current_capital)
VALUES(gen_random_uuid(), 1000000, 1000000)
ON CONFLICT DO NOTHING;

-- ============================================================
-- POSITIONS (open / partially closed paper trades)
-- ============================================================
CREATE TABLE IF NOT EXISTS positions (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol           VARCHAR(20) NOT NULL,
    side             VARCHAR(10) NOT NULL DEFAULT 'BUY',
    quantity         INT         NOT NULL,
    avg_entry        NUMERIC(12,2) NOT NULL,
    stop_loss        NUMERIC(12,2),
    t1               NUMERIC(12,2),
    t2               NUMERIC(12,2),
    t3               NUMERIC(12,2),
    trailing_sl      NUMERIC(12,2),
    current_sl_level VARCHAR(10) NOT NULL DEFAULT 'original',
    signal_id        UUID        REFERENCES signals(id) ON DELETE SET NULL,
    opened_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status           VARCHAR(20) NOT NULL DEFAULT 'open',
    notes            TEXT
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);

-- ============================================================
-- TRADES (entry + exit legs)
-- ============================================================
CREATE TABLE IF NOT EXISTS trades (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id  UUID        REFERENCES positions(id) ON DELETE SET NULL,
    symbol       VARCHAR(20) NOT NULL,
    side         VARCHAR(10) NOT NULL,
    quantity     INT         NOT NULL,
    price        NUMERIC(12,2) NOT NULL,
    executed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_reason  VARCHAR(30),
    pnl_abs      NUMERIC(12,2),
    pnl_pct      NUMERIC(8,4),
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol   ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_executed ON trades(executed_at DESC);

-- ============================================================
-- WATCHLIST
-- ============================================================
CREATE TABLE IF NOT EXISTS watchlist (
    id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol   VARCHAR(20) NOT NULL UNIQUE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes    TEXT,
    tags     TEXT[]
);

-- ============================================================
-- ALERTS
-- ============================================================
DO $$
BEGIN
    CREATE TYPE alert_type_enum AS ENUM (
        'price_above', 'price_below',
        'gate_score_gte', 'gate_score_lte',
        'volume_spike', 'category_upgrade',
        'breakout_detected', 'sl_breach_warning', 'target_proximity'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE alert_status_enum AS ENUM (
        'active', 'triggered', 'dismissed', 'expired'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS alerts (
    id              UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol          VARCHAR(20)      NOT NULL,
    alert_type      alert_type_enum  NOT NULL,
    status          alert_status_enum NOT NULL DEFAULT 'active',
    threshold_value NUMERIC(12,2),
    timeframe       VARCHAR(10),
    message         TEXT,
    notify_via      TEXT[]           NOT NULL DEFAULT ARRAY['web'],
    triggered_at    TIMESTAMPTZ,
    triggered_price NUMERIC(12,2),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);

-- ============================================================
-- BACKTESTS
-- ============================================================
CREATE TABLE IF NOT EXISTS backtests (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    universe        TEXT[],
    start_date      DATE        NOT NULL,
    end_date        DATE        NOT NULL,
    initial_capital NUMERIC(14,2) NOT NULL DEFAULT 1000000,
    final_equity    NUMERIC(14,2),
    total_trades    INT,
    winning_trades  INT,
    win_rate        NUMERIC(6,3),
    cagr            NUMERIC(8,4),
    sharpe_ratio    NUMERIC(8,4),
    max_drawdown    NUMERIC(8,4),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    config_snapshot JSONB
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id  UUID        NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    symbol       VARCHAR(20) NOT NULL,
    entry_date   DATE        NOT NULL,
    entry_price  NUMERIC(12,2) NOT NULL,
    sl_price     NUMERIC(12,2) NOT NULL,
    t1           NUMERIC(12,2),
    t2           NUMERIC(12,2),
    t3           NUMERIC(12,2),
    quantity     INT,
    timeframe    VARCHAR(10),
    category     VARCHAR(20),
    exit_date    DATE,
    exit_price   NUMERIC(12,2),
    exit_reason  VARCHAR(20),
    pnl_abs      NUMERIC(12,2),
    pnl_pct      NUMERIC(8,4),
    holding_days INT,
    rr_achieved  NUMERIC(8,4)
);

CREATE INDEX IF NOT EXISTS idx_bt_trades_backtest ON backtest_trades(backtest_id);

CREATE TABLE IF NOT EXISTS backtest_equity_curve (
    backtest_id    UUID  NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    curve_date     DATE  NOT NULL,
    equity         NUMERIC(14,2),
    cash           NUMERIC(14,2),
    open_positions INT,
    PRIMARY KEY (backtest_id, curve_date)
);

-- ============================================================
-- SCAN PERFORMANCE METRICS
-- ============================================================
CREATE TABLE IF NOT EXISTS scan_metrics (
    scan_id         UUID PRIMARY KEY REFERENCES scans(id) ON DELETE CASCADE,
    fetch_sec       NUMERIC(8,2),
    analysis_sec    NUMERIC(8,2),
    signal_gen_sec  NUMERIC(8,2),
    ranking_sec     NUMERIC(8,2),
    persist_sec     NUMERIC(8,2),
    symbols_fetched INT,
    cache_hits      INT,
    cache_misses    INT
);
