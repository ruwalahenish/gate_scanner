-- ============================================================
-- GATE Trading Intelligence Platform — Stock Master Registry
-- Migration 002
-- Run: psql $DATABASE_URL -f backend/migrations/002_stock_master.sql
-- ============================================================

-- Trigram extension for fast company-name similarity search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Sync lifecycle enum
DO $$
BEGIN
    CREATE TYPE sync_status_enum AS ENUM ('pending', 'enriched', 'failed', 'delisted');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ----------------------------------------------------------------
-- MAIN TABLE
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_master (
    -- Identity
    symbol          VARCHAR(20)       NOT NULL,
    exchange        VARCHAR(10)       NOT NULL DEFAULT 'NSE',  -- 'NSE' or 'BSE'

    -- From NSE EQUITY_L.csv (populated in Phase 1 sync)
    company_name    VARCHAR(200)      NOT NULL,
    isin            VARCHAR(12),
    series          VARCHAR(10),      -- 'EQ', 'BE', 'SM', etc.
    face_value      NUMERIC(10,2),
    listing_date    DATE,
    market_lot      INT,

    -- Index membership flags (updated in Phase 2; TRUE = currently a constituent)
    in_nifty50      BOOLEAN NOT NULL DEFAULT FALSE,
    in_nifty_next50 BOOLEAN NOT NULL DEFAULT FALSE,
    in_nifty100     BOOLEAN NOT NULL DEFAULT FALSE,
    in_nifty500     BOOLEAN NOT NULL DEFAULT FALSE,
    in_midcap150    BOOLEAN NOT NULL DEFAULT FALSE,
    in_smallcap100  BOOLEAN NOT NULL DEFAULT FALSE,
    is_fno          BOOLEAN NOT NULL DEFAULT FALSE,

    -- Fundamentals from yfinance .info (populated in Phase 3; nullable until enriched)
    sector          VARCHAR(100),
    industry        VARCHAR(100),
    market_cap      BIGINT,           -- INR; Reliance ~1.9e15, safely fits BIGINT
    pe_ratio        NUMERIC(10,2),
    pb_ratio        NUMERIC(10,2),
    dividend_yield  NUMERIC(8,4),     -- fractional e.g. 0.0230 = 2.30%
    eps             NUMERIC(12,2),
    book_value      NUMERIC(12,2),

    -- Sync lifecycle tracking
    sync_status     sync_status_enum  NOT NULL DEFAULT 'pending',
    last_synced_at  TIMESTAMPTZ,
    sync_error      TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (symbol, exchange)
);

-- ----------------------------------------------------------------
-- INDEXES
-- ----------------------------------------------------------------

-- Partial unique index: lets signals JOIN on just symbol without exchange filter
-- (all signals are NSE; this index guarantees uniqueness for NSE symbols)
CREATE UNIQUE INDEX IF NOT EXISTS idx_sm_symbol_nse
    ON stock_master(symbol) WHERE exchange = 'NSE';

-- Trigram index for ILIKE / pg_trgm similarity on company name
CREATE INDEX IF NOT EXISTS idx_sm_company_trgm
    ON stock_master USING gin (company_name gin_trgm_ops);

-- Sector filter
CREATE INDEX IF NOT EXISTS idx_sm_sector
    ON stock_master(sector);

-- Index membership fast scans (partial — only index TRUE rows)
CREATE INDEX IF NOT EXISTS idx_sm_nifty50
    ON stock_master(in_nifty50) WHERE in_nifty50 = TRUE;
CREATE INDEX IF NOT EXISTS idx_sm_nifty500
    ON stock_master(in_nifty500) WHERE in_nifty500 = TRUE;
CREATE INDEX IF NOT EXISTS idx_sm_fno
    ON stock_master(is_fno) WHERE is_fno = TRUE;

-- Sync queue: pick pending/failed rows efficiently
CREATE INDEX IF NOT EXISTS idx_sm_sync_queue
    ON stock_master(sync_status, last_synced_at NULLS FIRST);

-- Market cap ordering
CREATE INDEX IF NOT EXISTS idx_sm_market_cap
    ON stock_master(market_cap DESC NULLS LAST);

-- ISIN unique lookup (partial: only non-null ISINs)
CREATE UNIQUE INDEX IF NOT EXISTS idx_sm_isin
    ON stock_master(isin) WHERE isin IS NOT NULL;
